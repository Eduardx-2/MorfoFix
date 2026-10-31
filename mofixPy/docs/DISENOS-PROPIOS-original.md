# Diseños propios — no implementados en `mofixPy`

Extracto de `informes/14-funciones-python.md`. Marca **[propio]**: no salió del reversing. Este archivo es la única copia operativa; el motor Python **no** ejecuta estas fórmulas.

---

## 1.2 Estado declarativo **[propio]**

El motor **no guarda historial**. Recibe siempre el **estado completo de edición** (`EditState`) y lo renderiza de forma determinista. Rust guarda la pila de undo/redo como lista de `EditState`.

- Undo = Rust manda el estado anterior. El motor no se entera de que fue un undo.
- Un crash del sidecar no pierde trabajo: Rust re-crea la sesión y reenvía el último estado.
- Todo lo pesado que se deriva del estado se **cachea por clave de contenido**.

InShot guarda el historial *en* el motor (`body_undo`, `body_redo`, …). Este diseño lo saca afuera a propósito.

## 1.3 Orden del pipeline compuesto **[propio, con pistas RE]**

Strings del SDK (`RenderAfterMakeupBeforeLiquify`, `RenderLiquify`, `RenderAfterLiquify`) sugieren color **antes** del liquify. Diseño propio: **un solo remap** con campo compuesto

`height ∘ liquify ∘ manual_shapes ∘ body ∘ face`

más `bg_protect` por placa inpaint. El prototipo ya hace un remap MLS para cara; extenderlo a todo el pipeline es decisión nuestra.

## 2. Contrato API v0 — JSON exacto **[propio]** (salvo nombres EffectSDK)

Rutas concretas, campos, códigos HTTP, `--port 0` + línea `MORFOFIX_READY`, token por `--token-env`, Host 421, CORS off, `EditState` schema 1, `rev` / `409 STALE_REV`, `overlay`, concurrencia “latest wins” con `ThreadPoolExecutor(max_workers=1)`.

Valores `degree_*` en **[0, 1]** unipolar (UI 0…100) es **[propio]** (los nombres `degree_*` sí son [RE]).

### EditState (no usado por el sidecar actual)

```json
{
  "schema": 1,
  "face": {"0": {"intensity_jaw": 0.32, "left_intensity_eyesize": 0.05}},
  "facelift": {"0": {"intensity_facelift_contour": 0.4}},
  "body": {"0": {"intensity_bodyslim_waistthin": 0.4}},
  "body_options": {"bg_protect": true, "head_protect": true},
  "height": {"band": [0.48, 0.92], "value": 0.25, "keep_canvas": false},
  "liquify": [{"pts": [[0.41,0.55],[0.42,0.55]], "k": 0.15, "r": 0.03}],
  "manual_shapes": [{"type": "WaistThin_Rect", "cx": 0.5, "cy": 0.6, "w": 0.3, "h": 0.12, "angle": 0, "value": 0.35, "feather": 0.5, "symmetric": true}],
  "freeze": {"strokes": [{"pts": [[0.3,0.2]], "radius": 0.02, "erase": false}]},
  "retouch": {"degree_skin_smooth": 0.5, "brush": {"degree_skin_smooth": {"strokes": []}}},
  "remove": [{"strokes": [{"pts": [[0.6,0.3]], "radius": 0.015}], "method": "telea"}],
  "photo": {"crop": [0,0,1,1], "rotate_deg": 0, "flip_h": false, "hsl": {"hue": 0, "saturation": 0, "lightness": 0}}
}
```

Códigos: `BAD_PARAM`, `UNAUTHORIZED`, `NO_SESSION`, `STALE_REV`, `UNSUPPORTED_IMAGE`, `NO_FACE`/`NO_BODY`, `MODEL_MISSING`, `INTERNAL`+`trace_id`.

### 2.5 Concurrencia **[propio]**

Un executor de 1 worker. Si llega `rev=19` con `18` en cola, el 18 responde 409 y el 19 sustituye. El render en curso no se interrumpe; al terminar, si el `rev` ya es viejo → 409.

---

## 3. Inferencia — detalles de implementación **[propio]**

### Cara (MediaPipe)

- `RunningMode.IMAGE`, `output_facial_transformation_matrixes=True`, blendshapes OFF.
- `euler` por descomposición R de la matriz 4×4.
- Copia de trabajo lado mayor ≤ 2048 px.
- **Rescate de caras chicas:** recorte de cabeza (pose 0–10 + margen 60 %) o tiles 2×2 con 15 % de solape y NMS IoU 0.4.

### Pose — zonas interpoladas **[propio]**

| Zona | Fórmula |
|---|---|
| neck | punto medio 11–12 ↔ 0 |
| waist | `lerp(mid(11,12), mid(23,24), 0.62)` — calibrar |
| belly | lerp 0.80 |
| chest/breast L/R | lerp 0.28 ± 0.22·ancho de hombros |

### Segmentación **[propio]**

Selfie Segmenter / Multiclass 256²; upsample + **guided filter propio** (`cv2.boxFilter`). F4 face parsing BiSeNet: **ojo licencia** (pesos CelebAMask-HQ suelen ser no comerciales).

### 3.5 Cache `InferenceCache` **[propio]**

Clave `(image_sha1, geom_hash, kind, model_sha256, params)`. LRU RAM + `.npz` en disco. Rotación 90°/flip transforma landmarks; rotación libre re-infiere. Máx 100 MP → 415.

---

## 4. Rostro — lo no confirmado

### Multi-cara un MLS **[propio]**

Todos los controles de todas las caras al **mismo** MLS; caras sin params aportan FACE_OVAL fijo.

### Campo MLS para pipeline **[propio]**

`mls_backward_field(h, w, src, dst, grid_step) -> (dx, dy)` para componer un remap global.

### Columna “deformación” de sliders no-[proto] **[propio]**

Toda deformación fuera de las 9 filas [proto] (jaw, jawline_1, facev, facewidth, facelength, eyesize, eyedistance, mouthsize, nosesize): facesmall, headsmall, cheekbone, temple, hairline, faceresize, doublechin, eyewidth/height/tilt/tail/under/pupil/inner/outer/position/smiley, mouthwidth/height/thickness/up/down/smile/mshape/slant, nosetip/lift/bridge/root/philtrum, brows (salvo que se marquen proto), ratio, 3D, crown.

Modos nuevos: `translate`, `rotate` (±8°), `aniso`, `corner`; perfil `upper`.

Índices temple/cheekbone/laterales de puente: calibrar con overlays; hasta entonces `planned`.

### L/R **[propio]**

Si vienen `intensity_X` y `left_intensity_X`, se **suman** y se clampa a [−1,1] en el lado izquierdo del sujeto. Cómo combinaba InShot **no está confirmado**.

### Facelift **[propio]**

Por zona: desplazamiento 4–8 px a v=1, falloff `(1−r/R)²`, suavizado HF + aclarado, máscara de piel. ROIs: eye_area, brow_peak, face_mid, contour=JAWLINE, forehead, mouth_area.

### Papada **[propio]**

Franja submentoniana = JAWLINE bajada `0.18·half_len`; MLS local + inpaint Telea radio 5; `mix(original, corregida, v · feather)`. LaMa opcional F4+.

### Ojos brighten / redness **[propio]**

ROI contorno de ojo; iris = 468/473 + radio 469–472. Brighten: `L' = L + k·(255−L)·0.25` en iris+esclera. Redness: desaturar hue ∈ [−20°, 20°] en esclera.

---

## 5. Warps

### Mapeo pincel UI → (k, R) **[propio]**

El original solo tiene dos presets + zoom. MorfoFix añade radio/intensidad 0…100:

```
k_base, R_base = (0.15, 0.03) suave | (0.30, 0.10) fuerte   ← eso SÍ es RE
R = R_base · 2^((radius − 50) / 25) / zoom
k = k_base · strength / 50   clamp k ≤ 0.6
```

La conversión la haría UI/Rust. El motor actual espera `k`/`r` ya resueltos (presets RE).

`mesh_backward_field`, vectorizar miles de strokes, `numba`: **[propio]**.

Freeze en malla con `w *= (1 − frozen)` feather: **[propio, inspirado en RE]**. El código implementa vértices frozen inmóviles ([RE]), no la atenuación suave de campo.

### 5.3 `warps/field.py` **[propio]** (módulo no creado)

```
Field(dx, dy)
identity, compose(outer, inner), attenuate(f, mask), to_maps
radial_push, local_scale  # r_src = r · (1 − a·(1 − (r/R)²)²)
```

Orden: `height ∘ liquify ∘ manual_shapes ∘ body ∘ face`.

---

## 6. Cuerpo — algoritmos **[propio]**

### Slim por partes

Contorno por escaneo N=12 sobre `person_mask`; anchos estimados 0.18/0.12/0.35; `dst = src + v·s·(eje−src)`; anillo 1.6×; un MLS para todas las personas.

`intensity_bodyslim` global = multiplicador de todos los params **[propio]**.

Fuerzas iniciales **[propio]:** 0.18 cintura/piernas/brazos/cuello, 0.12 cadera/hombros, 0.25 busto/abdomen.

Deformaciones por param (bellythin `local_scale`, hiplift −y, leglong = height auto, shoulderbroad, shoulderrightangle, neckswan, breastenlarge, headsmall, …): interpretación nuestra; nombres [RE].

### Manipulador `manual_shapes` **[propio]**

Geometría de shaders cifrada. Diseño: Rect `dx_src = x·v·s·g(y)` ventana coseno; Circle `local_scale`; HipBeauty_Rect ensancha mitad inferior; `symmetric`.

### Height **[propio]**

El `stretch_vs.glsl` es passthrough; la malla de bandas Java no está documentada.

```
s = 1 + 0.30 · value
h_out = h + L·(s − 1)
y_src piecewise lineal + smoothstep feather 0.04·h
keep_canvas reescala a h
```

### Freeze por campo **[propio]**

Además de vértices 126² ([RE]), atenuar el campo compuesto `F *= (1 − mask)` en vez de `mix(orig, warped)` para evitar fantasmas. Máscara de referencia 1001². El motor actual usa **solo** `mix` [RE].

---

## 7. Protect **[propio]**

### Head protect

Elipse en caja de cabeza ×1.3, feather 15 %; `attenuate(body_field, head_mask)` solo sobre cuerpo.

### Background protect

```
M = refine_mask(person)
plate = inpaint(img, dilate(M, 12px))   # Telea ≤1024
W = remap(img, F); Mw = remap(M, F)
out = Mw·W + (1−Mw)·plate
```

Variante barata: `F *= 1 − dilate(M)` fuera de la persona. InShot la máscara era **remota**.

---

## 8. Retoque — algoritmos **[propio]**

### Piel (estructura RE, fórmulas nuestras)

guided_filter `r = max(2, 0.006·min(h,w))`, `eps = (0.02·255)²`; high = img − gaussian σ=1.5; k por varianza local; whiten LAB `L' = L + whiten·(100−L)·0.15·mask`. El motor implementa **solo** blur radio 1.5 y `amount = sharpen·0.6+0.11` ([RE]).

### Dientes **[propio]**

ROI `LIPS_INNER`; dientes = L > p40 ∩ sat < 0.45; `b' = b − amount·max(b,0)·0.6`, `L' = L + amount·(100−L)·0.12`. La regla “foto casi gris” (>50 % sat ≤10 % en mini 100 px) sí es [RE].

### Blemish / arrugas / ojeras **[propio]**

DoG → blobs 2–12 px → Telea; frequency sep. en frente/patas/surcos; ojeras = igualar L a la mejilla.

### Inpaint exemplar (Criminisi) **[propio]** F4; LaMa ONNX F4+.

### Metadata export **[propio]**

Orientation=1, sin thumbnail, ICC, `keep_gps` default false, 100 MP, escritura atómica tmp+fsync+replace, 16 bit → 8 con warning.

### Preview timings **[propio]**

≤120 ms slider cara 1600 px; ≤250 ms cuerpo+bg_protect. Rust bajaría `max_side` a 1200 al arrastrar.

---

## 11. Modelos — URLs **[propio, verificar al bajar]**

| Clave | Archivo | URL (patrón público MediaPipe) | Fase |
|---|---|---|---|
| face_landmarker | `face_landmarker.task` | `https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task` | F1 |
| pose_landmarker_full | `pose_landmarker_full.task` | `https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/1/pose_landmarker_full.task` | F2 |
| selfie_segmenter | `selfie_segmenter.tflite` | `…/image_segmenter/selfie_segmenter/float16/latest/selfie_segmenter.tflite` | F2 |
| selfie_multiclass | `selfie_multiclass_256x256.tflite` | `…/image_segmenter/selfie_multiclass_256x256/float32/latest/…` | F4 |
| face_parsing / lama | opcional | **no empaquetar** sin revisar licencia de pesos | F4 |

Runtime **nunca** descarga. Solo `scripts/fetch_models.py`.

---

## Pendientes honestos (14 §14)

- Calibración de `strength` / `s_param` / cintura-busto-abdomen: toda **[propio]**.
- Semántica fina (eyesmiley, mouthmshape, shoulderrightangle, neckswan, hiplift): nombres [RE], efecto interpretado.
- Combinación `intensity_X` + `left_`/`right_`: no confirmada; el diseño propio suma.
- Geometría de bandas Height: propia.
- Índices `*_index` de bodyslim: desconocidos; tabla MP 33 propia.
- Licencias de model cards: verificar antes de distribuir.
