use std::collections::VecDeque;
use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, AtomicU32, AtomicU64};
use std::sync::Mutex as StdMutex;
use std::time::Instant;

use tokio::sync::{Mutex, RwLock};

use crate::doc::edit_state::{Catalog, CatalogItem};
use crate::doc::Document;
use crate::engine::scheduler::PreviewScheduler;
use crate::engine::{EngineConfig, EngineManager};
use crate::settings::Settings;
use crate::temp::TempDirs;

pub struct AppState {
    pub engine: Mutex<EngineManager>,
    pub doc: Mutex<Option<Document>>,
    pub settings: StdMutex<Settings>,
    pub settings_path: PathBuf,
    pub scheduler: PreviewScheduler,
    pub catalog: RwLock<Catalog>,
    pub dirs: TempDirs,
    pub export_in_flight: AtomicBool,
    pub shutting_down: AtomicBool,
    pub health_failures: AtomicU32,
    pub autosave_gen: AtomicU64,
    pub render_started: Mutex<Option<Instant>>,
    pub interactive_ms: Mutex<VecDeque<f64>>,
}

impl AppState {
    pub fn new(cfg: EngineConfig, settings: Settings, dirs: TempDirs, settings_path: PathBuf) -> Self {
        Self {
            engine: Mutex::new(EngineManager::new(cfg)),
            doc: Mutex::new(None),
            settings: StdMutex::new(settings),
            settings_path,
            scheduler: PreviewScheduler::new(),
            catalog: RwLock::new(Catalog::default()),
            dirs,
            export_in_flight: AtomicBool::new(false),
            shutting_down: AtomicBool::new(false),
            health_failures: AtomicU32::new(0),
            autosave_gen: AtomicU64::new(0),
            render_started: Mutex::new(None),
            interactive_ms: Mutex::new(VecDeque::new()),
        }
    }

    pub fn persist_settings(&self) {
        if let Ok(settings) = self.settings.lock() {
            if let Err(err) = settings.save_to(&self.settings_path) {
                log::warn!("no se pudo guardar settings: {err}");
            }
        }
    }

    pub async fn set_catalog(&self, items: Vec<CatalogItem>) {
        *self.catalog.write().await = Catalog::from_items(items);
    }
}
