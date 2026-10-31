# Licencias de modelos y runtime — MorfoFix

MorfoFix no incluye modelos ni código de InShot. Los pesos se descargan
aparte (`mofixPy/scripts/fetch_models.py`) y se verifican por SHA-256.

Consultá `mofixPy/models/manifest.json` para la lista concreta empaquetada
en esta instalación. Las licencias típicas de los reemplazos abiertos:

- MediaPipe Face/Pose Landmarker — Apache License 2.0 (Google)
- Selfie segmentation / multiclass — Apache License 2.0
- ONNX Runtime (si se usa) — MIT
- OpenCV — Apache License 2.0
- NumPy, Pillow, FastAPI, Uvicorn — BSD / MIT / BSD

Nada de esto sale de la máquina: el motor solo escucha en `127.0.0.1`.
