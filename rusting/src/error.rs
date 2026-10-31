use serde::Serialize;

#[derive(Debug, thiserror::Error, Serialize)]
#[serde(tag = "code", content = "message")]
pub enum AppError {
    #[error("motor no disponible")]
    EngineDown(String),
    #[error("{1}")]
    Engine(String, String),
    #[error("superado")]
    Superseded,
    #[error("sin documento")]
    NoDocument,
    #[error("{0}")]
    Io(String),
    #[error("{0}")]
    Invalid(String),
}

impl AppError {
    pub fn io(err: impl ToString) -> Self {
        Self::Io(err.to_string())
    }

    pub fn invalid(err: impl ToString) -> Self {
        Self::Invalid(err.to_string())
    }

    pub fn engine_down(err: impl ToString) -> Self {
        Self::EngineDown(err.to_string())
    }

    pub fn from_engine_code(code: &str, message: String) -> Self {
        if code == "STALE_REV" {
            Self::Superseded
        } else {
            Self::Engine(code.to_string(), message)
        }
    }
}

impl From<std::io::Error> for AppError {
    fn from(value: std::io::Error) -> Self {
        Self::Io(value.to_string())
    }
}

impl From<serde_json::Error> for AppError {
    fn from(value: serde_json::Error) -> Self {
        Self::Invalid(value.to_string())
    }
}

impl From<reqwest::Error> for AppError {
    fn from(value: reqwest::Error) -> Self {
        if value.is_timeout() || value.is_connect() || value.is_request() {
            Self::EngineDown(if value.is_timeout() {
                "timeout".into()
            } else {
                "conexión rechazada".into()
            })
        } else {
            Self::EngineDown(value.without_url().to_string())
        }
    }
}
