# Licencias de modelos

Los binarios no se versionan. Bajalos con `python scripts/fetch_models.py`.

Verificá cada model card antes de distribuir (las URLs están también en `DISENOS-PROPIOS.md` §11).

| Modelo | Licencia esperada | Notas |
|---|---|---|
| face_landmarker.task | Apache-2.0 (MediaPipe) | FaceDetector / FaceMesh-V2 |
| pose_landmarker_full.task | Apache-2.0 | BlazePose GHUM |
| selfie_segmenter.tflite | ver model card | |

No se incluyen BiSeNet face-parsing ni LaMa: pesos públicos suelen tener restricciones (CelebAMask-HQ no comercial).
