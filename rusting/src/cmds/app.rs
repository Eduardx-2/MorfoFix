use std::sync::atomic::Ordering;

use tauri::{AppHandle, Manager, State};
use tauri_plugin_dialog::DialogExt;
use tauri_plugin_opener::OpenerExt;

use crate::error::AppError;
use crate::state::AppState;

#[tauri::command]
pub fn open_logs_dir(app: AppHandle, st: State<'_, AppState>) -> Result<(), AppError> {
    let dir = st.dirs.logs.clone();
    std::fs::create_dir_all(&dir)?;
    app.opener()
        .open_path(dir.display().to_string(), None::<String>)
        .map_err(|e| AppError::io(e))?;
    Ok(())
}

#[tauri::command]
pub async fn about_info(st: State<'_, AppState>) -> Result<serde_json::Value, AppError> {
    let engine = st.engine.lock().await.status_dto();
    Ok(serde_json::json!({
        "app": "MorfoFix",
        "app_version": env!("CARGO_PKG_VERSION"),
        "engine": engine,
    }))
}

pub async fn show_about(app: &AppHandle) {
    let state = app.state::<AppState>();
    let info = about_info(state).await.unwrap_or_else(|_| serde_json::json!({}));
    let engine = info.get("engine").cloned().unwrap_or(serde_json::Value::Null);
    let version = info.get("app_version").and_then(|v| v.as_str()).unwrap_or("0.1.0");
    let engine_ver = engine.get("version").and_then(|v| v.as_str()).unwrap_or("—");
    let models = engine.get("models").cloned().unwrap_or(serde_json::json!({}));
    let message = format!("MorfoFix {version}\nMotor {engine_ver}\nModelos: {models}\nOffline · sin telemetría");
    let app = app.clone();
    let _ = tokio::task::spawn_blocking(move || {
        app.dialog().message(message).title("Acerca de MorfoFix").blocking_show();
    })
    .await;
}

pub fn open_licenses(app: &AppHandle) {
    let path = app
        .path()
        .resource_dir()
        .ok()
        .map(|p| p.join("LICENSES.md"))
        .filter(|p| p.exists())
        .unwrap_or_else(|| PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("LICENSES.md"));
    let _ = app.opener().open_path(path.display().to_string(), None::<String>);
}

pub async fn request_quit(app: &AppHandle) {
    let state = app.state::<AppState>();
    if !crate::cmds::files::confirm_discard(app, &*state).await {
        return;
    }
    shutdown_and_exit(app).await;
}

pub async fn shutdown_and_exit(app: &AppHandle) {
    let state = app.state::<AppState>();
    if state.shutting_down.swap(true, Ordering::SeqCst) {
        return;
    }
    state.engine.lock().await.shutdown().await;
    app.exit(0);
}

use std::path::PathBuf;
