use morfofix_lib::doc::edit_state::EditState;
use morfofix_lib::engine::client::{EngineClient, RenderReq};
use morfofix_lib::error::AppError;
use serde_json::json;
use wiremock::matchers::{header, method, path};
use wiremock::{Mock, MockServer, ResponseTemplate};

fn req() -> RenderReq {
    RenderReq {
        rev: 1,
        state: EditState::new(),
        target: "preview".into(),
        max_side: 1600,
        format: "jpeg".into(),
        quality: 85,
        overlay: None,
    }
}

async fn client_on(server: &MockServer) -> EngineClient {
    EngineClient::new(server.address().port(), "tok").unwrap()
}

#[tokio::test]
async fn health_ok() {
    let server = MockServer::start().await;
    Mock::given(method("GET"))
        .and(path("/health"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "status": "ok", "version": "0.1.0", "api": "v0"
        })))
        .mount(&server)
        .await;
    assert_eq!(client_on(&server).await.health().await.unwrap().version, "0.1.0");
}

#[tokio::test]
async fn bad_param() {
    let server = MockServer::start().await;
    Mock::given(method("POST"))
        .and(path("/session/s1/render"))
        .and(header("Authorization", "Bearer tok"))
        .respond_with(ResponseTemplate::new(400).set_body_json(json!({
            "error": { "code": "BAD_PARAM", "message": "fuera de rango", "detail": {} }
        })))
        .mount(&server)
        .await;
    match client_on(&server).await.render("s1", &req()).await.unwrap_err() {
        AppError::Engine(code, msg) => {
            assert_eq!(code, "BAD_PARAM");
            assert!(msg.contains("fuera"));
        }
        other => panic!("{other:?}"),
    }
}

#[tokio::test]
async fn stale_rev_is_superseded() {
    let server = MockServer::start().await;
    Mock::given(method("POST"))
        .and(path("/session/s1/render"))
        .respond_with(ResponseTemplate::new(409).set_body_json(json!({
            "error": { "code": "STALE_REV", "message": "viejo" }
        })))
        .mount(&server)
        .await;
    assert!(matches!(
        client_on(&server).await.render("s1", &req()).await.unwrap_err(),
        AppError::Superseded
    ));
}

#[tokio::test]
async fn unauthorized() {
    let server = MockServer::start().await;
    Mock::given(method("POST"))
        .and(path("/session/s1/render"))
        .respond_with(ResponseTemplate::new(401).set_body_json(json!({
            "error": { "code": "UNAUTHORIZED", "message": "token inválido" }
        })))
        .mount(&server)
        .await;
    assert!(matches!(
        client_on(&server).await.render("s1", &req()).await.unwrap_err(),
        AppError::Engine(code, _) if code == "UNAUTHORIZED"
    ));
}

#[tokio::test]
async fn model_missing() {
    let server = MockServer::start().await;
    Mock::given(method("POST"))
        .and(path("/session/s1/render"))
        .respond_with(ResponseTemplate::new(503).set_body_json(json!({
            "error": { "code": "MODEL_MISSING", "message": "falta modelo" }
        })))
        .mount(&server)
        .await;
    assert!(matches!(
        client_on(&server).await.render("s1", &req()).await.unwrap_err(),
        AppError::Engine(code, _) if code == "MODEL_MISSING"
    ));
}

#[tokio::test]
async fn timeout_is_engine_down() {
    let server = MockServer::start().await;
    Mock::given(method("GET"))
        .and(path("/health"))
        .respond_with(ResponseTemplate::new(200).set_delay(std::time::Duration::from_secs(3)))
        .mount(&server)
        .await;
    assert!(matches!(
        client_on(&server).await.health().await.unwrap_err(),
        AppError::EngineDown(_)
    ));
}
