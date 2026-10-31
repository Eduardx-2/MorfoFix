use std::fs;
use std::path::PathBuf;
#[cfg(feature = "desktop")]
use std::path::Path;
#[cfg(feature = "desktop")]
use std::time::{Duration, SystemTime};

use serde::{Deserialize, Serialize};
#[cfg(feature = "desktop")]
use tauri::{AppHandle, Manager};
use uuid::Uuid;

use crate::doc::Document;
use crate::error::AppError;
use crate::settings::atomic_write;

#[cfg(feature = "desktop")]
const CACHE_MAX_BYTES: u64 = 1024 * 1024 * 1024;
#[cfg(feature = "desktop")]
const CACHE_MAX_AGE: Duration = Duration::from_secs(30 * 24 * 3600);

#[derive(Clone, Debug)]
pub struct TempDirs {
    pub cache: PathBuf,
    pub engine_cache: PathBuf,
    pub tmp: PathBuf,
    pub data: PathBuf,
    pub autosave: PathBuf,
    pub config: PathBuf,
    pub logs: PathBuf,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct AutosaveInfo {
    pub id: Uuid,
    pub path: PathBuf,
    pub file_name: String,
    pub saved_at: u64,
}

#[derive(Serialize, Deserialize)]
pub struct AutosaveFile {
    pub id: Uuid,
    pub path: PathBuf,
    pub committed: crate::doc::edit_state::EditState,
    pub history: Vec<crate::doc::edit_state::EditState>,
    pub saved_at: u64,
}

#[cfg(feature = "desktop")]
pub fn temp_init(app: &AppHandle) -> Result<TempDirs, AppError> {
    let cache = app.path().app_cache_dir().map_err(AppError::io)?;
    let data = app.path().app_data_dir().map_err(AppError::io)?;
    let config = app.path().app_config_dir().map_err(AppError::io)?;
    let logs = app.path().app_log_dir().map_err(AppError::io)?;
    let dirs = TempDirs {
        engine_cache: cache.join("engine-cache"),
        tmp: cache.join("tmp"),
        autosave: data.join("autosave"),
        cache,
        data,
        config,
        logs,
    };
    for dir in [
        &dirs.cache,
        &dirs.engine_cache,
        &dirs.tmp,
        &dirs.data,
        &dirs.autosave,
        &dirs.config,
        &dirs.logs,
    ] {
        fs::create_dir_all(dir)?;
    }
    prune_cache(&dirs.engine_cache);
    Ok(dirs)
}

pub fn autosave_write(dirs: &TempDirs, doc: &Document) -> Result<(), AppError> {
    let payload = AutosaveFile {
        id: doc.id,
        path: doc.path.clone(),
        committed: doc.committed.clone(),
        history: doc.history.snapshot_undo(20),
        saved_at: now_secs(),
    };
    let bytes = serde_json::to_vec_pretty(&payload)?;
    atomic_write(&dirs.autosave.join(format!("{}.json", doc.id)), &bytes)
}

pub fn autosave_find(dirs: &TempDirs) -> Vec<AutosaveInfo> {
    let mut out = Vec::new();
    let Ok(entries) = fs::read_dir(&dirs.autosave) else {
        return out;
    };
    for entry in entries.flatten() {
        let path = entry.path();
        if path.extension().and_then(|e| e.to_str()) != Some("json") {
            continue;
        }
        let Ok(raw) = fs::read_to_string(&path) else {
            continue;
        };
        let Ok(file) = serde_json::from_str::<AutosaveFile>(&raw) else {
            continue;
        };
        out.push(AutosaveInfo {
            id: file.id,
            file_name: file
                .path
                .file_name()
                .map(|s| s.to_string_lossy().into_owned())
                .unwrap_or_default(),
            path: file.path,
            saved_at: file.saved_at,
        });
    }
    out.sort_by_key(|a| std::cmp::Reverse(a.saved_at));
    out
}

pub fn autosave_load(dirs: &TempDirs, id: Uuid) -> Result<(AutosaveFile, PathBuf), AppError> {
    let path = dirs.autosave.join(format!("{id}.json"));
    let raw = fs::read_to_string(&path)?;
    let file = serde_json::from_str::<AutosaveFile>(&raw)?;
    Ok((file, path))
}

pub fn autosave_discard(dirs: &TempDirs, id: Uuid) {
    let _ = fs::remove_file(dirs.autosave.join(format!("{id}.json")));
}

pub fn autosave_discard_doc(dirs: &TempDirs, doc: &Document) {
    autosave_discard(dirs, doc.id);
}

#[cfg(feature = "desktop")]
fn prune_cache(dir: &Path) {
    let Ok(entries) = fs::read_dir(dir) else {
        return;
    };
    let now = SystemTime::now();
    let mut files: Vec<(PathBuf, SystemTime, u64)> = Vec::new();
    let mut total = 0u64;
    for entry in entries.flatten() {
        let path = entry.path();
        let Ok(meta) = entry.metadata() else { continue };
        if !meta.is_file() {
            if meta.is_dir() {
                prune_cache(&path);
            }
            continue;
        }
        let mtime = meta.modified().unwrap_or(now);
        let len = meta.len();
        if now.duration_since(mtime).unwrap_or_default() > CACHE_MAX_AGE {
            let _ = fs::remove_file(&path);
            continue;
        }
        total = total.saturating_add(len);
        files.push((path, mtime, len));
    }
    files.sort_by_key(|(_, mtime, _)| *mtime);
    let mut idx = 0;
    while total > CACHE_MAX_BYTES && idx < files.len() {
        let (path, _, len) = &files[idx];
        if fs::remove_file(path).is_ok() {
            total = total.saturating_sub(*len);
        }
        idx += 1;
    }
}

fn now_secs() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}
