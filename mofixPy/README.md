# mofixPy — motor Python de MorfoFix

Sidecar FastAPI de procesamiento local de imágenes. Rust controla el proceso y guarda el historial; Python recibe un `EditState` completo y devuelve una imagen. No descarga recursos ni realiza conexiones externas durante el uso.

Los diseños propios están integrados. Consultá [DISENOS-PROPIOS.md](DISENOS-PROPIOS.md) para conocer la cobertura, las decisiones de implementación y las limitaciones de validación.

## Instalación

Python ≥3.12. Se recomienda un entorno Python 3.12 para instalar el extra de visión según la disponibilidad de MediaPipe para la plataforma.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,vision]"
```

Para trabajar sin modelos, alcanza `pip install -e ".[dev]"`. Identidad, geometría, HSL, manipuladores, liquify, freeze, remove y exportación funcionan sin inferencia.

## Modelos

El manifiesto incluye cara, pose, Selfie Segmenter y Selfie Multiclass. Los pesos no están incluidos. El runtime solo carga archivos locales con un SHA256 fijado y coincidente.

Descarga inicial explícita desde las URLs del manifiesto:

```bash
python scripts/fetch_models.py --record-hashes
```

Este comando registra el hash de lo descargado; no implica una verificación independiente de su procedencia. Revisá y conservá el manifiesto resultante. Las descargas posteriores verifican esos hashes antes de reemplazar archivos:

```bash
python scripts/fetch_models.py
# Un modelo concreto:
python scripts/fetch_models.py --only face_landmarker
```

BiSeNet y LaMa siguen siendo opcionales y no están empaquetados. No se atribuyen licencias a pesos no revisados.

## Arranque desde Rust

Rust debe generar un token nuevo y pasarlo por entorno, mantener stdin del hijo abierto y leer stdout:

```text
python -m morfofix_engine --host 127.0.0.1 --port 0 \
  --token-env MORFOFIX_TOKEN --models-dir models --cache-dir .cache/engine
```

La variable `MORFOFIX_TOKEN` debe existir antes del arranque. Nunca se recibe el secreto como argumento. Con el servidor listo, stdout entrega:

```text
MORFOFIX_READY {"port":53121,"pid":4242,"version":"0.1.0","api":"v0"}
```

El puerto y PID varían por ejecución. Los logs JSON van a stderr. `POST /shutdown` solicita cierre ordenado; cerrar stdin también detiene el motor.

## API v0

Todas las rutas salvo `GET /health` requieren `Authorization: Bearer <token>`. Host debe ser `127.0.0.1:<puerto>` o `localhost:<puerto>`. No hay permisos CORS para acceder desde una web.

| Ruta | Uso |
|---|---|
| `GET /health` | Estado, modelos y sesiones |
| `POST /session` | Abrir `{"path":"/ruta/absoluta/foto.png"}` o upload multipart `file` |
| `POST /session/{id}/detect` | `{"what":["face","pose","person_mask"]}` |
| `POST /session/{id}/render` | Estado completo, revisión y JPEG de salida |
| `POST /session/{id}/params` | Atajo para cambiar un parámetro del último estado recibido |
| `POST /session/{id}/export` | Estado completo y destino PNG/JPEG/WEBP/TIFF |
| `GET /session/{id}/landmarks` | Puntos normalizados para diagnóstico |
| `DELETE /session/{id}` | Cerrar la sesión |
| `GET /catalog` | Parámetros disponibles, rangos y estado |
| `POST /shutdown` | Cierre del proceso |

Ejemplo de cuerpo de render, tras detectar una cara:

```json
{
  "rev": 1,
  "state": {"schema":1,"face":{"0":{"intensity_jaw":0.4}}},
  "target":"preview",
  "max_side":1600,
  "quality":85,
  "overlay":null
}
```

Respuesta: JPEG y headers `X-Rev`, `X-Render-Ms`, `X-Warnings`. `overlay` admite `landmarks`, `pose`, `mesh` y `freeze`. Un estado `{}` restablece todos los ajustes: no conserva parámetros de renders anteriores. Si se omite `rev`, se asigna la siguiente revisión para facilitar pruebas manuales; Rust debe enviar revisiones explícitas y crecientes.

Exportación:

```json
{
  "state":{"schema":1,"photo":{"hsl":{"saturation":0.15}}},
  "path":"/ruta/absoluta/salida.png",
  "format":"png",
  "quality":92,
  "keep_metadata":true,
  "keep_gps":false
}
```

HSL usa valores −1…1. Las coordenadas de edición están normalizadas. Los errores tienen la forma `{"error":{"code":"BAD_PARAM","message":"…","detail":{}}}`. No se clampa silenciosamente la entrada: los valores fuera de rango se rechazan.

`create_app(token=None, port=None)` está disponible para pruebas embebidas; el CLI siempre exige token y valida el puerto de Host.

## Verificación

```bash
pytest -q
python scripts/bench_render.py
```

Las pruebas usan imágenes y landmarks sintéticos, y dos pruebas levantan un servidor real solo en loopback. No requieren internet ni pesos de modelos. La calidad de detección con fotografías reales requiere instalar MediaPipe y los modelos.

La caché tiene límites de RAM y disco. Guarda inferencia en NPZ sin pickle y conserva renders y prefijos de inpaint en RAM. Es local y puede contener datos derivados de las fotos; se puede borrar su directorio con el motor detenido.
