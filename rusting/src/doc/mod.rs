pub mod edit_state;
pub mod history;

use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};
use uuid::Uuid;

use crate::engine::client::SessionInfo;
use crate::settings::Settings;

use self::edit_state::EditState;
use self::history::{History, HistoryInfo, DEFAULT_MAX_BYTES};

#[derive(Debug)]
pub struct Document {
    pub id: Uuid,
    pub path: PathBuf,
    pub session_id: String,
    pub info: SessionInfo,
    pub committed: EditState,
    pub working: EditState,
    pub history: History,
    pub dirty: bool,
    pub rev: u64,
    pub face_indices: Vec<u32>,
    pub body_indices: Vec<u32>,
    pub last_faces: Vec<serde_json::Value>,
    pub last_bodies: Vec<serde_json::Value>,
    pub overlay: Option<String>,
}

impl Document {
    pub fn open(path: PathBuf, session: SessionInfo, settings: &Settings) -> Self {
        let state = EditState::new();
        Self {
            id: Uuid::new_v4(),
            path,
            session_id: session.session_id.clone(),
            info: session,
            committed: state.clone(),
            working: state,
            history: History::new(settings.history_limit, DEFAULT_MAX_BYTES),
            dirty: false,
            rev: 0,
            face_indices: Vec::new(),
            body_indices: Vec::new(),
            last_faces: Vec::new(),
            last_bodies: Vec::new(),
            overlay: None,
        }
    }

    pub fn apply_detect(&mut self, resp: crate::engine::client::DetectResp, what: &[String]) {
        if what.iter().any(|w| w == "face") {
            self.last_faces = resp.faces.clone();
            self.face_indices = json_indices(&resp.faces);
        }
        if what.iter().any(|w| w == "pose") {
            self.last_bodies = resp.bodies.clone();
            self.body_indices = json_indices(&resp.bodies);
        }
    }

    pub fn file_name(&self) -> String {
        self.path
            .file_name()
            .map(|s| s.to_string_lossy().into_owned())
            .unwrap_or_else(|| self.path.display().to_string())
    }

    pub fn file_size(&self) -> u64 {
        std::fs::metadata(&self.path).map(|m| m.len()).unwrap_or(0)
    }

    pub fn next_rev(&mut self) -> u64 {
        self.rev = self.rev.saturating_add(1);
        self.rev
    }

    pub fn history_info(&self) -> HistoryInfo {
        self.history.info(self.committed.clone())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct DocInfo {
    pub session_id: String,
    pub width: u32,
    pub height: u32,
    pub preview_width: u32,
    pub preview_height: u32,
    pub orientation_applied: i32,
    pub format: String,
    pub has_alpha: bool,
    pub icc: bool,
    pub image_sha1: String,
    pub warnings: Vec<String>,
    pub path: PathBuf,
    pub file_name: String,
    pub file_size: u64,
    pub dirty: bool,
    pub id: Uuid,
    #[serde(default)]
    pub faces: Vec<serde_json::Value>,
    #[serde(default)]
    pub bodies: Vec<serde_json::Value>,
}

impl DocInfo {
    pub fn from_doc(doc: &Document) -> Self {
        Self {
            session_id: doc.session_id.clone(),
            width: doc.info.width,
            height: doc.info.height,
            preview_width: doc.info.preview_width,
            preview_height: doc.info.preview_height,
            orientation_applied: doc.info.orientation_applied,
            format: doc.info.format.clone(),
            has_alpha: doc.info.has_alpha,
            icc: doc.info.icc,
            image_sha1: doc.info.image_sha1.clone(),
            warnings: doc.info.warnings.clone(),
            path: doc.path.clone(),
            file_name: doc.file_name(),
            file_size: doc.file_size(),
            dirty: doc.dirty,
            id: doc.id,
            faces: doc.last_faces.clone(),
            bodies: doc.last_bodies.clone(),
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct DocSnapshot {
    pub info: DocInfo,
    pub state: EditState,
    pub history: HistoryInfo,
}

fn json_indices(values: &[serde_json::Value]) -> Vec<u32> {
    values
        .iter()
        .enumerate()
        .map(|(i, value)| {
            value
                .get("index")
                .and_then(|v| v.as_u64())
                .unwrap_or(i as u64) as u32
        })
        .collect()
}

pub fn is_supported_image(path: &Path) -> bool {
    matches!(
        path.extension()
            .and_then(|e| e.to_str())
            .map(|e| e.to_ascii_lowercase())
            .as_deref(),
        Some("jpg" | "jpeg" | "png" | "webp" | "tif" | "tiff")
    )
}
