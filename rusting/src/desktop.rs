use std::sync::atomic::Ordering;

use tauri::{DragDropEvent, Manager, RunEvent, WindowEvent};

use crate::engine::EngineConfig;
use crate::state::AppState;
use crate::{cmds, engine, logging, menu, settings, temp};

pub fn run() {
    let builder = tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .plugin(logging::plugin())
        .setup(|app| {
            let handle = app.handle().clone();
            let dirs = temp::temp_init(&handle)?;
            engine::kill_stale_pid(&dirs.data.join("engine.pid"));
            let settings_path = dirs.config.join("settings.json");
            let loaded = settings::Settings::load_from(&settings_path);
            let recents = loaded.recents_existing();
            let cfg = EngineConfig::from_app(&handle, &loaded, &dirs)?;
            let offers = temp::autosave_find(&dirs);
            app.manage(AppState::new(cfg, loaded, dirs, settings_path));
            let built = menu::build_menu(&handle, &recents, menu::MenuFlags::default())?;
            app.set_menu(built)?;
            if !offers.is_empty() {
                let _ = tauri::Emitter::emit(&handle, "autosave://offer", &offers);
            }
            tauri::async_runtime::spawn(cmds::engine::start_engine(handle));
            Ok(())
        })
        .on_menu_event(|app, ev| menu::on_menu_event(app, ev))
        .on_window_event(|window, event| match event {
            WindowEvent::CloseRequested { api, .. } => {
                api.prevent_close();
                let app = window.app_handle().clone();
                tauri::async_runtime::spawn(async move {
                    cmds::app::request_quit(&app).await;
                });
            }
            WindowEvent::Destroyed => {
                let app = window.app_handle().clone();
                tauri::async_runtime::spawn(async move {
                    let state = app.state::<AppState>();
                    if !state.shutting_down.load(Ordering::SeqCst) {
                        state.engine.lock().await.shutdown().await;
                    }
                });
            }
            WindowEvent::DragDrop(DragDropEvent::Drop { paths, .. }) => {
                let app = window.app_handle().clone();
                let paths = paths.clone();
                tauri::async_runtime::spawn(async move {
                    cmds::files::handle_drop(&app, paths).await;
                });
            }
            _ => {}
        })
        .invoke_handler(tauri::generate_handler![
            cmds::engine::engine_status,
            cmds::engine::engine_restart,
            cmds::engine::engine_catalog,
            cmds::files::open_image_dialog,
            cmds::files::doc_open,
            cmds::files::doc_detect,
            cmds::files::doc_current,
            cmds::files::export_dialog,
            cmds::files::doc_export,
            cmds::files::recents_list,
            cmds::files::recents_clear,
            cmds::settings::settings_get,
            cmds::settings::settings_set,
            cmds::settings::autosave_list,
            cmds::settings::autosave_restore,
            cmds::settings::autosave_discard,
            cmds::edit::edit_preview,
            cmds::edit::doc_preview,
            cmds::edit::edit_commit,
            cmds::edit::edit_set_param,
            cmds::edit::history_undo,
            cmds::edit::history_redo,
            cmds::app::open_logs_dir,
            cmds::app::about_info,
        ]);

    builder
        .build(tauri::generate_context!())
        .expect("error al construir MorfoFix")
        .run(|app, event| {
            if let RunEvent::ExitRequested { api, .. } = event {
                let state = app.state::<AppState>();
                if !state.shutting_down.load(Ordering::SeqCst) {
                    api.prevent_exit();
                    let app = app.clone();
                    tauri::async_runtime::spawn(async move {
                        cmds::app::request_quit(&app).await;
                    });
                }
            }
        });
}
