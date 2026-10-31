pub mod client;
pub mod ready;
pub mod scheduler;

use std::collections::{BTreeMap, VecDeque};
use std::path::{Path, PathBuf};
use std::process::Stdio;
use std::time::{Duration, Instant};

use serde::Serialize;
#[cfg(feature = "desktop")]
use tauri::{AppHandle, Emitter, Manager};
use tokio::io::{AsyncBufReadExt, BufReader};
use tokio::process::{Child, ChildStdout, Command};
use tokio::task::JoinHandle;

use self::client::{EngineClient, Health};
use self::ready::{parse_ready_line, ReadyInfo, ReadyParseError};
use crate::error::AppError;
use crate::logging::{log_engine_stderr, redact};
#[cfg(feature = "desktop")]
use crate::settings::Settings;
#[cfg(feature = "desktop")]
use crate::temp::TempDirs;

#[cfg(feature = "desktop")]
const READY_TIMEOUT: Duration = Duration::from_secs(20);
#[cfg(feature = "desktop")]
const HEALTH_EVERY: Duration = Duration::from_secs(5);
const MAX_RESTARTS: usize = 5;
const RESTART_WINDOW: Duration = Duration::from_secs(5 * 60);

#[derive(Clone, Debug)]
pub enum EngineState {
    Starting,
    Ready { port: u16, pid: u32, version: String },
    Restarting { attempt: u32 },
    Down { reason: String },
}

impl EngineState {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Starting => "starting",
            Self::Ready { .. } => "ready",
            Self::Restarting { .. } => "restarting",
            Self::Down { .. } => "down",
        }
    }
}

#[derive(Clone, Debug, Serialize)]
pub struct EngineStatusDto {
    pub state: String,
    pub version: Option<String>,
    pub models: BTreeMap<String, String>,
    pub reason: Option<String>,
}

#[derive(Clone, Debug)]
pub struct EngineConfig {
    pub program: PathBuf,
    pub args: Vec<String>,
    pub models_dir: PathBuf,
    pub cache_dir: PathBuf,
    pub ready_timeout: Duration,
    pub log_level: String,
    pub fixed_port: Option<u16>,
    pub pid_file: PathBuf,
    pub cwd: PathBuf,
}

impl EngineConfig {
    #[cfg(feature = "desktop")]
    pub fn from_app(app: &AppHandle, settings: &Settings, dirs: &TempDirs) -> Result<Self, AppError> {
        let engine_dir = engine_src_dir();
        let (program, args, models_dir, cwd) = if cfg!(debug_assertions) {
            let python = settings
                .engine
                .python
                .clone()
                .or_else(|| std::env::var_os("MORFOFIX_PYTHON").map(PathBuf::from))
                .unwrap_or_else(default_python);
            (
                python,
                vec!["-m".into(), "morfofix_engine".into()],
                engine_dir.join("models"),
                engine_dir.clone(),
            )
        } else {
            let resource = app.path().resource_dir().map_err(AppError::io)?;
            let exe = if cfg!(windows) {
                resource.join("engine/morfofix-engine.exe")
            } else {
                resource.join("engine/morfofix-engine")
            };
            (
                exe,
                Vec::new(),
                resource.join("engine/models"),
                resource.join("engine"),
            )
        };
        Ok(Self {
            program,
            args,
            models_dir,
            cache_dir: dirs.engine_cache.clone(),
            ready_timeout: READY_TIMEOUT,
            log_level: settings.engine.log_level.clone(),
            fixed_port: settings.engine.fixed_port,
            pid_file: dirs.data.join("engine.pid"),
            cwd,
        })
    }
}

pub struct EngineManager {
    child: Option<Child>,
    stdin: Option<tokio::process::ChildStdin>,
    token: String,
    state: EngineState,
    restarts: VecDeque<Instant>,
    cfg: EngineConfig,
    drain: Vec<JoinHandle<()>>,
    intended_shutdown: bool,
    models: BTreeMap<String, String>,
}

impl EngineManager {
    pub fn new(cfg: EngineConfig) -> Self {
        Self {
            child: None,
            stdin: None,
            token: String::new(),
            state: EngineState::Down {
                reason: "sin arrancar".into(),
            },
            restarts: VecDeque::new(),
            cfg,
            drain: Vec::new(),
            intended_shutdown: false,
            models: BTreeMap::new(),
        }
    }

    pub fn state(&self) -> &EngineState {
        &self.state
    }

    pub fn status_dto(&self) -> EngineStatusDto {
        match &self.state {
            EngineState::Ready { version, .. } => EngineStatusDto {
                state: "ready".into(),
                version: Some(version.clone()),
                models: self.models.clone(),
                reason: None,
            },
            EngineState::Starting => EngineStatusDto {
                state: "starting".into(),
                version: None,
                models: self.models.clone(),
                reason: None,
            },
            EngineState::Restarting { attempt } => EngineStatusDto {
                state: "restarting".into(),
                version: None,
                models: self.models.clone(),
                reason: Some(format!("intento {attempt}")),
            },
            EngineState::Down { reason } => EngineStatusDto {
                state: "down".into(),
                version: None,
                models: self.models.clone(),
                reason: Some(reason.clone()),
            },
        }
    }

    pub fn base_url(&self) -> Option<String> {
        match self.state {
            EngineState::Ready { port, .. } => Some(format!("http://127.0.0.1:{port}")),
            _ => None,
        }
    }

    pub fn token(&self) -> &str {
        &self.token
    }

    pub fn client(&self) -> Result<EngineClient, AppError> {
        match self.state {
            EngineState::Ready { port, .. } => EngineClient::new(port, &self.token),
            _ => Err(AppError::engine_down("motor no listo")),
        }
    }

    pub fn set_models(&mut self, health: &Health) {
        self.models = health
            .models
            .iter()
            .map(|(k, v)| {
                (
                    k.clone(),
                    v.as_str().unwrap_or(&v.to_string()).to_string(),
                )
            })
            .collect();
    }

    pub fn reset_restart_window(&mut self) {
        self.restarts.clear();
    }

    pub fn is_intended_shutdown(&self) -> bool {
        self.intended_shutdown
    }

    #[cfg(feature = "desktop")]
    pub async fn start(&mut self, app: &AppHandle) -> Result<(), AppError> {
        self.start_with(|dto| {
            let _ = app.emit("engine://state", dto);
        })
        .await
    }

    pub async fn start_with<F>(&mut self, emit: F) -> Result<(), AppError>
    where
        F: Fn(EngineStatusDto),
    {
        if self.child.is_some() {
            if matches!(self.state, EngineState::Ready { .. }) {
                return Err(AppError::invalid("el motor ya está en ejecución"));
            }
            self.shutdown().await;
        }
        self.intended_shutdown = false;
        self.state = EngineState::Starting;
        emit(self.status_dto());
        let token = new_token();
        self.token = token.clone();
        let port = self
            .cfg
            .fixed_port
            .map(|p| p.to_string())
            .unwrap_or_else(|| "0".into());
        let mut cmd = Command::new(&self.cfg.program);
        cmd.args(&self.cfg.args)
            .arg("--host")
            .arg("127.0.0.1")
            .arg("--port")
            .arg(&port)
            .arg("--token-env")
            .arg("MORFOFIX_TOKEN")
            .arg("--models-dir")
            .arg(&self.cfg.models_dir)
            .arg("--cache-dir")
            .arg(&self.cfg.cache_dir)
            .arg("--log-level")
            .arg(&self.cfg.log_level)
            .env("MORFOFIX_TOKEN", &token)
            .env("PYTHONUNBUFFERED", "1")
            .current_dir(&self.cfg.cwd)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .kill_on_drop(true);
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            cmd.creation_flags(0x0800_0000);
        }
        log::info!(
            target: "engine",
            "spawn {}",
            self.cfg.program.file_name().and_then(|s| s.to_str()).unwrap_or("engine")
        );
        let mut child = match cmd.spawn() {
            Ok(child) => child,
            Err(err) => {
                self.state = EngineState::Down {
                    reason: format!("no se pudo lanzar el motor: {err}"),
                };
                emit(self.status_dto());
                return Err(AppError::io(err));
            }
        };
        self.stdin = child.stdin.take();
        let stdout = child.stdout.take().ok_or_else(|| AppError::invalid("stdout del motor ausente"))?;
        let stderr = child.stderr.take();
        self.child = Some(child);
        if let Some(stderr) = stderr {
            let token = token.clone();
            self.drain.push(tokio::spawn(async move {
                let mut lines = BufReader::new(stderr).lines();
                while let Ok(Some(line)) = lines.next_line().await {
                    log_engine_stderr(&line, &token);
                }
            }));
        }
        match self.wait_ready(stdout).await {
            Ok(info) => {
                self.state = EngineState::Ready {
                    port: info.port,
                    pid: info.pid,
                    version: info.version,
                };
                if let Err(err) = std::fs::write(&self.cfg.pid_file, info.pid.to_string()) {
                    log::warn!(target: "engine", "no se pudo escribir pid: {err}");
                }
                emit(self.status_dto());
                Ok(())
            }
            Err(err) => {
                self.shutdown().await;
                self.state = EngineState::Down {
                    reason: err.to_string(),
                };
                emit(self.status_dto());
                Err(err)
            }
        }
    }

    pub async fn wait_ready(&mut self, stdout: ChildStdout) -> Result<ReadyInfo, AppError> {
        let timeout = self.cfg.ready_timeout;
        let token = self.token.clone();
        let (tx, rx) = tokio::sync::oneshot::channel();
        let handle = tokio::spawn(async move {
            let mut lines = BufReader::new(stdout).lines();
            let read = async {
                loop {
                    match lines.next_line().await {
                        Ok(Some(line)) => match parse_ready_line(&line) {
                            Ok(info) => return Ok((info, lines)),
                            Err(ReadyParseError::NotReady) => {
                                let safe = redact(&line, &token);
                                if !safe.is_empty() {
                                    log::info!(target: "engine.stdout", "{safe}");
                                }
                            }
                            Err(err) => return Err(AppError::from(err)),
                        },
                        Ok(None) => {
                            return Err(AppError::engine_down("el motor cerró stdout antes de READY"));
                        }
                        Err(err) => return Err(AppError::io(err)),
                    }
                }
            };
            match tokio::time::timeout(timeout, read).await {
                Ok(Ok((info, mut rest))) => {
                    let _ = tx.send(Ok(info));
                    while let Ok(Some(line)) = rest.next_line().await {
                        let safe = redact(&line, &token);
                        if !safe.is_empty() {
                            log::info!(target: "engine.stdout", "{safe}");
                        }
                    }
                }
                Ok(Err(err)) => {
                    let _ = tx.send(Err(err));
                }
                Err(_) => {
                    let _ = tx.send(Err(AppError::engine_down(format!(
                        "timeout de {timeout:?} esperando READY"
                    ))));
                }
            }
        });
        self.drain.push(handle);
        rx.await.unwrap_or_else(|_| Err(AppError::engine_down("lector READY cancelado")))
    }

    pub async fn health(&self) -> Result<Health, AppError> {
        self.client()?.health().await
    }

    #[cfg(feature = "desktop")]
    pub async fn restart(&mut self, app: &AppHandle) -> Result<(), AppError> {
        self.prune_restarts();
        if self.restarts.len() >= MAX_RESTARTS {
            self.state = EngineState::Down {
                reason: "El motor local no responde".into(),
            };
            let _ = app.emit("engine://state", self.status_dto());
            let _ = app.emit(
                "app://toast",
                serde_json::json!({
                    "message": "El motor local no responde",
                    "action": "retry"
                }),
            );
            return Err(AppError::engine_down("El motor local no responde"));
        }
        let attempt = self.restarts.len() as u32 + 1;
        self.state = EngineState::Restarting { attempt };
        let _ = app.emit("engine://state", self.status_dto());
        let backoff = Duration::from_millis(500 * (1u64 << (attempt.saturating_sub(1).min(4))));
        tokio::time::sleep(backoff).await;
        self.restarts.push_back(Instant::now());
        self.start(app).await
    }

    pub fn can_auto_restart(&self) -> bool {
        self.restarts.iter().filter(|t| t.elapsed() < RESTART_WINDOW).count() < MAX_RESTARTS
            && !self.intended_shutdown
    }

    pub async fn shutdown(&mut self) {
        self.intended_shutdown = true;
        if let Ok(client) = self.client() {
            let _ = tokio::time::timeout(Duration::from_secs(1), client.shutdown()).await;
        }
        if let Some(mut child) = self.child.take() {
            let waited = tokio::time::timeout(Duration::from_millis(1500), child.wait()).await;
            if waited.is_err() {
                if let Err(err) = child.kill().await {
                    log::warn!(target: "engine", "kill falló: {err}");
                }
                let _ = child.wait().await;
            }
        }
        self.stdin.take();
        for task in self.drain.drain(..) {
            task.abort();
        }
        let _ = std::fs::remove_file(&self.cfg.pid_file);
        if !matches!(self.state, EngineState::Down { .. }) {
            self.state = EngineState::Down {
                reason: "apagado".into(),
            };
        }
        self.token.clear();
    }

    pub fn try_reap(&mut self) -> bool {
        if self.intended_shutdown {
            return false;
        }
        if let Some(child) = self.child.as_mut() {
            match child.try_wait() {
                Ok(Some(status)) => {
                    self.child = None;
                    self.stdin.take();
                    self.state = EngineState::Down {
                        reason: format!("el motor salió ({status})"),
                    };
                    true
                }
                _ => false,
            }
        } else {
            false
        }
    }

    #[cfg(feature = "desktop")]
    fn prune_restarts(&mut self) {
        self.restarts.retain(|t| t.elapsed() < RESTART_WINDOW);
    }
}

pub fn new_token() -> String {
    let mut b = [0u8; 32];
    getrandom::getrandom(&mut b).expect("os rng");
    hex::encode(b)
}

#[cfg(feature = "desktop")]
pub fn engine_src_dir() -> PathBuf {
    if let Some(p) = std::env::var_os("MORFOFIX_ENGINE_DIR") {
        return PathBuf::from(p);
    }
    let manifest = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let mofix = manifest.join("../mofixPy");
    if mofix.join("morfofix_engine").exists() {
        mofix
    } else {
        manifest.join("../engine")
    }
}

#[cfg(feature = "desktop")]
fn default_python() -> PathBuf {
    let root = engine_src_dir();
    if cfg!(windows) {
        root.join(".venv/Scripts/python.exe")
    } else {
        root.join(".venv/bin/python")
    }
}

pub fn kill_stale_pid(pid_file: &Path) {
    let Ok(raw) = std::fs::read_to_string(pid_file) else {
        return;
    };
    let Ok(pid) = raw.trim().parse::<u32>() else {
        let _ = std::fs::remove_file(pid_file);
        return;
    };
    if is_our_engine(pid) {
        log::warn!(target: "engine", "matando motor huérfano pid={pid}");
        #[cfg(unix)]
        libc_kill(pid);
        #[cfg(not(unix))]
        {
            let _ = std::process::Command::new("taskkill")
                .args(["/PID", &pid.to_string(), "/F"])
                .status();
        }
    }
    let _ = std::fs::remove_file(pid_file);
}

fn is_our_engine(pid: u32) -> bool {
    #[cfg(unix)]
    {
        let comm = std::fs::read_to_string(format!("/proc/{pid}/comm")).unwrap_or_default();
        let cmd = std::fs::read_to_string(format!("/proc/{pid}/cmdline")).unwrap_or_default();
        let name = comm.trim();
        name.contains("morfofix-engine")
            || name.contains("morfofix_engine")
            || ((name == "python" || name.starts_with("python"))
                && (cmd.contains("morfofix_engine") || cmd.contains("morfofix-engine")))
    }
    #[cfg(not(unix))]
    {
        let _ = pid;
        false
    }
}

#[cfg(unix)]
fn libc_kill(pid: u32) {
    unsafe {
        libc::kill(pid as i32, libc::SIGTERM);
    }
}

#[cfg(feature = "desktop")]
pub async fn health_loop(app: AppHandle) {
    loop {
        tokio::time::sleep(HEALTH_EVERY).await;
        let state = app.state::<crate::state::AppState>();
        if state.shutting_down.load(std::sync::atomic::Ordering::SeqCst) {
            break;
        }
        if state.export_in_flight.load(std::sync::atomic::Ordering::SeqCst) {
            continue;
        }
        if let Some(started) = *state.render_started.lock().await {
            if started.elapsed() > Duration::from_secs(5) {
                continue;
            }
        }
        let mut engine = state.engine.lock().await;
        if engine.try_reap() {
            let _ = app.emit("engine://state", engine.status_dto());
            drop(engine);
            crate::cmds::engine::recover_after_crash(&app).await;
            continue;
        }
        if !matches!(engine.state(), EngineState::Ready { .. }) {
            continue;
        }
        match engine.health().await {
            Ok(health) => {
                engine.set_models(&health);
                state.health_failures.store(0, std::sync::atomic::Ordering::SeqCst);
            }
            Err(_) => {
                let fails = state.health_failures.fetch_add(1, std::sync::atomic::Ordering::SeqCst) + 1;
                if fails >= 3 {
                    state.health_failures.store(0, std::sync::atomic::Ordering::SeqCst);
                    drop(engine);
                    crate::cmds::engine::recover_after_crash(&app).await;
                }
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tokio::process::Command as TokioCommand;

    async fn spawn_printer(script: &str) -> (Child, ChildStdout) {
        let mut child = TokioCommand::new("python3")
            .args(["-c", script])
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .kill_on_drop(true)
            .spawn()
            .unwrap();
        let stdout = child.stdout.take().unwrap();
        (child, stdout)
    }

    fn manager_for(child: Child, timeout: Duration) -> EngineManager {
        EngineManager {
            child: Some(child),
            stdin: None,
            token: "secret-token".into(),
            state: EngineState::Starting,
            restarts: VecDeque::new(),
            cfg: EngineConfig {
                program: PathBuf::from("python3"),
                args: vec![],
                models_dir: PathBuf::from("/tmp"),
                cache_dir: PathBuf::from("/tmp"),
                ready_timeout: timeout,
                log_level: "info".into(),
                fixed_port: None,
                pid_file: PathBuf::from("/tmp/morfofix-test.pid"),
                cwd: PathBuf::from("/tmp"),
            },
            drain: vec![],
            intended_shutdown: false,
            models: BTreeMap::new(),
        }
    }

    #[tokio::test]
    async fn wait_ready_skips_garbage() {
        let (child, stdout) = spawn_printer(
            r#"
import sys
print('loading', flush=True)
print('MORFOFIX_READY {"port":53121,"pid":4242,"version":"0.1.0","api":"v0"}', flush=True)
sys.stdin.read()
"#,
        )
        .await;
        let mut mgr = manager_for(child, Duration::from_secs(3));
        let info = mgr.wait_ready(stdout).await.unwrap();
        assert_eq!(info.port, 53121);
        mgr.shutdown().await;
    }

    #[tokio::test]
    async fn wait_ready_timeout() {
        let (child, stdout) = spawn_printer(
            r#"
import time, sys
while True:
    print('log', flush=True)
    time.sleep(0.05)
"#,
        )
        .await;
        let mut mgr = manager_for(child, Duration::from_millis(200));
        let err = mgr.wait_ready(stdout).await.unwrap_err();
        assert!(err.to_string().contains("timeout") || matches!(err, AppError::EngineDown(_)));
        mgr.shutdown().await;
    }

    #[tokio::test]
    async fn wait_ready_bad_json() {
        let (child, stdout) = spawn_printer(
            r#"
print('MORFOFIX_READY {nope', flush=True)
"#,
        )
        .await;
        let mut mgr = manager_for(child, Duration::from_secs(2));
        let err = mgr.wait_ready(stdout).await.unwrap_err();
        assert!(matches!(err, AppError::Invalid(_)));
        mgr.shutdown().await;
    }
}

#[cfg(unix)]
mod libc {
    #[link(name = "c")]
    extern "C" {
        pub fn kill(pid: i32, sig: i32) -> i32;
    }
    pub const SIGTERM: i32 = 15;
}
