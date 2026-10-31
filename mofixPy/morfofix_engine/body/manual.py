"""User-positioned shapes in normalized post-geometry coordinates."""
import numpy as np
from morfofix_engine.warps.field import Field, compose, identity

SHAPES = {"WaistThin_Rect", "HipBeauty_Rect", "Slim_Circle", "Enlarge_Circle", "Shrink_Circle", "LegThin_Rect", "ArmThin_Rect", "HipBeauty_Circle", "BellyThin_Circle", "BreastEnlarge_Circle", "FaceThin_Circle", "Stretch_Rect"}


def manual_field(h, w, shapes):
    result = identity(h, w)
    gy, gx = np.indices((h, w), dtype=np.float32)
    for s in shapes:
        angle = np.deg2rad(s.angle)
        c, sn = float(np.cos(angle)), float(np.sin(angle))
        x, y = gx-s.cx*(w-1), gy-s.cy*(h-1)
        u, v = c*x+sn*y, -sn*x+c*y
        rx, ry = max(s.w*w/2, 1), max(s.h*h/2, 1)
        nx, ny = u/rx, v/ry
        edge = max(s.feather, .001)
        if s.type.endswith("Circle"):
            q = nx*nx+ny*ny
            t = np.maximum(0, 1-q)**2
            a = .25*s.value*(-1 if s.type in {"Slim_Circle", "Shrink_Circle", "BellyThin_Circle", "FaceThin_Circle"} else 1)
            du, dv = -a*u*t, -a*v*t
        elif s.type == "Stretch_Rect":
            # Análogo vertical de WaistThin_Rect (flechas ↑/↓ del manipulador):
            # value > 0 comprime en alto, value < 0 estira, con transición en los bordes de arriba/abajo.
            window = (np.abs(nx)<1)*(np.abs(ny)<1)
            fade = np.clip((1-np.abs(ny))/edge, 0, 1)
            fade = fade*fade*(3-2*fade)
            gain = .5*(1+np.cos(np.pi*np.clip(nx, -1, 1)))
            dv = v*.18*s.value*gain*fade*window
            du = np.zeros_like(dv)
        else:
            window = (np.abs(nx)<1)*(np.abs(ny)<1)
            fade = np.clip((1-np.abs(nx))/edge, 0, 1)
            fade = fade*fade*(3-2*fade)
            gain = .5*(1+np.cos(np.pi*np.clip(ny, -1, 1)))
            du = u*.18*s.value*gain*fade*window
            if s.type == "HipBeauty_Rect":
                du *= -np.clip(ny+0.5, 0, 1)
            dv = np.zeros_like(du)
        if not s.symmetric:
            du, dv = du*(u>=0), dv*(u>=0)
        f = Field((c*du-sn*dv).astype(np.float32), (sn*du+c*dv).astype(np.float32))
        result = compose(f, result)
    return result
