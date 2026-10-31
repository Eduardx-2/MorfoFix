use serde_json::Value;
use tauri::{AppHandle, State};
use uuid::Uuid;

use crate::doc::DocInfo;
use crate::error::AppError;
use crate::menu;
use crate::settings::Settings;
use crate::state::AppState;
use crate::temp::{self, AutosaveInfo};

#[tauri::command]
pub fn settings_get(st: State<'_, AppState>) -> Result<Settings, AppError> {
    st.settings
        .lock()
        .map(|s| s.clone())
        .map_err(|_| AppError::invalid("settings"))
}

#[tauri::command]
pub fn settings_set(app: AppHandle, st: State<'_, AppState>, patch: Value) -> Result<Settings, AppError> {
    let mut settings = st.settings.lock().map_err(|_| AppError::invalid("settings"))?;
    settings.merge_patch(&patch)?;
    settings.save_to(&st.settings_path)?;
    let cloned = settings.clone();
    drop(settings);
    menu::refresh_menu(&app);
    Ok(cloned)
}

#[tauri::command]
pub fn autosave_list(st: State<'_, AppState>) -> Vec<AutosaveInfo> {
    temp::autosave_find(&st.dirs)
}

#[tauri::command]
pub async fn autosave_restore(app: AppHandle, st: State<'_, AppState>, id: Uuid) -> Result<DocInfo, AppError> {
    let (file, _) = temp::autosave_load(&st.dirs, id)?;
    let info = crate::cmds::files::open_path(&app, &*st, file.path.clone()).await?;
    {
        let mut doc = st.doc.lock().await;
        if let Some(doc) = doc.as_mut() {
            doc.committed = file.committed.clone();
            doc.working = file.committed.clone();
            doc.history.restore_undo(
                file.history
                    .into_iter()
                    .map(|s| (s, "recuperado".into()))
                    .collect(),
            );
            doc.dirty = true;
        }
    }
    let _ = crate::cmds::edit::rerender(&app).await;
    Ok(info)
}

#[tauri::command]
pub fn autosave_discard(st: State<'_, AppState>, id: Uuid) {
    temp::autosave_discard(&st.dirs, id);
}
