"""Smooth band stretching, represented as a backward field."""
import numpy as np
from morfofix_engine.warps.field import from_maps


def height_field(h, w, band, value, keep_canvas=False):
    a, b = np.array(band)*h
    scale = 1 + .30*value
    length = b-a
    out_h = max(1, round(h + length*(scale-1)))
    # Integrate a smooth local scale around both band boundaries.
    src = np.linspace(0, h, max(1025, h+1))
    feather = max(.04*h, 1e-6)
    def smooth(t):
        t = np.clip(t, 0, 1)
        return t*t*(3-2*t)
    # Si la banda toca un borde (línea "solo debajo"/"solo encima"), ese lado
    # no lleva transición: estira de forma pareja hasta el borde.
    lo = np.ones_like(src) if a <= 0 else smooth((src-a)/feather+.5)
    hi = np.ones_like(src) if b >= h else smooth((b-src)/feather+.5)
    weight = lo*hi
    integral = np.concatenate(([0.], np.cumsum((weight[1:]+weight[:-1])*.5*np.diff(src))))
    if integral[-1] > 0:
        integral *= length/integral[-1]
    dest = src + (scale-1)*integral
    output = h if keep_canvas else out_h
    ys = np.linspace(0, dest[-1]-1, output) if keep_canvas else np.arange(output)
    mapped = np.interp(ys, dest, src).astype(np.float32)
    x = np.broadcast_to(np.arange(w, dtype=np.float32), (output, w)).copy()
    y = np.broadcast_to(mapped[:, None], (output, w)).copy()
    return from_maps(x, y)
