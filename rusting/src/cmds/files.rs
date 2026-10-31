use std::path::PathBuf;

use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Emitter, Manager, State};
use tauri_plugin_dialog::{DialogExt, MessageDialogButtons};

use crate::doc::{is_supported_image, DocInfo, DocSnapshot, Document};
use crate::engine::client::{DetectReq, EngineClient, ExportReq};
use crate::error::AppError;
use crate::logging::file_name_only;
use crate::menu;
use crate::state::AppState;

const IMAGE_FILTER: &[&str] = &["jpg", "jpeg", "png", "webp", "tif", "tiff"];

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ExportRequest {
    pub path: PathBuf,
    pub format: String,
    #[serde(default = "default_quality")]
    pub quality: u8,
    #[serde(default = "default_meta")]
    pub keep_metadata: bool,
    #[serde(default)]
    pub keep_gps: bool,
}

fn default_quality() -> u8 {
    92
}
fn default_meta() -> bool {
    true
}

#[tauri::command]
pub async fn open_image_dialog(app: AppHandle) -> Result<Option<PathBuf>, AppError> {
    let start = {
        let state = app.state::<AppState>();
        state
            .settings
            .lock()
            .ok()
            .and_then(|s| s.last_open_dir.clone())
    };
    let picked = tokio::task::spawn_blocking(move || {
        let mut dialog = app.dialog().file().add_filter("Imágenes", IMAGE_FILTER);
        if let Some(dir) = start {
            dialog = dialog.set_directory(dir);
        }
        dialog.blocking_pick_file().and_then(|f| f.into_path().ok())
    })
    .await
    .map_err(AppError::io)?;
    Ok(picked)
}

#[tauri::command]
pub async fn doc_open(app: AppHandle, st: State<'_, AppState>, path: PathBuf) -> Result<DocInfo, AppError> {
    open_path(&app, &st, path).await
}

pub async fn open_path(app: &AppHandle, st: &AppState, path: PathBuf) -> Result<DocInfo, AppError> {
    if !is_supported_image(&path) {
        let _ = app.emit(
            "app://toast",
            serde_json::json!({ "message": "Formato no admitido" }),
        );
        return Err(AppError::invalid("Formato no admitido"));
    }
    if !confirm_discard(app, st).await {
        return Err(AppError::invalid("cancelado"));
    }
    let client = st.engine.lock().await.client()?;
    {
        let mut doc = st.doc.lock().await;
        if let Some(old) = doc.as_ref() {
            let _ = client.close_session(&old.session_id).await;
            crate::temp::autosave_discard_doc(&st.dirs, old);
        }
        *doc = None;
    }
    let session = client.open_session(&path).await?;
    let mut document = {
        let settings = st.settings.lock().map_err(|_| AppError::invalid("settings"))?;
        Document::open(path.clone(), session, &settings)
    };
    if let Some(parent) = path.parent() {
        if let Ok(mut settings) = st.settings.lock() {
            settings.last_open_dir = Some(parent.to_path_buf());
            settings.push_recent(path.clone());
            let _ = settings.save_to(&st.settings_path);
        }
    }
    let title = crate::cmds::engine::document_title(Some(&document));
    document.working = document.committed.clone();
    detect_best_effort(&client, &mut document).await;
    let info = DocInfo::from_doc(&document);
    *st.doc.lock().await = Some(document);
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.set_title(&title);
    }
    menu::refresh_menu(app);
    let _ = app.emit("doc://opened", &info);
    let _ = app.emit("doc://dirty", serde_json::json!({ "dirty": false, "file_name": info.file_name }));
    Ok(info)
}

#[tauri::command]
pub async fn doc_detect(st: State<'_, AppState>) -> Result<crate::engine::client::DetectResp, AppError> {
    let sid = {
        let doc = st.doc.lock().await;
        doc.as_ref().ok_or(AppError::NoDocument)?.session_id.clone()
    };
    let client = st.engine.lock().await.client()?;
    let mut merged = crate::engine::client::DetectResp::default();
    for what in [vec!["face".into()], vec!["pose".into()], vec!["person_mask".into()]] {
        let req = DetectReq {
            what: what.clone(),
            max_faces: 5,
            max_people: 3,
        };
        match client.detect(&sid, &req).await {
            Ok(resp) => {
                if what.iter().any(|w| w == "face") {
                    merged.faces = resp.faces.clone();
                }
                if what.iter().any(|w| w == "pose") {
                    merged.bodies = resp.bodies.clone();
                }
                if !resp.masks.is_null() {
                    merged.masks = resp.masks.clone();
                }
                if let Some(doc) = st.doc.lock().await.as_mut() {
                    doc.apply_detect(resp, &what);
                }
            }
            Err(err) => log::warn!(target: "engine", "detect {what:?}: {err}"),
        }
    }
    Ok(merged)
}

#[tauri::command]
pub async fn doc_current(st: State<'_, AppState>) -> Result<Option<DocSnapshot>, AppError> {
    let doc = st.doc.lock().await;
    Ok(doc.as_ref().map(|d| DocSnapshot {
        info: DocInfo::from_doc(d),
        state: d.committed.clone(),
        history: d.history_info(),
    }))
}

#[tauri::command]
pub async fn export_dialog(app: AppHandle, st: State<'_, AppState>, format: String) -> Result<Option<PathBuf>, AppError> {
    let (start_dir, suggested) = {
        let doc = st.doc.lock().await;
        let doc = doc.as_ref().ok_or(AppError::NoDocument)?;
        let ext = normalize_format(&format);
        let stem = doc
            .path
            .file_stem()
            .map(|s| s.to_string_lossy().into_owned())
            .unwrap_or_else(|| "foto".into());
        let name = format!("{stem}-morfofix.{ext}");
        let dir = st
            .settings
            .lock()
            .ok()
            .and_then(|s| s.last_export_dir.clone())
            .or_else(|| doc.path.parent().map(|p| p.to_path_buf()));
        (dir, name)
    };
    let picked = tokio::task::spawn_blocking(move || {
        let mut dialog = app
            .dialog()
            .file()
            .set_file_name(&suggested)
            .add_filter("Imágenes", IMAGE_FILTER);
        if let Some(dir) = start_dir {
            dialog = dialog.set_directory(dir);
        }
        dialog.blocking_save_file().and_then(|f| f.into_path().ok())
    })
    .await
    .map_err(AppError::io)?;
    Ok(picked.map(|p| ensure_ext(p, &format)))
}

#[tauri::command]
pub async fn doc_export(app: AppHandle, st: State<'_, AppState>, req: ExportRequest) -> Result<crate::engine::client::ExportResult, AppError> {
    let (sid, state, original) = {
        let doc = st.doc.lock().await;
        let doc = doc.as_ref().ok_or(AppError::NoDocument)?;
        (doc.session_id.clone(), doc.committed.clone(), doc.path.clone())
    };
    let path = ensure_ext(req.path, &req.format);
    if path == original {
        let overwrite = confirm(
            &app,
            "¿Sobrescribir la foto original?",
            "Sobrescribir",
            "Cancelar",
        )
        .await;
        if !overwrite {
            return Err(AppError::invalid("cancelado"));
        }
    }
    let client = st.engine.lock().await.client()?;
    st.export_in_flight.store(true, std::sync::atomic::Ordering::SeqCst);
    let result = client
        .export(
            &sid,
            &ExportReq {
                path: path.clone(),
                state,
                format: normalize_format(&req.format),
                quality: req.quality.clamp(1, 100),
                keep_metadata: req.keep_metadata,
                keep_gps: req.keep_gps,
            },
        )
        .await;
    st.export_in_flight.store(false, std::sync::atomic::Ordering::SeqCst);
    let result = result.map_err(|err| match err {
        AppError::Io(msg) | AppError::Engine(_, msg) => {
            AppError::Io(format!("No se pudo guardar en {}: {msg}", path.display()))
        }
        other => other,
    })?;
    if let Some(doc) = st.doc.lock().await.as_mut() {
        doc.dirty = false;
        crate::temp::autosave_discard_doc(&st.dirs, doc);
    }
    if let Some(parent) = path.parent() {
        if let Ok(mut settings) = st.settings.lock() {
            settings.last_export_dir = Some(parent.to_path_buf());
            let _ = settings.save_to(&st.settings_path);
        }
    }
    if let Some(window) = app.get_webview_window("main") {
        let title = crate::cmds::engine::document_title(st.doc.lock().await.as_ref());
        let _ = window.set_title(&title);
    }
    let _ = app.emit("doc://dirty", serde_json::json!({ "dirty": false }));
    menu::refresh_menu(&app);
    Ok(result)
}

#[tauri::command]
pub fn recents_list(st: State<'_, AppState>) -> Vec<crate::settings::RecentItem> {
    st.settings.lock().map(|s| s.recents_existing()).unwrap_or_default()
}

#[tauri::command]
pub fn recents_clear(app: AppHandle, st: State<'_, AppState>) {
    if let Ok(mut settings) = st.settings.lock() {
        settings.recents.clear();
        let _ = settings.save_to(&st.settings_path);
    }
    menu::refresh_menu(&app);
}

pub async fn menu_open(app: &AppHandle) {
    match open_image_dialog(app.clone()).await {
        Ok(Some(path)) => {
            let state = app.state::<AppState>();
            if let Err(err) = open_path(app, &*state, path).await {
                log::warn!("abrir: {err}");
            }
        }
        Ok(None) => {}
        Err(err) => log::warn!("diálogo abrir: {err}"),
    }
}

pub async fn menu_export(app: &AppHandle) {
    let state = app.state::<AppState>();
    let format = state
        .settings
        .lock()
        .map(|s| s.export.format.clone())
        .unwrap_or_else(|_| "jpeg".into());
    match export_dialog(app.clone(), state.clone(), format.clone()).await {
        Ok(Some(path)) => {
            let quality = state.settings.lock().map(|s| s.export.quality).unwrap_or(92);
            let keep_metadata = state.settings.lock().map(|s| s.export.keep_metadata).unwrap_or(true);
            let keep_gps = state.settings.lock().map(|s| s.export.keep_gps).unwrap_or(false);
            let req = ExportRequest {
                path,
                format,
                quality,
                keep_metadata,
                keep_gps,
            };
            if let Err(err) = doc_export(app.clone(), state.clone(), req).await {
                let _ = app.emit("app://toast", serde_json::json!({ "message": err.to_string() }));
            }
        }
        Ok(None) => {}
        Err(AppError::NoDocument) => {}
        Err(err) => log::warn!("export: {err}"),
    }
}

pub async fn menu_close(app: &AppHandle) {
    let state = app.state::<AppState>();
    if !confirm_discard(app, &*state).await {
        return;
    }
    close_doc(app, &*state).await;
}

pub async fn close_doc(app: &AppHandle, st: &AppState) {
    let client = st.engine.lock().await.client().ok();
    let mut doc = st.doc.lock().await;
    if let Some(old) = doc.take() {
        if let Some(client) = client {
            let _ = client.close_session(&old.session_id).await;
        }
        crate::temp::autosave_discard_doc(&st.dirs, &old);
    }
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.set_title("MorfoFix");
    }
    let _ = app.emit("doc://closed", ());
    menu::refresh_menu(app);
}

pub async fn open_recent(app: &AppHandle, idx: usize) {
    let path = {
        let state = app.state::<AppState>();
        state
            .settings
            .lock()
            .ok()
            .and_then(|s| s.recents_existing().get(idx).map(|r| r.path.clone()))
    };
    if let Some(path) = path {
        let state = app.state::<AppState>();
        let _ = open_path(app, &*state, path).await;
    }
}

pub async fn confirm_discard(app: &AppHandle, st: &AppState) -> bool {
    let dirty = st.doc.lock().await.as_ref().map(|d| d.dirty).unwrap_or(false);
    if !dirty {
        return true;
    }
    confirm(
        app,
        "Tenés cambios sin exportar. ¿Salir igual?",
        "Salir",
        "Cancelar",
    )
    .await
}

pub async fn confirm(app: &AppHandle, message: &str, ok: &str, cancel: &str) -> bool {
    let app = app.clone();
    let message = message.to_string();
    let ok = ok.to_string();
    let cancel = cancel.to_string();
    tokio::task::spawn_blocking(move || {
        app.dialog()
            .message(message)
            .title("MorfoFix")
            .buttons(MessageDialogButtons::OkCancelCustom(ok, cancel))
            .blocking_show()
    })
    .await
    .unwrap_or(false)
}

pub fn normalize_format(format: &str) -> String {
    match format.to_ascii_lowercase().as_str() {
        "jpg" | "jpeg" => "jpeg".into(),
        "png" => "png".into(),
        "webp" => "webp".into(),
        "tif" | "tiff" => "tiff".into(),
        other => other.to_string(),
    }
}

pub fn ensure_ext(path: PathBuf, format: &str) -> PathBuf {
    let fmt = normalize_format(format);
    let want = match fmt.as_str() {
        "jpeg" => "jpg",
        "tiff" => "tiff",
        other => other,
    };
    match path.extension().and_then(|e| e.to_str()).map(|e| e.to_ascii_lowercase()) {
        Some(ext) if ext == want || (want == "jpg" && ext == "jpeg") || (want == "tiff" && ext == "tif") => path,
        _ => path.with_extension(want),
    }
}

pub(crate) async fn detect_best_effort(client: &EngineClient, document: &mut Document) {
    for what in [vec!["face".into()], vec!["pose".into()]] {
        let req = DetectReq {
            what: what.clone(),
            max_faces: 5,
            max_people: 3,
        };
        match client.detect(&document.session_id, &req).await {
            Ok(resp) => document.apply_detect(resp, &what),
            Err(err) => log::warn!(target: "engine", "detect {what:?}: {err}"),
        }
    }
}

pub async fn handle_drop(app: &AppHandle, paths: Vec<PathBuf>) {
    let Some(path) = paths.into_iter().next() else {
        return;
    };
    if !is_supported_image(&path) {
        let _ = app.emit(
            "app://toast",
            serde_json::json!({ "message": "Formato no admitido" }),
        );
        log::info!("drop ignorado {}", file_name_only(&path));
        return;
    }
    let state = app.state::<AppState>();
    if let Err(err) = open_path(app, &*state, path).await {
        log::warn!("drop: {err}");
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::doc::edit_state::EditState;
    use crate::engine::client::{EngineClient, RenderReq, SessionInfo};
    use crate::settings::Settings;
    use serde_json::json;
    use wiremock::matchers::{method, path, path_regex};
    use wiremock::{Mock, MockServer, ResponseTemplate};

    #[tokio::test]
    async fn after_respawn_detect_before_render() {
        let server = MockServer::start().await;
        Mock::given(method("POST"))
            .and(path("/session"))
            .respond_with(ResponseTemplate::new(200).set_body_json(json!({
                "session_id": "s-new",
                "width": 10,
                "height": 10
            })))
            .mount(&server)
            .await;
        Mock::given(method("POST"))
            .and(path_regex(r"^/session/.+/detect$"))
            .respond_with(ResponseTemplate::new(200).set_body_json(json!({
                "faces": [{"index": 0, "bbox": [0.1, 0.1, 0.5, 0.5]}],
                "bodies": []
            })))
            .mount(&server)
            .await;
        Mock::given(method("POST"))
            .and(path_regex(r"^/session/.+/render$"))
            .respond_with(
                ResponseTemplate::new(200)
                    .set_body_raw([0xff, 0xd8, 0xff, 0xd9], "image/jpeg")
                    .insert_header("X-Rev", "1")
                    .insert_header("X-Render-Ms", "1.0"),
            )
            .mount(&server)
            .await;

        let client = EngineClient::new(server.address().port(), "tok").unwrap();
        let session = SessionInfo {
            session_id: "s-old".into(),
            width: 10,
            height: 10,
            preview_width: 10,
            preview_height: 10,
            orientation_applied: 0,
            format: "jpeg".into(),
            has_alpha: false,
            icc: false,
            image_sha1: String::new(),
            warnings: Vec::new(),
        };
        let mut document = Document::open(PathBuf::from("/tmp/foto.jpg"), session, &Settings::default());
        let info = client.open_session(&document.path).await.unwrap();
        document.session_id = info.session_id.clone();
        document.info = info;
        detect_best_effort(&client, &mut document).await;
        let req = RenderReq {
            rev: 1,
            state: EditState::new(),
            target: "preview".into(),
            max_side: 1600,
            format: "jpeg".into(),
            quality: 85,
            overlay: None,
        };
        client.render(&document.session_id, &req).await.unwrap();

        let rec = server.received_requests().await.unwrap();
        let paths: Vec<String> = rec.iter().map(|r| r.url.path().to_string()).collect();
        let detect_at = paths.iter().position(|p| p.ends_with("/detect")).expect("detect");
        let render_at = paths.iter().position(|p| p.ends_with("/render")).expect("render");
        assert!(detect_at < render_at, "detect debe ir antes de render: {paths:?}");
        assert_eq!(document.session_id, "s-new");
        assert_eq!(document.face_indices, vec![0]);
    }
}
