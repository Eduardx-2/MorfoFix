use tauri::menu::{IsMenuItem, Menu, MenuEvent, MenuItem, PredefinedMenuItem, Submenu};
use tauri::{AppHandle, Emitter, Manager, Runtime, Wry};

use crate::settings::RecentItem;
use crate::state::AppState;

#[derive(Clone, Copy, Debug, Default)]
pub struct MenuFlags {
    pub has_doc: bool,
    pub can_undo: bool,
    pub can_redo: bool,
}

pub fn build_menu(app: &AppHandle, recents: &[RecentItem], flags: MenuFlags) -> tauri::Result<Menu<Wry>> {
    let open = MenuItem::with_id(app, "file-open", "Abrir…", true, Some("CmdOrCtrl+O"))?;
    let export = MenuItem::with_id(app, "file-export", "Exportar…", flags.has_doc, Some("CmdOrCtrl+S"))?;
    let export2 = MenuItem::with_id(app, "file-export-alt", "Exportar…", flags.has_doc, Some("CmdOrCtrl+E"))?;
    let close = MenuItem::with_id(app, "file-close", "Cerrar foto", flags.has_doc, Some("CmdOrCtrl+W"))?;
    let quit = MenuItem::with_id(app, "file-quit", "Salir", true, Some("CmdOrCtrl+Q"))?;
    let recents_sub = recents_submenu(app, recents)?;
    let sep1 = PredefinedMenuItem::separator(app)?;
    let sep2 = PredefinedMenuItem::separator(app)?;
    let file_items: Vec<&dyn IsMenuItem<Wry>> = vec![
        &open, &recents_sub, &sep1, &export, &export2, &close, &sep2, &quit,
    ];
    let file = Submenu::with_items(app, "Archivo", true, &file_items)?;

    let undo = MenuItem::with_id(app, "edit-undo", "Deshacer", flags.can_undo, Some("CmdOrCtrl+Z"))?;
    let redo = MenuItem::with_id(app, "edit-redo", "Rehacer", flags.can_redo, Some("CmdOrCtrl+Y"))?;
    let redo2 = MenuItem::with_id(app, "edit-redo-alt", "Rehacer", flags.can_redo, Some("CmdOrCtrl+Shift+Z"))?;
    let reset = MenuItem::with_id(app, "edit-reset", "Restablecer todo", flags.has_doc, None::<&str>)?;
    let sep_edit = PredefinedMenuItem::separator(app)?;
    let edit_items: Vec<&dyn IsMenuItem<Wry>> = vec![&undo, &redo, &redo2, &sep_edit, &reset];
    let edit = Submenu::with_items(app, "Editar", true, &edit_items)?;

    let compare = MenuItem::with_id(app, "view-compare", "Antes / Después", flags.has_doc, None::<&str>)?;
    let zoom_in = MenuItem::with_id(app, "view-zoom-in", "Acercar", flags.has_doc, Some("CmdOrCtrl+="))?;
    let zoom_out = MenuItem::with_id(app, "view-zoom-out", "Alejar", flags.has_doc, Some("CmdOrCtrl+-"))?;
    let zoom_fit = MenuItem::with_id(app, "view-zoom-fit", "Ajustar", flags.has_doc, Some("CmdOrCtrl+0"))?;
    let landmarks = MenuItem::with_id(app, "view-landmarks", "Puntos de referencia", flags.has_doc, None::<&str>)?;
    let sep_view1 = PredefinedMenuItem::separator(app)?;
    let sep_view2 = PredefinedMenuItem::separator(app)?;
    let view_items: Vec<&dyn IsMenuItem<Wry>> =
        vec![&compare, &sep_view1, &zoom_in, &zoom_out, &zoom_fit, &sep_view2, &landmarks];
    let view = Submenu::with_items(app, "Ver", true, &view_items)?;

    let about = MenuItem::with_id(app, "help-about", "Acerca de MorfoFix", true, None::<&str>)?;
    let licenses = MenuItem::with_id(app, "help-licenses", "Licencias de modelos", true, None::<&str>)?;
    let logs = MenuItem::with_id(app, "help-logs", "Abrir carpeta de logs", true, None::<&str>)?;
    let help_items: Vec<&dyn IsMenuItem<Wry>> = vec![&about, &licenses, &logs];
    let help = Submenu::with_items(app, "Ayuda", true, &help_items)?;
    let top: Vec<&dyn IsMenuItem<Wry>> = vec![&file, &edit, &view, &help];
    Menu::with_items(app, &top)
}

fn recents_submenu(app: &AppHandle, recents: &[RecentItem]) -> tauri::Result<Submenu<Wry>> {
    if recents.is_empty() {
        let empty = MenuItem::with_id(app, "file-recent-empty", "(vacío)", false, None::<&str>)?;
        return Submenu::with_items(app, "Recientes", true, &[&empty]);
    }
    let mut items: Vec<MenuItem<Wry>> = Vec::new();
    for (i, item) in recents.iter().take(10).enumerate() {
        items.push(MenuItem::with_id(
            app,
            format!("file-recent-{i}"),
            &item.file_name,
            true,
            None::<&str>,
        )?);
    }
    let refs: Vec<&dyn IsMenuItem<Wry>> = items.iter().map(|i| i as _).collect();
    Submenu::with_items(app, "Recientes", true, &refs)
}

pub fn refresh_menu(app: &AppHandle) {
    let state = app.state::<AppState>();
    let recents = state
        .settings
        .lock()
        .map(|s| s.recents_existing())
        .unwrap_or_default();
    let flags = current_flags(&state);
    if let Ok(menu) = build_menu(app, &recents, flags) {
        let _ = app.set_menu(menu);
    }
}

pub fn current_flags(state: &AppState) -> MenuFlags {
    let Ok(doc) = state.doc.try_lock() else {
        return MenuFlags::default();
    };
    match doc.as_ref() {
        Some(doc) => MenuFlags {
            has_doc: true,
            can_undo: doc.history.can_undo(),
            can_redo: doc.history.can_redo(),
        },
        None => MenuFlags::default(),
    }
}

pub fn on_menu_event(app: &AppHandle, ev: MenuEvent) {
    let id = ev.id().as_ref().to_string();
    let handle = app.clone();
    tauri::async_runtime::spawn(async move {
        match id.as_str() {
            "file-open" => crate::cmds::files::menu_open(&handle).await,
            "file-export" | "file-export-alt" => crate::cmds::files::menu_export(&handle).await,
            "file-close" => crate::cmds::files::menu_close(&handle).await,
            "file-quit" => crate::cmds::app::request_quit(&handle).await,
            "edit-undo" => {
                let _ = crate::cmds::edit::history_undo(handle.clone(), handle.state()).await;
            }
            "edit-redo" | "edit-redo-alt" => {
                let _ = crate::cmds::edit::history_redo(handle.clone(), handle.state()).await;
            }
            "edit-reset" => crate::cmds::edit::reset_all(&handle).await,
            "view-compare" => {
                let _ = handle.emit("menu://compare", ());
            }
            "view-zoom-in" => {
                let _ = handle.emit("menu://zoom", "in");
            }
            "view-zoom-out" => {
                let _ = handle.emit("menu://zoom", "out");
            }
            "view-zoom-fit" => {
                let _ = handle.emit("menu://zoom", "fit");
            }
            "view-landmarks" => {
                let _ = handle.emit("menu://landmarks", ());
            }
            "help-about" => crate::cmds::app::show_about(&handle).await,
            "help-licenses" => crate::cmds::app::open_licenses(&handle),
            "help-logs" => {
                let _ = crate::cmds::app::open_logs_dir(handle.clone(), handle.state());
            }
            other if other.starts_with("file-recent-") => {
                if let Ok(idx) = other.trim_start_matches("file-recent-").parse::<usize>() {
                    crate::cmds::files::open_recent(&handle, idx).await;
                }
            }
            _ => {}
        }
        refresh_menu(&handle);
    });
}

pub fn apply_flags<R: Runtime>(app: &AppHandle<R>, flags: MenuFlags) {
    if let Some(menu) = app.menu() {
        for (id, enabled) in [
            ("file-export", flags.has_doc),
            ("file-export-alt", flags.has_doc),
            ("file-close", flags.has_doc),
            ("edit-undo", flags.can_undo),
            ("edit-redo", flags.can_redo),
            ("edit-redo-alt", flags.can_redo),
            ("edit-reset", flags.has_doc),
            ("view-compare", flags.has_doc),
            ("view-zoom-in", flags.has_doc),
            ("view-zoom-out", flags.has_doc),
            ("view-zoom-fit", flags.has_doc),
            ("view-landmarks", flags.has_doc),
        ] {
            if let Some(item) = menu.get(id) {
                if let Some(mi) = item.as_menuitem() {
                    let _ = mi.set_enabled(enabled);
                }
            }
        }
    }
}
