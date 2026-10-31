use morfofix_lib::doc::edit_state::{sanitize_with_indices, Catalog, EditState};

#[test]
fn fixture_roundtrip() {
    let raw = include_str!("fixtures/edit_state.json");
    let parsed: EditState = serde_json::from_str(raw).expect("fixture deserializa");
    let again = serde_json::to_vec(&parsed).expect("serializa");
    let parsed2: EditState = serde_json::from_slice(&again).expect("re-deserializa");
    assert_eq!(parsed, parsed2);
}

#[test]
fn fixture_cuerpo_roundtrip() {
    // Mismo JSON que mofixPy/tests/fixtures/edit_state_cuerpo.json (lo valida pydantic).
    let raw = include_str!("fixtures/edit_state_cuerpo.json");
    let parsed: EditState = serde_json::from_str(raw).expect("fixture cuerpo deserializa");
    let h = parsed.height.as_ref().unwrap();
    assert_eq!(h.y_start, Some(0.6));
    assert_eq!(h.y_end, Some(1.0));
    assert_eq!(parsed.freeze.rects.len(), 1);
    assert!(parsed.freeze.invert);
    assert_eq!(parsed.liquify[0].k, 0.95);
    let arm = parsed.arm.manual.as_ref().expect("arm.manual");
    assert!((arm.value - 0.4).abs() < 1e-6);
    let again = serde_json::to_vec(&parsed).expect("serializa");
    let parsed2: EditState = serde_json::from_slice(&again).expect("re-deserializa");
    assert_eq!(parsed, parsed2);
}

#[test]
fn arm_survives_roundtrip() {
    let raw = r#"{"arm":{"manual":{"cx":0.4,"cy":0.5,"rx":0.06,"ry":0.14,"angle":12,"value":0.6,"protect_bg":true}}}"#;
    let state: EditState = serde_json::from_str(raw).expect("deserializa arm");
    let out = serde_json::to_value(&state).expect("serializa");
    assert!((out["arm"]["manual"]["value"].as_f64().unwrap() - 0.6).abs() < 1e-6);
    assert_eq!(out["arm"]["manual"]["protect_bg"], serde_json::json!(true));
}

#[test]
fn arm_null_is_omitted() {
    let state: EditState = serde_json::from_str(r#"{"arm":{"manual":null}}"#).unwrap();
    let out = serde_json::to_value(&state).unwrap();
    assert!(out.get("arm").is_none());
}

#[test]
fn arm_sanitize_clamps() {
    let mut state: EditState = serde_json::from_value(serde_json::json!({
        "arm": { "manual": {
            "cx": 0.5, "cy": 0.5, "rx": 0.9, "ry": 0.001, "angle": 400.0, "value": 2.0
        }}
    })).unwrap();
    sanitize_with_indices(&mut state, &Catalog::from_items(vec![]), None, None);
    let m = state.arm.manual.unwrap();
    assert!((m.rx - 0.5).abs() < 1e-5);
    assert!((m.ry - 0.01).abs() < 1e-5);
    assert!((m.angle - 180.0).abs() < 1e-5);
    assert!((m.value - 1.0).abs() < 1e-5);
}

#[test]
fn python_top_level_keys_survive() {
    // Espejo de EditState.model_fields (+ alias schema) en core/edit_state.py.
    let keys = [
        "schema", "face", "facelift", "body", "body_options", "height", "liquify",
        "manual_shapes", "freeze", "retouch", "remove", "photo", "arm", "muscle",
    ];
    let mut obj = serde_json::Map::new();
    obj.insert("schema".into(), serde_json::json!(1));
    obj.insert("arm".into(), serde_json::json!({
        "manual": { "cx": 0.5, "cy": 0.5, "rx": 0.05, "ry": 0.1, "value": 0.3 }
    }));
    obj.insert("muscle".into(), serde_json::json!({
        "0": { "mode": "abs", "strength": 0.4 }
    }));
    let state: EditState = serde_json::from_value(serde_json::Value::Object(obj)).unwrap();
    let out = serde_json::to_value(&state).unwrap();
    for key in ["arm", "muscle"] {
        assert!(out.get(key).is_some(), "{key} se perdió en serde");
    }
    assert!(keys.contains(&"arm"));
}
