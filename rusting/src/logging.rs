#[cfg(feature = "desktop")]
use tauri::plugin::TauriPlugin;
#[cfg(feature = "desktop")]
use tauri_plugin_log::{RotationStrategy, Target, TargetKind};

#[cfg(feature = "desktop")]
pub fn plugin() -> TauriPlugin<tauri::Wry> {
    let level = if cfg!(debug_assertions) {
        log::LevelFilter::Debug
    } else {
        log::LevelFilter::Info
    };
    tauri_plugin_log::Builder::new()
        .level(level)
        .rotation_strategy(RotationStrategy::KeepSome(7))
        .max_file_size(5 * 1024 * 1024)
        .targets([
            Target::new(TargetKind::LogDir {
                file_name: Some("morfofix".into()),
            }),
            Target::new(TargetKind::Stdout),
            Target::new(TargetKind::Webview),
        ])
        .build()
}

pub fn redact(line: &str, token: &str) -> String {
    if token.is_empty() {
        return line.to_string();
    }
    line.replace(token, "<redacted>")
}

pub fn log_engine_stderr(line: &str, token: &str) {
    let line = redact(line.trim(), token);
    if line.is_empty() {
        return;
    }
    let level = serde_json::from_str::<serde_json::Value>(&line)
        .ok()
        .and_then(|v| {
            v.get("level")
                .and_then(|l| l.as_str())
                .map(|s| s.to_ascii_lowercase())
        })
        .unwrap_or_default();
    match level.as_str() {
        "error" | "err" => log::error!(target: "engine", "{line}"),
        "warn" | "warning" => log::warn!(target: "engine", "{line}"),
        "debug" => log::debug!(target: "engine", "{line}"),
        "trace" => log::trace!(target: "engine", "{line}"),
        _ => log::info!(target: "engine", "{line}"),
    }
}

pub fn file_name_only(path: &std::path::Path) -> String {
    path.file_name()
        .map(|s| s.to_string_lossy().into_owned())
        .unwrap_or_else(|| "archivo".into())
}
