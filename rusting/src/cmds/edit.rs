use std::time::Duration;

use tauri::ipc::Response;
use tauri::{AppHandle, Emitter, Manager, State};

use crate::doc::edit_state::{
    apply_param, kind_of, sanitize_with_indices, ui_to_degree, ui_to_intensity, EditState, Kind, Target,
};
use crate::doc::history::HistoryInfo;
use crate::engine::client::{RenderOut, RenderReq};
use crate::error::AppError;
use crate::menu;
use crate::state::AppState;

#[tauri::command]
pub async fn edit_preview(
    app: AppHandle,
    st: State<'_, AppState>,
    mut state: EditState,
    interactive: bool,
    overlay: Option<String>,
) -> Result<Response, AppError> {
    if let Some(doc) = st.doc.lock().await.as_mut() {
        doc.overlay = overlay.clone();
    }
    preview_state(&app, &st, &mut state, interactive, overlay).await
}

#[tauri::command]
pub async fn doc_preview(app: AppHandle, st: State<'_, AppState>) -> Result<Response, AppError> {
    let (mut working, overlay) = {
        let doc = st.doc.lock().await;
        let doc = doc.as_ref().ok_or(AppError::NoDocument)?;
        (doc.working.clone(), doc.overlay.clone())
    };
    preview_state(&app, &st, &mut working, false, overlay).await
}

#[tauri::command]
pub async fn edit_commit(app: AppHandle, st: State<'_, AppState>, mut state: EditState, label: String) -> Result<HistoryInfo, AppError> {
    let catalog = st.catalog.read().await.clone();
    let info = {
        let mut guard = st.doc.lock().await;
        let doc = guard.as_mut().ok_or(AppError::NoDocument)?;
        let faces = if doc.face_indices.is_empty() {
            None
        } else {
            Some(doc.face_indices.as_slice())
        };
        let bodies = if doc.body_indices.is_empty() {
            None
        } else {
            Some(doc.body_indices.as_slice())
        };
        let fixes = sanitize_with_indices(&mut state, &catalog, faces, bodies);
        log_fixes(&fixes);
        if state != doc.committed {
            doc.history.commit(doc.committed.clone(), &label);
            doc.committed = state.clone();
            doc.working = state;
            doc.dirty = true;
        }
        doc.history_info()
    };
    emit_doc_meta(&app, &st).await;
    schedule_autosave(app.clone());
    Ok(info)
}

#[tauri::command]
pub async fn edit_set_param(
    app: AppHandle,
    st: State<'_, AppState>,
    name: String,
    value_ui: i32,
    target: Target,
    commit: bool,
) -> Result<Response, AppError> {
    let value = match kind_of(&name) {
        Some(Kind::Degree) => ui_to_degree(value_ui),
        Some(Kind::Intensity) => ui_to_intensity(value_ui),
        None => return Err(AppError::invalid(format!("param desconocido: {name}"))),
    };
    let mut working = {
        let mut doc = st.doc.lock().await;
        let doc = doc.as_mut().ok_or(AppError::NoDocument)?;
        apply_param(&mut doc.working, &name, value, &target)?;
        doc.working.clone()
    };
    if commit {
        let _ = edit_commit(app.clone(), st.clone(), working.clone(), pretty_label(&name)).await?;
    }
    preview_state(&app, &st, &mut working, !commit, None).await
}

#[tauri::command]
pub async fn history_undo(app: AppHandle, st: State<'_, AppState>) -> Result<HistoryInfo, AppError> {
    let info = {
        let mut doc = st.doc.lock().await;
        let doc = doc.as_mut().ok_or(AppError::NoDocument)?;
        if let Some(prev) = doc.history.undo(doc.committed.clone()) {
            doc.committed = prev.clone();
            doc.working = prev;
            doc.dirty = true;
        }
        doc.history_info()
    };
    emit_doc_meta(&app, &st).await;
    let _ = app.emit("history://changed", &info);
    Ok(info)
}

#[tauri::command]
pub async fn history_redo(app: AppHandle, st: State<'_, AppState>) -> Result<HistoryInfo, AppError> {
    let info = {
        let mut doc = st.doc.lock().await;
        let doc = doc.as_mut().ok_or(AppError::NoDocument)?;
        if let Some(next) = doc.history.redo(doc.committed.clone()) {
            doc.committed = next.clone();
            doc.working = next;
            doc.dirty = true;
        }
        doc.history_info()
    };
    emit_doc_meta(&app, &st).await;
    let _ = app.emit("history://changed", &info);
    Ok(info)
}

pub async fn reset_all(app: &AppHandle) {
    let state = app.state::<AppState>();
    let fresh = EditState::new();
    if let Ok(info) = edit_commit(app.clone(), state, fresh, "Restablecer todo".into()).await {
        let _ = app.emit("history://changed", &info);
        let _ = rerender(app).await;
    }
}

pub async fn rerender(app: &AppHandle) -> Result<Response, AppError> {
    let state = app.state::<AppState>();
    let mut working = {
        let doc = state.doc.lock().await;
        doc.as_ref().ok_or(AppError::NoDocument)?.committed.clone()
    };
    preview_state(app, &state, &mut working, false, None).await
}

async fn preview_state(
    app: &AppHandle,
    st: &AppState,
    state: &mut EditState,
    interactive: bool,
    overlay: Option<String>,
) -> Result<Response, AppError> {
    let catalog = st.catalog.read().await.clone();
    let max_side = choose_max_side(st, interactive).await;
    let (sid, rev, faces, bodies) = {
        let mut doc = st.doc.lock().await;
        let doc = doc.as_mut().ok_or(AppError::NoDocument)?;
        let faces = doc.face_indices.clone();
        let bodies = doc.body_indices.clone();
        let fixes = sanitize_with_indices(
            state,
            &catalog,
            if faces.is_empty() { None } else { Some(faces.as_slice()) },
            if bodies.is_empty() { None } else { Some(bodies.as_slice()) },
        );
        log_fixes(&fixes);
        if !state.muscle.is_empty() {
            log::debug!(
                target: "engine",
                "preview muscle personas={} modos={:?}",
                state.muscle.len(),
                state.muscle.values().map(|m| m.mode.as_str()).collect::<Vec<_>>()
            );
        }
        doc.working = state.clone();
        (doc.session_id.clone(), doc.next_rev(), faces, bodies)
    };
    let _ = (faces, bodies);
    let req = RenderReq {
        rev,
        state: state.clone(),
        target: "preview".into(),
        max_side,
        format: "jpeg".into(),
        quality: 85,
        overlay,
    };
    let client = st.engine.lock().await.client()?;
    *st.render_started.lock().await = Some(std::time::Instant::now());
    let app_busy = app.clone();
    let busy = tokio::spawn(async move {
        tokio::time::sleep(Duration::from_millis(150)).await;
        let _ = app_busy.emit("preview://busy", true);
    });
    let result = st
        .scheduler
        .submit_with(req, move |req| {
            let client = client.clone();
            let sid = sid.clone();
            async move { client.render(&sid, &req).await }
        })
        .await;
    busy.abort();
    *st.render_started.lock().await = None;
    let _ = app.emit("preview://busy", false);
    match result {
        Ok(out) => deliver_preview(app, st, interactive, out).await,
        Err(AppError::EngineDown(msg)) => Err(AppError::EngineDown(msg)),
        Err(err) => Err(err),
    }
}

async fn deliver_preview(
    app: &AppHandle,
    st: &AppState,
    interactive: bool,
    out: RenderOut,
) -> Result<Response, AppError> {
    if interactive {
        let mut window = st.interactive_ms.lock().await;
        window.push_back(out.ms);
        while window.len() > 5 {
            window.pop_front();
        }
    }
    let _ = app.emit(
        "preview://meta",
        serde_json::json!({
            "rev": out.rev,
            "ms": out.ms,
            "warnings": out.warnings,
        }),
    );
    Ok(Response::new(out.bytes))
}

async fn choose_max_side(st: &AppState, interactive: bool) -> u32 {
    let (preview, interactive_side) = {
        match st.settings.lock() {
            Ok(s) => (s.preview_max_side, s.preview_interactive_side),
            Err(_) => (1600, 1200),
        }
    };
    if !interactive {
        return preview;
    }
    let avg = {
        let window = st.interactive_ms.lock().await;
        if window.len() == 5 {
            Some(window.iter().sum::<f64>() / window.len() as f64)
        } else {
            None
        }
    };
    if avg.unwrap_or(0.0) > 150.0 {
        900
    } else {
        interactive_side
    }
}

async fn emit_doc_meta(app: &AppHandle, st: &AppState) {
    let (dirty, name, title) = {
        let doc = st.doc.lock().await;
        match doc.as_ref() {
            Some(doc) => (
                doc.dirty,
                doc.file_name(),
                crate::cmds::engine::document_title(Some(doc)),
            ),
            None => (false, String::new(), "MorfoFix".into()),
        }
    };
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.set_title(&title);
    }
    let _ = app.emit("doc://dirty", serde_json::json!({ "dirty": dirty, "file_name": name }));
    menu::refresh_menu(app);
}

fn schedule_autosave(app: AppHandle) {
    let state = app.state::<AppState>();
    let gen = state.autosave_gen.fetch_add(1, std::sync::atomic::Ordering::SeqCst) + 1;
    tauri::async_runtime::spawn(async move {
        tokio::time::sleep(Duration::from_secs(2)).await;
        let state = app.state::<AppState>();
        if state.autosave_gen.load(std::sync::atomic::Ordering::SeqCst) != gen {
            return;
        }
        let doc = state.doc.lock().await;
        if let Some(doc) = doc.as_ref() {
            if let Err(err) = crate::temp::autosave_write(&state.dirs, doc) {
                log::warn!("autosave: {err}");
            }
        }
    });
}

fn log_fixes(fixes: &[crate::doc::edit_state::Fix]) {
    for fix in fixes {
        log::warn!(target: "sanitize", "{}: {}", fix.path, fix.reason);
    }
}

fn pretty_label(name: &str) -> String {
    name.trim_start_matches("left_")
        .trim_start_matches("right_")
        .trim_start_matches("up_")
        .trim_start_matches("down_")
        .trim_start_matches("intensity_")
        .trim_start_matches("degree_")
        .replace('_', " ")
}
