use std::collections::BTreeMap;

use serde::{Deserialize, Serialize};

use crate::error::AppError;

#[derive(Clone, Debug, Default, PartialEq, Serialize, Deserialize)]
#[serde(default)]
pub struct EditState {
    #[serde(rename = "schema")]
    pub schema: u32,
    pub face: BTreeMap<String, BTreeMap<String, f32>>,
    pub facelift: BTreeMap<String, BTreeMap<String, f32>>,
    pub body: BTreeMap<String, BTreeMap<String, f32>>,
    pub body_options: BodyOptions,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub height: Option<Height>,
    pub liquify: Vec<LiquifyStroke>,
    pub manual_shapes: Vec<ManualShape>,
    pub freeze: Freeze,
    pub retouch: Retouch,
    pub remove: Vec<RemoveOp>,
    pub photo: Photo,
    #[serde(default, skip_serializing_if = "BTreeMap::is_empty")]
    pub muscle: BTreeMap<String, Muscle>,
    #[serde(default, skip_serializing_if = "Arm::is_empty")]
    pub arm: Arm,
    #[serde(default, skip_serializing_if = "BTreeMap::is_empty")]
    pub makeup: BTreeMap<String, serde_json::Value>,
    #[serde(default, skip_serializing_if = "BTreeMap::is_empty")]
    pub eyes: BTreeMap<String, serde_json::Value>,
    #[serde(default, skip_serializing_if = "BTreeMap::is_empty")]
    pub hair: BTreeMap<String, serde_json::Value>,
    #[serde(default, skip_serializing_if = "BTreeMap::is_empty")]
    pub background: BTreeMap<String, serde_json::Value>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub overlays: Vec<serde_json::Value>,
}

impl EditState {
    pub fn new() -> Self {
        Self {
            schema: 1,
            ..Self::default()
        }
    }
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct BodyOptions {
    pub bg_protect: bool,
    pub head_protect: bool,
}

impl Default for BodyOptions {
    fn default() -> Self {
        Self {
            bg_protect: false,
            head_protect: true,
        }
    }
}

/// Estiramiento vertical. `y_start`/`y_end` (0..1, imagen sin estirar) son las
/// líneas del overlay; si vienen mandan sobre `band` (compatibilidad).
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Height {
    #[serde(default = "default_band")]
    pub band: [f32; 2],
    pub value: f32,
    #[serde(default)]
    pub keep_canvas: bool,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub y_start: Option<f32>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub y_end: Option<f32>,
}

fn default_band() -> [f32; 2] {
    [0.48, 0.92]
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct LiquifyStroke {
    pub pts: Vec<[f32; 2]>,
    pub k: f32,
    pub r: f32,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ManualShape {
    #[serde(rename = "type")]
    pub kind: String,
    pub cx: f32,
    pub cy: f32,
    pub w: f32,
    pub h: f32,
    #[serde(default)]
    pub angle: f32,
    pub value: f32,
    #[serde(default = "default_feather")]
    pub feather: f32,
    #[serde(default = "default_true")]
    pub symmetric: bool,
}

fn default_feather() -> f32 {
    0.5
}
fn default_true() -> bool {
    true
}

#[derive(Clone, Debug, Default, PartialEq, Serialize, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct Freeze {
    pub strokes: Vec<BrushStroke>,
    /// Rectángulos (x, y, w, h normalizados); se aplican después de los trazos.
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub rects: Vec<FreezeRect>,
    #[serde(skip_serializing_if = "is_false")]
    pub invert: bool,
    /// Difuminado del borde, fracción del lado menor (0..0.25).
    #[serde(skip_serializing_if = "is_zero")]
    pub feather: f32,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct FreezeRect {
    pub x: f32,
    pub y: f32,
    pub w: f32,
    pub h: f32,
    #[serde(default)]
    pub erase: bool,
}

fn is_false(v: &bool) -> bool {
    !*v
}
fn is_zero(v: &f32) -> bool {
    *v == 0.0
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct BrushStroke {
    pub pts: Vec<[f32; 2]>,
    pub radius: f32,
    #[serde(default)]
    pub erase: bool,
}

#[derive(Clone, Debug, Default, PartialEq, Serialize, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct Retouch {
    pub degree_skin_smooth: f32,
    pub degree_sharpen: f32,
    pub degree_whiten_skin: f32,
    pub degree_skin_details: f32,
    pub degree_skin_texture: f32,
    pub degree_skin_matte: f32,
    pub degree_whiten_teeth: f32,
    pub degree_brighten_eyes: f32,
    pub degree_whiten_eyes: f32,
    pub degree_remove_eye_redness: f32,
    pub degree_dark_circles: f32,
    pub degree_remove_blemishes: f32,
    pub degree_wrinkles: f32,
    #[serde(default, skip_serializing_if = "is_zero")]
    pub sculpt_contour: f32,
    #[serde(default, skip_serializing_if = "is_zero")]
    pub sculpt_jaw: f32,
    #[serde(default, skip_serializing_if = "is_zero")]
    pub sculpt_cheeks: f32,
    #[serde(default, skip_serializing_if = "is_zero")]
    pub sculpt_eyes: f32,
    #[serde(default, skip_serializing_if = "is_zero")]
    pub skin_tone: f32,
    #[serde(default, skip_serializing_if = "is_zero")]
    pub glow: f32,
    pub brush: BTreeMap<String, Mask>,
}

#[derive(Clone, Debug, Default, PartialEq, Serialize, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct Mask {
    pub strokes: Vec<BrushStroke>,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(default)]
pub struct Muscle {
    pub mode: String,
    pub strength: f32,
    pub definition: f32,
    pub warp: f32,
    pub light: String,
    pub gloss: f32,
    pub brush: Mask,
}

impl Default for Muscle {
    fn default() -> Self {
        Self {
            mode: "man_abs".into(),
            strength: 0.6,
            definition: 0.5,
            warp: 0.3,
            light: "auto".into(),
            gloss: 0.0,
            brush: Mask::default(),
        }
    }
}

#[derive(Clone, Debug, Default, PartialEq, Serialize, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct Arm {
    /// Trazo activo: lo que mueve el editor.
    pub manual: Option<ArmManual>,
    /// Trazos ya fijados (doc 23). Se aplican en orden antes del activo.
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub manual_strokes: Vec<ArmManual>,
}

pub const ARM_MAX_STROKES: usize = 32;
pub const MANUAL_SHAPES_MAX: usize = 64;

impl Arm {
    pub fn is_empty(&self) -> bool {
        self.manual.is_none() && self.manual_strokes.is_empty()
    }
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ArmManual {
    pub cx: f32,
    pub cy: f32,
    pub rx: f32,
    pub ry: f32,
    #[serde(default)]
    pub angle: f32,
    #[serde(default)]
    pub value: f32,
    #[serde(default)]
    pub protect_bg: bool,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RemoveOp {
    pub strokes: Vec<BrushStroke>,
    #[serde(default = "default_telea")]
    pub method: String,
}

fn default_telea() -> String {
    "telea".into()
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct Photo {
    pub crop: [f32; 4],
    pub rotate_deg: f32,
    pub flip_h: bool,
    pub hsl: Hsl,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub adjust: Option<serde_json::Value>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub lut: Option<serde_json::Value>,
}

impl Default for Photo {
    fn default() -> Self {
        Self {
            crop: [0.0, 0.0, 1.0, 1.0],
            rotate_deg: 0.0,
            flip_h: false,
            hsl: Hsl::default(),
            adjust: None,
            lut: None,
        }
    }
}

#[derive(Clone, Debug, Default, PartialEq, Serialize, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct Hsl {
    pub hue: f32,
    pub saturation: f32,
    pub lightness: f32,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Kind {
    Intensity,
    Degree,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct CatalogItem {
    pub name: String,
    #[serde(default)]
    pub label_es: String,
    #[serde(default)]
    pub tab: String,
    #[serde(default)]
    pub kind: String,
    #[serde(default)]
    pub range: Vec<f32>,
    #[serde(default)]
    pub lr: bool,
    #[serde(default)]
    pub status: String,
    #[serde(default)]
    pub phase: u32,
    #[serde(default)]
    pub group: String,
}

#[derive(Clone, Debug, Default)]
pub struct Catalog {
    pub loaded: bool,
    pub items: Vec<CatalogItem>,
}

impl Catalog {
    pub fn from_items(items: Vec<CatalogItem>) -> Self {
        Self {
            loaded: true,
            items,
        }
    }

    pub fn contains(&self, name: &str) -> bool {
        let base = strip_side(name);
        self.items.iter().any(|item| {
            item.name == name
                || item.name == base
                || (item.lr && (name == format!("left_{}", item.name) || name == format!("right_{}", item.name)))
        })
    }
}

#[derive(Clone, Debug, PartialEq, Serialize)]
pub struct Fix {
    pub path: String,
    pub reason: String,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum BrushMode {
    Suave,
    Fuerte,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(untagged)]
pub enum Target {
    Face { face: u32 },
    Human { human: u32 },
    Global(String),
}

pub fn ui_to_intensity(v: i32) -> f32 {
    (v.clamp(-100, 100) as f32) / 100.0
}

pub fn ui_to_degree(v: i32) -> f32 {
    (v.clamp(0, 100) as f32) / 100.0
}

pub fn kind_of(name: &str) -> Option<Kind> {
    let mut base = name;
    if let Some(rest) = base.strip_prefix("left_") {
        base = rest;
    } else if let Some(rest) = base.strip_prefix("right_") {
        base = rest;
    }
    if let Some(rest) = base.strip_prefix("up_") {
        base = rest;
    } else if let Some(rest) = base.strip_prefix("down_") {
        base = rest;
    }
    if base.starts_with("degree_") {
        Some(Kind::Degree)
    } else if base.starts_with("intensity_") {
        Some(Kind::Intensity)
    } else {
        None
    }
}

pub fn sanitize(state: &mut EditState, catalog: &Catalog) -> Vec<Fix> {
    sanitize_with_indices(state, catalog, None, None)
}

pub fn sanitize_with_indices(
    state: &mut EditState,
    catalog: &Catalog,
    faces: Option<&[u32]>,
    bodies: Option<&[u32]>,
) -> Vec<Fix> {
    let mut fixes = Vec::new();
    if state.schema == 0 {
        state.schema = 1;
    }
    sanitize_param_map(&mut state.face, catalog, faces, "face", &mut fixes);
    sanitize_param_map(&mut state.facelift, catalog, faces, "facelift", &mut fixes);
    sanitize_param_map(&mut state.body, catalog, bodies, "body", &mut fixes);
    sanitize_muscle(&mut state.muscle, bodies, &mut fixes);
    if let Some(m) = state.arm.manual.as_mut() {
        sanitize_arm_manual(m, "arm.manual", &mut fixes);
    }
    // Trazos fijados: sin valor no aportan nada; más de 32 → se recortan los más viejos.
    state.arm.manual_strokes.retain(|m| m.value.is_finite() && m.value != 0.0);
    if state.arm.manual_strokes.len() > ARM_MAX_STROKES {
        let extra = state.arm.manual_strokes.len() - ARM_MAX_STROKES;
        log::warn!(target: "sanitize", "arm.manual_strokes: {extra} de más, recorto los primeros");
        fixes.push(Fix { path: "arm.manual_strokes".into(), reason: format!("más de {ARM_MAX_STROKES}") });
        state.arm.manual_strokes.drain(0..extra);
    }
    for (i, m) in state.arm.manual_strokes.iter_mut().enumerate() {
        sanitize_arm_manual(m, &format!("arm.manual_strokes.{i}"), &mut fixes);
    }
    if state.manual_shapes.len() > MANUAL_SHAPES_MAX {
        let extra = state.manual_shapes.len() - MANUAL_SHAPES_MAX;
        fixes.push(Fix { path: "manual_shapes".into(), reason: format!("más de {MANUAL_SHAPES_MAX}") });
        state.manual_shapes.drain(0..extra);
    }
    if let Some(height) = state.height.as_mut() {
        height.value = finite_or_zero(height.value, "height.value", &mut fixes);
        height.value = height.value.clamp(-1.0, 1.0);
        // Las líneas del overlay (y_start/y_end) mandan sobre band.
        let raw0 = height.y_start.unwrap_or(height.band[0]);
        let raw1 = height.y_end.unwrap_or(height.band[1]);
        let mut y0 = finite_or_zero(raw0, "height.y_start", &mut fixes).clamp(0.0, 1.0);
        let mut y1 = finite_or_zero(raw1, "height.y_end", &mut fixes).clamp(0.0, 1.0);
        if y0 > y1 {
            std::mem::swap(&mut y0, &mut y1);
            fixes.push(Fix {
                path: "height.band".into(),
                reason: "banda invertida".into(),
            });
        }
        if y1 - y0 < 0.02 {
            y1 = (y0 + 0.02).min(1.0);
            y0 = (y1 - 0.02).max(0.0);
            fixes.push(Fix {
                path: "height.band".into(),
                reason: "alto mínimo 0.02".into(),
            });
        }
        height.band = [y0, y1];
        if height.y_start.is_some() || height.y_end.is_some() {
            height.y_start = Some(y0);
            height.y_end = Some(y1);
        }
    }
    for (i, stroke) in state.liquify.iter_mut().enumerate() {
        stroke.k = finite_or_zero(stroke.k, &format!("liquify.{i}.k"), &mut fixes).clamp(0.001, LIQUIFY_K_MAX);
        stroke.r = finite_or_zero(stroke.r, &format!("liquify.{i}.r"), &mut fixes).clamp(0.002, 0.5);
        clamp_pts(&mut stroke.pts, &format!("liquify.{i}.pts"), &mut fixes);
    }
    for (i, shape) in state.manual_shapes.iter_mut().enumerate() {
        shape.cx = unit(shape.cx, &format!("manual_shapes.{i}.cx"), &mut fixes);
        shape.cy = unit(shape.cy, &format!("manual_shapes.{i}.cy"), &mut fixes);
        shape.w = finite_or_zero(shape.w, &format!("manual_shapes.{i}.w"), &mut fixes).clamp(0.001, 1.0);
        shape.h = finite_or_zero(shape.h, &format!("manual_shapes.{i}.h"), &mut fixes).clamp(0.001, 1.0);
        shape.value = finite_or_zero(shape.value, &format!("manual_shapes.{i}.value"), &mut fixes).clamp(-1.0, 1.0);
        shape.feather = unit(shape.feather, &format!("manual_shapes.{i}.feather"), &mut fixes);
    }
    for (i, stroke) in state.freeze.strokes.iter_mut().enumerate() {
        clamp_pts(&mut stroke.pts, &format!("freeze.{i}.pts"), &mut fixes);
        stroke.radius = finite_or_zero(stroke.radius, &format!("freeze.{i}.radius"), &mut fixes).clamp(0.001, 0.5);
    }
    state.freeze.rects.retain(|r| r.x.is_finite() && r.y.is_finite() && r.w.is_finite() && r.h.is_finite());
    for (i, r) in state.freeze.rects.iter_mut().enumerate() {
        r.x = unit(r.x, &format!("freeze.rects.{i}.x"), &mut fixes);
        r.y = unit(r.y, &format!("freeze.rects.{i}.y"), &mut fixes);
        r.w = r.w.clamp(0.001, 1.0);
        r.h = r.h.clamp(0.001, 1.0);
    }
    state.freeze.feather = finite_or_zero(state.freeze.feather, "freeze.feather", &mut fixes).clamp(0.0, 0.25);
    sanitize_retouch(&mut state.retouch, catalog, &mut fixes);
    for (i, op) in state.remove.iter_mut().enumerate() {
        for (j, stroke) in op.strokes.iter_mut().enumerate() {
            clamp_pts(&mut stroke.pts, &format!("remove.{i}.{j}.pts"), &mut fixes);
            stroke.radius =
                finite_or_zero(stroke.radius, &format!("remove.{i}.{j}.radius"), &mut fixes).clamp(0.001, 0.5);
        }
    }
    let crop = &mut state.photo.crop;
    for c in crop.iter_mut() {
        *c = unit(*c, "photo.crop", &mut fixes);
    }
    if crop[2] <= crop[0] || crop[3] <= crop[1] {
        *crop = [0.0, 0.0, 1.0, 1.0];
        fixes.push(Fix {
            path: "photo.crop".into(),
            reason: "área no positiva".into(),
        });
    }
    state.photo.rotate_deg = finite_or_zero(state.photo.rotate_deg, "photo.rotate_deg", &mut fixes).clamp(-180.0, 180.0);
    state.photo.hsl.hue = finite_or_zero(state.photo.hsl.hue, "photo.hsl.hue", &mut fixes).clamp(-1.0, 1.0);
    state.photo.hsl.saturation =
        finite_or_zero(state.photo.hsl.saturation, "photo.hsl.saturation", &mut fixes).clamp(-1.0, 1.0);
    state.photo.hsl.lightness =
        finite_or_zero(state.photo.hsl.lightness, "photo.hsl.lightness", &mut fixes).clamp(-1.0, 1.0);
    fixes
}

fn sanitize_muscle(
    muscle: &mut BTreeMap<String, Muscle>,
    bodies: Option<&[u32]>,
    fixes: &mut Vec<Fix>,
) {
    let keys: Vec<String> = muscle.keys().cloned().collect();
    for key in keys {
        if !key.chars().all(|c| c.is_ascii_digit()) {
            muscle.remove(&key);
            fixes.push(Fix {
                path: format!("muscle.{key}"),
                reason: "índice inválido".into(),
            });
            continue;
        }
        if let Some(allowed) = bodies {
            if let Ok(idx) = key.parse::<u32>() {
                if !allowed.contains(&idx) {
                    muscle.remove(&key);
                    fixes.push(Fix {
                        path: format!("muscle.{key}"),
                        reason: "índice ausente en la detección".into(),
                    });
                    continue;
                }
            }
        }
        if let Some(cfg) = muscle.get_mut(&key) {
            cfg.strength = finite_or_zero(cfg.strength, &format!("muscle.{key}.strength"), fixes).clamp(0.0, 1.0);
            cfg.definition = finite_or_zero(cfg.definition, &format!("muscle.{key}.definition"), fixes).clamp(0.0, 1.0);
            cfg.warp = finite_or_zero(cfg.warp, &format!("muscle.{key}.warp"), fixes).clamp(0.0, 1.0);
            cfg.gloss = finite_or_zero(cfg.gloss, &format!("muscle.{key}.gloss"), fixes).clamp(0.0, 1.0);
            for (i, stroke) in cfg.brush.strokes.iter_mut().enumerate() {
                clamp_pts(&mut stroke.pts, &format!("muscle.{key}.brush.{i}.pts"), fixes);
                stroke.radius =
                    finite_or_zero(stroke.radius, &format!("muscle.{key}.brush.{i}.radius"), fixes).clamp(0.001, 0.5);
            }
        }
    }
}

fn sanitize_retouch(retouch: &mut Retouch, catalog: &Catalog, fixes: &mut Vec<Fix>) {
    for (name, value) in [
        ("degree_skin_smooth", &mut retouch.degree_skin_smooth),
        ("degree_sharpen", &mut retouch.degree_sharpen),
        ("degree_whiten_skin", &mut retouch.degree_whiten_skin),
        ("degree_skin_details", &mut retouch.degree_skin_details),
        ("degree_skin_texture", &mut retouch.degree_skin_texture),
        ("degree_skin_matte", &mut retouch.degree_skin_matte),
        ("degree_whiten_teeth", &mut retouch.degree_whiten_teeth),
        ("degree_brighten_eyes", &mut retouch.degree_brighten_eyes),
        ("degree_whiten_eyes", &mut retouch.degree_whiten_eyes),
        ("degree_remove_eye_redness", &mut retouch.degree_remove_eye_redness),
        ("degree_dark_circles", &mut retouch.degree_dark_circles),
        ("degree_remove_blemishes", &mut retouch.degree_remove_blemishes),
        ("degree_wrinkles", &mut retouch.degree_wrinkles),
        ("sculpt_contour", &mut retouch.sculpt_contour),
        ("sculpt_jaw", &mut retouch.sculpt_jaw),
        ("sculpt_cheeks", &mut retouch.sculpt_cheeks),
        ("sculpt_eyes", &mut retouch.sculpt_eyes),
        ("skin_tone", &mut retouch.skin_tone),
        ("glow", &mut retouch.glow),
    ] {
        *value = finite_or_zero(*value, name, fixes).clamp(0.0, 1.0);
        if catalog.loaded && *value != 0.0 && !catalog.contains(name) {
            fixes.push(Fix {
                path: name.into(),
                reason: "no está en el catálogo".into(),
            });
            *value = 0.0;
        }
    }
    if catalog.loaded {
        let unknown: Vec<String> = retouch
            .brush
            .keys()
            .filter(|k| !catalog.contains(k))
            .cloned()
            .collect();
        for key in unknown {
            retouch.brush.remove(&key);
            fixes.push(Fix {
                path: format!("retouch.brush.{key}"),
                reason: "no está en el catálogo".into(),
            });
        }
    }
}

fn sanitize_param_map(
    map: &mut BTreeMap<String, BTreeMap<String, f32>>,
    catalog: &Catalog,
    indices: Option<&[u32]>,
    bucket: &str,
    fixes: &mut Vec<Fix>,
) {
    let keys: Vec<String> = map.keys().cloned().collect();
    for key in keys {
        if !key.chars().all(|c| c.is_ascii_digit()) {
            map.remove(&key);
            fixes.push(Fix {
                path: format!("{bucket}.{key}"),
                reason: "índice inválido".into(),
            });
            continue;
        }
        if let Some(allowed) = indices {
            if let Ok(idx) = key.parse::<u32>() {
                if !allowed.contains(&idx) {
                    map.remove(&key);
                    fixes.push(Fix {
                        path: format!("{bucket}.{key}"),
                        reason: "índice ausente en la detección".into(),
                    });
                    continue;
                }
            }
        }
        let Some(params) = map.get_mut(&key) else {
            continue;
        };
        let names: Vec<String> = params.keys().cloned().collect();
        for name in names {
            let raw = params.get(&name).copied().unwrap_or(0.0);
            if !raw.is_finite() {
                log::warn!(target: "sanitize", "{bucket}.{key}.{name} no finito → 0");
                fixes.push(Fix {
                    path: format!("{bucket}.{key}.{name}"),
                    reason: "NaN/inf".into(),
                });
                params.insert(name.clone(), 0.0);
            }
            let value = params.get(&name).copied().unwrap_or(0.0);
            let clamped = match kind_of(&name) {
                Some(Kind::Degree) => value.clamp(0.0, 1.0),
                _ => value.clamp(-1.0, 1.0),
            };
            if catalog.loaded && !catalog.contains(&name) {
                params.remove(&name);
                fixes.push(Fix {
                    path: format!("{bucket}.{key}.{name}"),
                    reason: "no está en el catálogo".into(),
                });
                continue;
            }
            if clamped.abs() < 0.005 {
                params.remove(&name);
            } else {
                params.insert(name, clamped);
            }
        }
        if params.is_empty() {
            map.remove(&key);
        }
    }
}

fn finite_or_zero(v: f32, path: &str, fixes: &mut Vec<Fix>) -> f32 {
    if v.is_finite() {
        v
    } else {
        log::warn!(target: "sanitize", "{path} no finito → 0");
        fixes.push(Fix {
            path: path.into(),
            reason: "NaN/inf".into(),
        });
        0.0
    }
}

fn sanitize_arm_manual(m: &mut ArmManual, path: &str, fixes: &mut Vec<Fix>) {
    m.cx = unit(m.cx, &format!("{path}.cx"), fixes);
    m.cy = unit(m.cy, &format!("{path}.cy"), fixes);
    m.rx = finite_or_zero(m.rx, &format!("{path}.rx"), fixes).clamp(0.01, 0.5);
    m.ry = finite_or_zero(m.ry, &format!("{path}.ry"), fixes).clamp(0.01, 0.5);
    m.angle = finite_or_zero(m.angle, &format!("{path}.angle"), fixes).clamp(-180.0, 180.0);
    m.value = finite_or_zero(m.value, &format!("{path}.value"), fixes).clamp(-1.0, 1.0);
}

fn unit(v: f32, path: &str, fixes: &mut Vec<Fix>) -> f32 {
    finite_or_zero(v, path, fixes).clamp(0.0, 1.0)
}

fn clamp_pts(pts: &mut Vec<[f32; 2]>, path: &str, fixes: &mut Vec<Fix>) {
    for (i, pt) in pts.iter_mut().enumerate() {
        pt[0] = unit(pt[0], &format!("{path}.{i}.x"), fixes);
        pt[1] = unit(pt[1], &format!("{path}.{i}.y"), fixes);
    }
}

fn strip_side(name: &str) -> &str {
    name.strip_prefix("left_")
        .or_else(|| name.strip_prefix("right_"))
        .unwrap_or(name)
}

/// Tope de `k` del liquify (igual que pydantic `Liquify.k le=1.0`).
pub const LIQUIFY_K_MAX: f32 = 1.0;
pub const BRUSH_R_MIN: f32 = 0.01;
pub const BRUSH_R_MAX: f32 = 0.25;

/// Espejo de `brushToStroke` de la UI (ui/js/models/params.js).
/// r = fracción del lado menor (0.01..0.25, lineal con el slider);
/// k = base·(0.2 + 0.8·intensidad/100), base 0.55 suave / 0.9 fuerte.
/// El zoom ya no interviene: el trazo vive en coordenadas de imagen.
pub fn brush_to_stroke(mode: BrushMode, radius_ui: u8, strength_ui: u8, pts: Vec<[f32; 2]>) -> LiquifyStroke {
    let k_base = match mode {
        BrushMode::Suave => 0.55,
        BrushMode::Fuerte => 0.9,
    };
    let r = (BRUSH_R_MIN + (BRUSH_R_MAX - BRUSH_R_MIN) * f32::from(radius_ui.min(100)) / 100.0).clamp(BRUSH_R_MIN, BRUSH_R_MAX);
    let k = (k_base * (0.2 + 0.8 * f32::from(strength_ui.min(100)) / 100.0)).clamp(0.02, LIQUIFY_K_MAX);
    let min_dist = 0.15 * r;
    LiquifyStroke {
        pts: decimate_pts(pts, min_dist),
        k,
        r,
    }
}

fn decimate_pts(pts: Vec<[f32; 2]>, min_dist: f32) -> Vec<[f32; 2]> {
    if pts.len() <= 1 {
        return pts;
    }
    let last_pt = *pts.last().unwrap();
    let mut out = Vec::with_capacity(pts.len());
    out.push(pts[0]);
    for pt in pts.into_iter().skip(1) {
        let last = *out.last().unwrap();
        let dx = pt[0] - last[0];
        let dy = pt[1] - last[1];
        if (dx * dx + dy * dy).sqrt() >= min_dist {
            out.push(pt);
        }
    }
    if out.last() != Some(&last_pt) {
        out.push(last_pt);
    }
    out
}

pub fn apply_param(state: &mut EditState, name: &str, value: f32, target: &Target) -> Result<(), AppError> {
    match kind_of(name) {
        Some(Kind::Degree) => set_retouch(state, name, value),
        Some(Kind::Intensity) => {
            let index = match target {
                Target::Human { human } if name.contains("bodyslim") || name.contains("body") => human.to_string(),
                Target::Face { face } => face.to_string(),
                Target::Human { human } => human.to_string(),
                Target::Global(_) => "0".into(),
            };
            let bucket = if name.contains("facelift_") {
                &mut state.facelift
            } else if name.contains("bodyslim") {
                &mut state.body
            } else {
                &mut state.face
            };
            if value.abs() < 0.005 {
                if let Some(map) = bucket.get_mut(&index) {
                    map.remove(name);
                    if map.is_empty() {
                        bucket.remove(&index);
                    }
                }
            } else {
                bucket.entry(index).or_default().insert(name.to_string(), value);
            }
        }
        None => return Err(AppError::invalid(format!("param desconocido: {name}"))),
    }
    Ok(())
}

fn set_retouch(state: &mut EditState, name: &str, value: f32) {
    let slot = match name {
        "degree_skin_smooth" => &mut state.retouch.degree_skin_smooth,
        "degree_sharpen" => &mut state.retouch.degree_sharpen,
        "degree_whiten_skin" => &mut state.retouch.degree_whiten_skin,
        "degree_skin_details" => &mut state.retouch.degree_skin_details,
        "degree_skin_texture" => &mut state.retouch.degree_skin_texture,
        "degree_skin_matte" => &mut state.retouch.degree_skin_matte,
        "degree_whiten_teeth" => &mut state.retouch.degree_whiten_teeth,
        "degree_brighten_eyes" => &mut state.retouch.degree_brighten_eyes,
        "degree_whiten_eyes" => &mut state.retouch.degree_whiten_eyes,
        "degree_remove_eye_redness" => &mut state.retouch.degree_remove_eye_redness,
        "degree_dark_circles" => &mut state.retouch.degree_dark_circles,
        "degree_remove_blemishes" => &mut state.retouch.degree_remove_blemishes,
        "degree_wrinkles" => &mut state.retouch.degree_wrinkles,
        _ => return,
    };
    *slot = value;
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn arm_manual_strokes_roundtrip_and_limit() {
        let st = |v: f32| serde_json::json!({"cx": 0.5, "cy": 0.5, "rx": 0.06, "ry": 0.14, "angle": 0, "value": v});
        let mut strokes: Vec<serde_json::Value> = (0..40).map(|_| st(0.3)).collect();
        strokes.push(st(0.0));
        let mut state: EditState = serde_json::from_value(serde_json::json!({
            "arm": {"manual": st(0.0), "manual_strokes": strokes}
        })).expect("manual_strokes debe deserializar");
        let fixes = sanitize_with_indices(&mut state, &Catalog::default(), None, None);
        assert_eq!(state.arm.manual_strokes.len(), ARM_MAX_STROKES);
        assert!(fixes.iter().any(|f| f.path == "arm.manual_strokes"));
        let out = serde_json::to_value(&state).unwrap();
        assert_eq!(out["arm"]["manual_strokes"].as_array().unwrap().len(), ARM_MAX_STROKES);
        // Sin trazos, la clave no se serializa (motor viejo no la ve).
        let empty: EditState = serde_json::from_value(serde_json::json!({"arm": {"manual": st(0.2)}})).unwrap();
        assert!(serde_json::to_value(&empty).unwrap()["arm"].get("manual_strokes").is_none());
    }

    #[test]
    fn intensity_and_degree_conversion() {
        assert_eq!(ui_to_intensity(150), 1.0);
        assert_eq!(ui_to_intensity(-37), -0.37);
        assert_eq!(ui_to_degree(150), 1.0);
        assert_eq!(ui_to_degree(-4), 0.0);
    }

    #[test]
    fn kind_prefixes() {
        assert_eq!(kind_of("intensity_jaw"), Some(Kind::Intensity));
        assert_eq!(kind_of("left_intensity_eyesize"), Some(Kind::Intensity));
        assert_eq!(kind_of("right_intensity_eyesize"), Some(Kind::Intensity));
        assert_eq!(kind_of("up_intensity_mouththickness"), Some(Kind::Intensity));
        assert_eq!(kind_of("down_intensity_mouththickness"), Some(Kind::Intensity));
        assert_eq!(kind_of("degree_skin_smooth"), Some(Kind::Degree));
        assert_eq!(kind_of("foo"), None);
    }

    #[test]
    fn sanitize_nan_unknown_and_band() {
        let catalog = Catalog::from_items(vec![CatalogItem {
            name: "intensity_jaw".into(),
            ..CatalogItem::empty()
        }]);
        let mut state = EditState::new();
        state.face.insert(
            "0".into(),
            BTreeMap::from([
                ("intensity_jaw".into(), f32::NAN),
                ("intensity_unknown".into(), 0.4),
            ]),
        );
        state.height = Some(Height {
            band: [0.9, 0.2],
            value: 0.1,
            keep_canvas: false,
            y_start: None,
            y_end: None,
        });
        state.liquify.push(LiquifyStroke {
            pts: vec![[-0.2, 1.4], [0.3, 0.3]],
            k: 0.1,
            r: 0.05,
        });
        let fixes = sanitize(&mut state, &catalog);
        assert!(fixes.iter().any(|f| f.reason.contains("NaN")));
        assert!(state.face.get("0").is_none() || !state.face["0"].contains_key("intensity_unknown"));
        let band = state.height.unwrap().band;
        assert!(band[0] <= band[1]);
        assert!(band[1] - band[0] >= 0.02 - 1e-5);
        assert_eq!(state.liquify[0].pts[0][0], 0.0);
        assert_eq!(state.liquify[0].pts[0][1], 1.0);
    }

    #[test]
    fn brush_mapping_matches_ui() {
        // Mismos números que brushToStroke() en ui/js/models/params.js.
        let stroke = brush_to_stroke(BrushMode::Suave, 50, 50, vec![[0.1, 0.1], [0.2, 0.2]]);
        assert!((stroke.k - 0.33).abs() < 1e-6);
        assert!((stroke.r - 0.13).abs() < 1e-6);
        let strong = brush_to_stroke(BrushMode::Fuerte, 100, 100, vec![[0.1, 0.1], [0.2, 0.2]]);
        assert!((strong.k - 0.9).abs() < 1e-6);
        assert!((strong.r - 0.25).abs() < 1e-6);
    }

    #[test]
    fn liquify_k_up_to_one_survives_sanitize() {
        let catalog = Catalog::from_items(vec![]);
        let mut state = EditState::new();
        state.liquify.push(LiquifyStroke { pts: vec![[0.4, 0.5], [0.45, 0.5]], k: 0.95, r: 0.1 });
        state.liquify.push(LiquifyStroke { pts: vec![[0.4, 0.5], [0.45, 0.5]], k: 3.0, r: 0.1 });
        sanitize(&mut state, &catalog);
        assert!((state.liquify[0].k - 0.95).abs() < 1e-6);
        assert!((state.liquify[1].k - LIQUIFY_K_MAX).abs() < 1e-6);
    }

    #[test]
    fn height_lines_contract() {
        // Línea arrastrada: estirar solo por debajo de y=0.6.
        let json = r#"{"value":0.4,"y_start":0.6,"y_end":1.0}"#;
        let h: Height = serde_json::from_str(json).unwrap();
        assert_eq!(h.band, [0.48, 0.92]);
        let mut state = EditState::new();
        state.height = Some(h);
        sanitize(&mut state, &Catalog::from_items(vec![]));
        let h = state.height.clone().unwrap();
        assert_eq!(h.band, [0.6, 1.0]);
        assert_eq!(h.y_start, Some(0.6));
        assert_eq!(h.y_end, Some(1.0));
        // Invertidas y fuera de rango se ordenan/clampean.
        state.height = Some(Height { band: [0.48, 0.92], value: 0.2, keep_canvas: false, y_start: Some(1.4), y_end: Some(0.3) });
        sanitize(&mut state, &Catalog::from_items(vec![]));
        let h = state.height.unwrap();
        assert_eq!(h.band, [0.3, 1.0]);
        // Serializa y_start/y_end (el motor los recibe).
        let out = serde_json::to_value(&EditState { height: Some(Height { band: [0.0, 0.5], value: 0.1, keep_canvas: false, y_start: Some(0.0), y_end: Some(0.5) }), ..EditState::new() }).unwrap();
        assert_eq!(out["height"]["y_end"], serde_json::json!(0.5));
        // Estado viejo sin y_*: no los emite.
        let old: Height = serde_json::from_str(r#"{"band":[0.2,0.8],"value":0.1}"#).unwrap();
        assert!(serde_json::to_value(&old).unwrap().get("y_start").is_none());
    }

    #[test]
    fn muscle_roundtrip_and_skip_empty() {
        let json = r#"{"schema":1,"muscle":{"0":{"mode":"man_abs","strength":0.6,"definition":0.6,"warp":0.3,"light":"auto","gloss":0.0,"brush":{"strokes":[{"pts":[[0.4,0.5],[0.41,0.51]],"radius":0.04,"erase":true}]}}}}"#;
        let state: EditState = serde_json::from_str(json).unwrap();
        assert_eq!(state.muscle["0"].mode, "man_abs");
        assert!((state.muscle["0"].strength - 0.6).abs() < 1e-6);
        assert_eq!(state.muscle["0"].brush.strokes.len(), 1);
        let out = serde_json::to_value(&state).unwrap();
        assert_eq!(out["muscle"]["0"]["mode"], "man_abs");
        assert!(out.get("makeup").is_none());
        let empty = serde_json::to_value(EditState::new()).unwrap();
        assert!(empty.get("muscle").is_none());
        assert!(serde_json::from_str::<Retouch>(r#"{"degree_skin_smooth":0,"unknown_key":1}"#).is_err());
    }

    #[test]
    fn freeze_rects_invert_feather() {
        let json = r#"{"strokes":[{"pts":[[0.5,0.5]],"radius":0.5}],"rects":[{"x":0.1,"y":0.2,"w":0.3,"h":0.4,"erase":true},{"x":-1,"y":0.2,"w":5,"h":0.4}],"invert":true,"feather":0.9}"#;
        let fz: Freeze = serde_json::from_str(json).unwrap();
        let mut state = EditState::new();
        state.freeze = fz;
        sanitize(&mut state, &Catalog::from_items(vec![]));
        assert_eq!(state.freeze.strokes[0].radius, 0.5);
        assert_eq!(state.freeze.rects.len(), 2);
        assert!(state.freeze.rects[0].erase);
        assert_eq!(state.freeze.rects[1].x, 0.0);
        assert_eq!(state.freeze.rects[1].w, 1.0);
        assert!(state.freeze.invert);
        assert!((state.freeze.feather - 0.25).abs() < 1e-6);
        // Campos desconocidos siguen rechazados.
        assert!(serde_json::from_str::<Freeze>(r#"{"strokes":[],"lasso":[]}"#).is_err());
        // Freeze vacío serializa igual que antes (sin rects/invert/feather).
        let v = serde_json::to_value(Freeze::default()).unwrap();
        assert_eq!(v, serde_json::json!({"strokes": []}));
    }

    impl CatalogItem {
        fn empty() -> Self {
            Self {
                name: String::new(),
                label_es: String::new(),
                tab: String::new(),
                kind: String::new(),
                range: vec![],
                lr: false,
                status: String::new(),
                phase: 0,
                group: String::new(),
            }
        }
    }
}
