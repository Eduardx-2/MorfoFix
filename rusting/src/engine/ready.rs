use serde::Deserialize;

use crate::error::AppError;

pub const READY_PREFIX: &str = "MORFOFIX_READY ";

#[derive(Clone, Debug, PartialEq, Eq, Deserialize)]
pub struct ReadyInfo {
    pub port: u16,
    pub pid: u32,
    pub version: String,
    pub api: String,
}

#[derive(Debug, thiserror::Error, PartialEq, Eq)]
pub enum ReadyParseError {
    #[error("no es una línea READY")]
    NotReady,
    #[error("JSON de READY inválido")]
    BadJson,
    #[error("READY incompleto o incompatible")]
    Invalid,
}

pub fn parse_ready_line(line: &str) -> Result<ReadyInfo, ReadyParseError> {
    let line = line.trim_end_matches(['\r', '\n']);
    let Some(json) = line.strip_prefix(READY_PREFIX) else {
        return Err(ReadyParseError::NotReady);
    };
    let info: ReadyInfo = serde_json::from_str(json).map_err(|_| ReadyParseError::BadJson)?;
    if info.port == 0 || info.pid == 0 || info.version.is_empty() || info.api != "v0" {
        return Err(ReadyParseError::Invalid);
    }
    Ok(info)
}

impl From<ReadyParseError> for AppError {
    fn from(value: ReadyParseError) -> Self {
        match value {
            ReadyParseError::NotReady => AppError::invalid("línea READY ausente"),
            ReadyParseError::BadJson => AppError::invalid("JSON de READY inválido"),
            ReadyParseError::Invalid => AppError::invalid("READY incompleto o API incompatible"),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn valid_first_line() {
        let info = parse_ready_line(
            r#"MORFOFIX_READY {"port":53121,"pid":4242,"version":"0.1.0","api":"v0"}"#,
        )
        .unwrap();
        assert_eq!(info.port, 53121);
        assert_eq!(info.pid, 4242);
        assert_eq!(info.version, "0.1.0");
        assert_eq!(info.api, "v0");
    }

    #[test]
    fn garbage_is_not_ready() {
        assert_eq!(
            parse_ready_line("loading models"),
            Err(ReadyParseError::NotReady)
        );
    }

    #[test]
    fn broken_json() {
        assert_eq!(
            parse_ready_line("MORFOFIX_READY {nope"),
            Err(ReadyParseError::BadJson)
        );
    }

    #[test]
    fn invalid_fields() {
        assert_eq!(
            parse_ready_line(r#"MORFOFIX_READY {"port":0,"pid":1,"version":"0.1.0","api":"v0"}"#),
            Err(ReadyParseError::Invalid)
        );
        assert_eq!(
            parse_ready_line(r#"MORFOFIX_READY {"port":1,"pid":1,"version":"0.1.0","api":"v1"}"#),
            Err(ReadyParseError::Invalid)
        );
    }
}
