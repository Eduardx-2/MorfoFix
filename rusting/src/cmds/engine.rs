use tauri::{AppHandle, Emitter, Manager, State};

use crate::doc::edit_state::CatalogItem;
use crate::doc::{DocInfo, Document};
use crate::engine::{health_loop, EngineStatusDto};
use crate::error::AppError;
use crate::state::AppState;

#[tauri::command]
pub async fn engine_catalog(st: State<'_, AppState>) -> Result<Vec<CatalogItem>, AppError> {
    Ok(st.catalog.read().await.items.clone())
}

#[tauri::command]
pub async fn engine_status(st: State<'_, AppState>) -> Result<EngineStatusDto, AppError> {
    Ok(st.engine.lock().await.status_dto())
}

#[tauri::command]
pub async fn engine_restart(app: AppHandle, st: State<'_, AppState>) -> Result<EngineStatusDto, AppError> {
    {
        let mut engine = st.engine.lock().await;
        engine.reset_restart_window();
        engine.restart(&app).await?;
    }
    after_engine_ready(&app).await;
    Ok(st.engine.lock().await.status_dto())
}

pub async fn recover_after_crash(app: &AppHandle) {
    let state = app.state::<AppState>();
    {
        let mut engine = state.engine.lock().await;
        if engine.is_intended_shutdown() {
            return;
        }
        match engine.restart(app).await {
            Ok(()) => {}
            Err(err) => {
                log::error!(target: "engine", "restart falló: {err}");
                return;
            }
        }
    }
    after_engine_ready(app).await;
}

pub async fn after_engine_ready(app: &AppHandle) {
    let state = app.state::<AppState>();
    let client = {
        let engine = state.engine.lock().await;
        match engine.client() {
            Ok(c) => c,
            Err(_) => return,
        }
    };
    if let Ok(catalog) = client.catalog().await {
        state.set_catalog(catalog).await;
    }
    if let Ok(health) = client.health().await {
        state.engine.lock().await.set_models(&health);
        let _ = app.emit("engine://state", state.engine.lock().await.status_dto());
    }
    let mut doc_guard = state.doc.lock().await;
    if let Some(doc) = doc_guard.as_mut() {
        match client.open_session(&doc.path).await {
            Ok(info) => {
                doc.session_id = info.session_id.clone();
                doc.info = info;
                crate::cmds::files::detect_best_effort(&client, doc).await;
                let opened = DocInfo::from_doc(doc);
                drop(doc_guard);
                let _ = app.emit("doc://opened", &opened);
                let _ = crate::cmds::edit::rerender(app).await;
            }
            Err(err) => log::error!(target: "engine", "re-session: {err}"),
        }
    }
}

pub async fn start_engine(app: AppHandle) {
    {
        let state = app.state::<AppState>();
        let mut engine = state.engine.lock().await;
        if let Err(err) = engine.start(&app).await {
            log::error!(target: "engine", "arranque: {err}");
            return;
        }
    }
    after_engine_ready(&app).await;
    tauri::async_runtime::spawn(health_loop(app));
}

pub fn document_title(doc: Option<&Document>) -> String {
    match doc {
        Some(doc) => {
            let mark = if doc.dirty { "• " } else { "" };
            format!("MorfoFix — {mark}{}", doc.file_name())
        }
        None => "MorfoFix".into(),
    }
}
