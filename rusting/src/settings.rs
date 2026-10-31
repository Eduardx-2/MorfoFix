use std::fs;
use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::error::AppError;

pub const SCHEMA: u32 = 1;

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(default)]
pub struct Settings {
    pub schema: u32,
    pub last_open_dir: Option<PathBuf>,
    pub last_export_dir: Option<PathBuf>,
    pub export: ExportDefaults,
    pub preview_max_side: u32,
    pub preview_interactive_side: u32,
    pub history_limit: usize,
    pub engine: EngineSettings,
    pub ui: Value,
    pub recents: Vec<RecentItem>,
}

impl Default for Settings {
    fn default() -> Self {
        Self {
            schema: SCHEMA,
            last_open_dir: None,
            last_export_dir: None,
            export: ExportDefaults::default(),
            preview_max_side: 1600,
            preview_interactive_side: 1200,
            history_limit: 100,
            engine: EngineSettings::default(),
            ui: Value::Object(Default::default()),
            recents: Vec::new(),
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(default)]
pub struct ExportDefaults {
    pub format: String,
    pub quality: u8,
    pub keep_metadata: bool,
    pub keep_gps: bool,
}

impl Default for ExportDefaults {
    fn default() -> Self {
        Self {
            format: "jpeg".into(),
            quality: 92,
            keep_metadata: true,
            keep_gps: false,
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(default)]
pub struct EngineSettings {
    pub fixed_port: Option<u16>,
    pub python: Option<PathBuf>,
    pub log_level: String,
}

impl Default for EngineSettings {
    fn default() -> Self {
        Self {
            fixed_port: None,
            python: None,
            log_level: if cfg!(debug_assertions) {
                "debug".into()
            } else {
                "info".into()
            },
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct RecentItem {
    pub path: PathBuf,
    pub file_name: String,
    pub opened_at: u64,
}

impl Settings {
    pub fn load_from(path: &Path) -> Self {
        match fs::read_to_string(path) {
            Ok(raw) => match serde_json::from_str::<Settings>(&raw) {
                Ok(mut settings) => {
                    if settings.schema == 0 {
                        settings.schema = SCHEMA;
                    }
                    settings.recents.retain(|item| item.path.exists());
                    settings.validate_inplace();
                    settings
                }
                Err(_) => {
                    quarantine(path);
                    Settings::default()
                }
            },
            Err(_) => Settings::default(),
        }
    }

    pub fn save_to(&self, path: &Path) -> Result<(), AppError> {
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent)?;
        }
        let json = serde_json::to_vec_pretty(self)?;
        atomic_write(path, &json)
    }

    pub fn merge_patch(&mut self, patch: &Value) -> Result<(), AppError> {
        let Value::Object(map) = patch else {
            return Err(AppError::invalid("el parche de settings debe ser un objeto"));
        };
        let mut current = serde_json::to_value(&*self)?;
        let Value::Object(dst) = &mut current else {
            return Err(AppError::invalid("settings internos inválidos"));
        };
        for (k, v) in map {
            dst.insert(k.clone(), v.clone());
        }
        let mut merged: Settings = serde_json::from_value(current)?;
        merged.validate_inplace();
        *self = merged;
        Ok(())
    }

    fn validate_inplace(&mut self) {
        if self.preview_max_side == 0 {
            self.preview_max_side = 1600;
        }
        if self.preview_interactive_side == 0 {
            self.preview_interactive_side = 1200;
        }
        if self.history_limit == 0 {
            self.history_limit = 100;
        }
        self.export.quality = self.export.quality.clamp(1, 100);
        let format = self.export.format.to_ascii_lowercase();
        if !matches!(format.as_str(), "png" | "jpeg" | "jpg" | "webp" | "tiff") {
            self.export.format = "jpeg".into();
        } else if format == "jpg" {
            self.export.format = "jpeg".into();
        } else {
            self.export.format = format;
        }
        self.recents.truncate(10);
    }

    pub fn push_recent(&mut self, path: PathBuf) {
        let file_name = path
            .file_name()
            .map(|s| s.to_string_lossy().into_owned())
            .unwrap_or_default();
        self.recents.retain(|item| item.path != path);
        self.recents.insert(
            0,
            RecentItem {
                path,
                file_name,
                opened_at: now_secs(),
            },
        );
        self.recents.truncate(10);
    }

    pub fn recents_existing(&self) -> Vec<RecentItem> {
        self.recents
            .iter()
            .filter(|item| item.path.exists())
            .cloned()
            .collect()
    }
}

pub fn atomic_write(path: &Path, data: &[u8]) -> Result<(), AppError> {
    let tmp_name = format!(
        "{}.tmp",
        path.file_name().and_then(|s| s.to_str()).unwrap_or("file")
    );
    let tmp = path.with_file_name(tmp_name);
    fs::write(&tmp, data)?;
    fs::rename(&tmp, path)?;
    Ok(())
}

fn quarantine(path: &Path) {
    let stamp = now_secs();
    let bad = path.with_file_name(format!("settings.bad-{stamp}.json"));
    let _ = fs::rename(path, bad);
}

fn now_secs() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[test]
    fn corrupt_settings_quarantined() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("settings.json");
        fs::write(&path, "{nope").unwrap();
        let settings = Settings::load_from(&path);
        assert_eq!(settings.preview_max_side, 1600);
        assert!(!path.exists());
        let bad: Vec<_> = fs::read_dir(dir.path())
            .unwrap()
            .filter_map(|e| e.ok())
            .map(|e| e.file_name().to_string_lossy().into_owned())
            .collect();
        assert!(bad.iter().any(|n| n.starts_with("settings.bad-")));
    }

    #[test]
    fn recents_dedup_and_cap() {
        let mut s = Settings::default();
        for i in 0..12 {
            s.push_recent(PathBuf::from(format!("/tmp/f{i}.jpg")));
        }
        s.push_recent(PathBuf::from("/tmp/f11.jpg"));
        assert_eq!(s.recents.len(), 10);
        assert_eq!(s.recents[0].path, PathBuf::from("/tmp/f11.jpg"));
    }
}
