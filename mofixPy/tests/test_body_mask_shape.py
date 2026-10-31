import numpy as np
from PIL import Image
from conftest import make_face
from morfofix_engine.body.slim import body_field
from morfofix_engine.face.landmark_map import synthetic_landmarks
from morfofix_engine.inference.pose import Body, _as_2d_mask

def _kp():
    kp = np.zeros((33, 4), np.float32); kp[:, 3] = 1
    kp[:11, :2] = (.5, .15); kp[11, :2] = (.62, .35); kp[12, :2] = (.38, .35)
    kp[23, :2] = (.58, .75); kp[24, :2] = (.42, .75)
    return kp

def _session(client, app, tmp_path):
    p = tmp_path / "x.png"; Image.fromarray(np.full((500, 400, 3), 120, np.uint8)).save(p)
    sid = client.post('/session', json={'path': str(p)}).json()['session_id']
    return sid, app.state.store.get(sid)

def test_as_2d_mask_squeezes_mediapipe_channel():
    assert _as_2d_mask(np.ones((7, 5, 1), np.float32)).shape == (7, 5)

def test_body_field_accepts_hw1_mask():
    h, w, p = 200, 150, {'0': {'intensity_bodyslim_waistthin': .3}}
    a = body_field(h, w, [Body(0, (.3, .1, .7, .9), 1., _kp(), np.ones((h, w, 1), np.float32))], p)
    b = body_field(h, w, [Body(0, (.3, .1, .7, .9), 1., _kp(), np.ones((h, w), np.float32))], p)
    assert np.allclose(a.dx, b.dx) and np.allclose(a.dy, b.dy)

def test_render_face_plus_body_with_hw1_mask(client, app, tmp_path):
    sid, sess = _session(client, app, tmp_path)
    sess.faces = [make_face(synthetic_landmarks(400, 500))]
    sess.bodies = [Body(0, (.3, .1, .7, .9), 1., _kp(), np.ones((500, 400, 1), np.float32))]
    r = client.post(f'/session/{sid}/render', json={'state': {
        'face': {'0': {'intensity_jaw': .5}}, 'body': {'0': {'intensity_bodyslim_waistthin': .3}}}})
    assert r.status_code == 200, r.text

def test_1d_keypoints_return_422_not_500(client, app, tmp_path):
    sid, sess = _session(client, app, tmp_path)
    sess.bodies = [Body(0, (0, 0, 1, 1), 0., np.zeros((0,), np.float32), None)]
    r = client.post(f'/session/{sid}/render', json={'state': {'body': {'0': {'intensity_bodyslim_waistthin': .3}}}})
    assert r.status_code == 200, r.text
    assert "NO_BODY:0" in r.headers.get("X-Warnings", "")
