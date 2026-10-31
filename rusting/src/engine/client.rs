use std::path::Path;
use std::time::Duration;

use reqwest::header::AUTHORIZATION;
use reqwest::StatusCode;
use serde::{Deserialize, Serialize};

use crate::doc::edit_state::{CatalogItem, EditState};
use crate::error::AppError;

#[derive(Clone, Debug)]
pub struct EngineClient {
    http: reqwest::Client,
    base: String,
    token: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Health {
    pub status: String,
    pub version: String,
    pub api: String,
    #[serde(default)]
    pub uptime_s: f64,
    #[serde(default)]
    pub models: serde_json::Map<String, serde_json::Value>,
    #[serde(default)]
    pub sessions: u32,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SessionInfo {
    pub session_id: String,
    pub width: u32,
    pub height: u32,
    #[serde(default)]
    pub preview_width: u32,
    #[serde(default)]
    pub preview_height: u32,
    #[serde(default)]
    pub orientation_applied: i32,
    #[serde(default)]
    pub format: String,
    #[serde(default)]
    pub has_alpha: bool,
    #[serde(default)]
    pub icc: bool,
    #[serde(default)]
    pub image_sha1: String,
    #[serde(default)]
    pub warnings: Vec<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct DetectReq {
    #[serde(default = "default_what")]
    pub what: Vec<String>,
    #[serde(default = "default_max_faces")]
    pub max_faces: u32,
    #[serde(default = "default_max_people")]
    pub max_people: u32,
}

fn default_what() -> Vec<String> {
    vec!["face".into()]
}
fn default_max_faces() -> u32 {
    5
}
fn default_max_people() -> u32 {
    3
}

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct DetectResp {
    #[serde(default)]
    pub faces: Vec<serde_json::Value>,
    #[serde(default)]
    pub bodies: Vec<serde_json::Value>,
    #[serde(default)]
    pub masks: serde_json::Value,
    #[serde(default)]
    pub timings_ms: serde_json::Value,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct RenderReq {
    pub rev: u64,
    pub state: EditState,
    #[serde(default = "preview_target")]
    pub target: String,
    pub max_side: u32,
    #[serde(default = "jpeg_format")]
    pub format: String,
    #[serde(default = "jpeg_quality")]
    pub quality: u8,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub overlay: Option<String>,
}

fn preview_target() -> String {
    "preview".into()
}
fn jpeg_format() -> String {
    "jpeg".into()
}
fn jpeg_quality() -> u8 {
    85
}

#[derive(Clone, Debug)]
pub struct RenderOut {
    pub bytes: Vec<u8>,
    pub rev: u64,
    pub ms: f64,
    pub warnings: Vec<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ExportReq {
    pub path: std::path::PathBuf,
    pub state: EditState,
    pub format: String,
    pub quality: u8,
    pub keep_metadata: bool,
    pub keep_gps: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ExportResult {
    pub path: std::path::PathBuf,
    pub width: u32,
    pub height: u32,
    pub bytes: u64,
    pub ms: f64,
    #[serde(default)]
    pub warnings: Vec<String>,
}

impl EngineClient {
    pub fn new(port: u16, token: &str) -> Result<Self, AppError> {
        let http = reqwest::Client::builder()
            .no_proxy()
            .connect_timeout(Duration::from_secs(1))
            .build()
            .map_err(AppError::from)?;
        Ok(Self {
            http,
            base: format!("http://127.0.0.1:{port}"),
            token: token.to_string(),
        })
    }

    pub fn base_url(&self) -> &str {
        &self.base
    }

    pub async fn health(&self) -> Result<Health, AppError> {
        self.map_response(
            self.http
                .get(format!("{}/health", self.base))
                .timeout(Duration::from_secs(1))
                .send()
                .await,
        )
        .await
    }

    pub async fn open_session(&self, path: &Path) -> Result<SessionInfo, AppError> {
        let body = serde_json::json!({ "path": path });
        self.map_response(
            self.auth(self.http.post(format!("{}/session", self.base)))
                .timeout(Duration::from_secs(30))
                .json(&body)
                .send()
                .await,
        )
        .await
    }

    pub async fn close_session(&self, sid: &str) -> Result<(), AppError> {
        let result = self
            .auth(self.http.delete(format!("{}/session/{sid}", self.base)))
            .timeout(Duration::from_secs(5))
            .send()
            .await;
        match result {
            Ok(resp) if resp.status() == StatusCode::NO_CONTENT || resp.status().is_success() => Ok(()),
            Ok(resp) => {
                let _ = map_error_body(resp).await;
                Ok(())
            }
            Err(_) => Ok(()),
        }
    }

    pub async fn detect(&self, sid: &str, req: &DetectReq) -> Result<DetectResp, AppError> {
        self.map_response(
            self.auth(self.http.post(format!("{}/session/{sid}/detect", self.base)))
                .timeout(Duration::from_secs(30))
                .json(req)
                .send()
                .await,
        )
        .await
    }

    pub async fn render(&self, sid: &str, req: &RenderReq) -> Result<RenderOut, AppError> {
        let resp = match self
            .auth(self.http.post(format!("{}/session/{sid}/render", self.base)))
            .timeout(Duration::from_secs(10))
            .json(req)
            .send()
            .await
        {
            Ok(resp) => resp,
            Err(err) => return Err(AppError::from(err)),
        };
        if !resp.status().is_success() {
            return Err(map_error_body(resp).await);
        }
        let rev = header_u64(resp.headers().get("x-rev")).unwrap_or(req.rev);
        let ms = header_f64(resp.headers().get("x-render-ms")).unwrap_or(0.0);
        let warnings = resp
            .headers()
            .get("x-warnings")
            .and_then(|v| v.to_str().ok())
            .filter(|s| !s.is_empty())
            .map(|s| s.split(',').map(|p| p.trim().to_string()).filter(|p| !p.is_empty()).collect())
            .unwrap_or_default();
        let bytes = resp.bytes().await.map_err(AppError::from)?.to_vec();
        log::debug!(
            target: "engine",
            "render sid={} rev={rev} ms={ms:.0} bytes={}k warnings={warnings:?}",
            short_sid(sid),
            bytes.len() / 1024
        );
        Ok(RenderOut {
            bytes,
            rev,
            ms,
            warnings,
        })
    }

    pub async fn export(&self, sid: &str, req: &ExportReq) -> Result<ExportResult, AppError> {
        self.map_response(
            self.auth(self.http.post(format!("{}/session/{sid}/export", self.base)))
                .timeout(Duration::from_secs(120))
                .json(req)
                .send()
                .await,
        )
        .await
    }

    pub async fn catalog(&self) -> Result<Vec<CatalogItem>, AppError> {
        let value: serde_json::Value = self
            .map_response(
                self.auth(self.http.get(format!("{}/catalog", self.base)))
                    .timeout(Duration::from_secs(5))
                    .send()
                    .await,
            )
            .await?;
        if let Some(params) = value.get("params") {
            Ok(serde_json::from_value(params.clone())?)
        } else {
            Ok(serde_json::from_value(value)?)
        }
    }

    pub async fn shutdown(&self) -> Result<(), AppError> {
        let resp = self
            .auth(self.http.post(format!("{}/shutdown", self.base)))
            .timeout(Duration::from_secs(1))
            .send()
            .await
            .map_err(AppError::from)?;
        if resp.status() == StatusCode::ACCEPTED || resp.status().is_success() {
            Ok(())
        } else {
            Err(map_error_body(resp).await)
        }
    }

    fn auth(&self, builder: reqwest::RequestBuilder) -> reqwest::RequestBuilder {
        builder.header(AUTHORIZATION, format!("Bearer {}", self.token))
    }

    async fn map_response<T: for<'de> Deserialize<'de>>(
        &self,
        result: Result<reqwest::Response, reqwest::Error>,
    ) -> Result<T, AppError> {
        let resp = result.map_err(AppError::from)?;
        if resp.status().is_success() || resp.status() == StatusCode::ACCEPTED {
            Ok(resp.json().await.map_err(AppError::from)?)
        } else {
            Err(map_error_body(resp).await)
        }
    }
}

fn short_sid(sid: &str) -> String {
    sid.chars().take(8).collect()
}

fn header_u64(value: Option<&reqwest::header::HeaderValue>) -> Option<u64> {
    value.and_then(|v| v.to_str().ok()).and_then(|s| s.parse().ok())
}

fn header_f64(value: Option<&reqwest::header::HeaderValue>) -> Option<f64> {
    value.and_then(|v| v.to_str().ok()).and_then(|s| s.parse().ok())
}

#[derive(Deserialize)]
struct EngineErrBody {
    error: EngineErrInner,
}

#[derive(Deserialize)]
struct EngineErrInner {
    code: String,
    message: String,
}

async fn map_error_body(resp: reqwest::Response) -> AppError {
    let status = resp.status();
    if let Ok(body) = resp.json::<EngineErrBody>().await {
        if body.error.code == "BAD_PARAM" {
            log::warn!(target: "engine", "BAD_PARAM {}", body.error.message);
        }
        return AppError::from_engine_code(&body.error.code, body.error.message);
    }
    match status {
        StatusCode::UNAUTHORIZED => AppError::Engine("UNAUTHORIZED".into(), "token inválido".into()),
        StatusCode::SERVICE_UNAVAILABLE => AppError::Engine("MODEL_MISSING".into(), "modelo ausente".into()),
        _ => AppError::engine_down(format!("HTTP {}", status.as_u16())),
    }
}
