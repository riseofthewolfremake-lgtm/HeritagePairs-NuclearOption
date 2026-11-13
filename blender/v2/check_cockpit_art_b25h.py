"""B-25H cockpit check 7 (2026-11-01 v3), run OUTSIDE Blender (Blender's Python has no PIL):

  python blender/v2/check_cockpit_art_b25h.py <b25h_cockpit_check.json>

The fal panel art must show a dark hole under every real dial: the art pixel at each dial centre (through the measured fit
b25h_cockpit_layout.PF_*) is dark, and the dark disc there is at least as wide as the dial face, so no painted instrument
sits under a real one. Adds its row to the json written by check_cockpit_b25h.py; exit code 1 if any check in the json fails.
"""
import os, sys, json
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import b25h_cockpit_layout as LY

out = sys.argv[1]
res = json.load(open(out)) if os.path.exists(out) else {}
im = np.asarray(Image.open(os.path.join(HERE, '..', '..', 'assets', 'textures_v2', 'fal_raw_cockpit_b25h', LY.PANELS['panel'][1])).convert('L')).astype(int)
H, W = im.shape
bad, rows = [], []
for gid, x, z, r in LY.REAL:
    u, v = LY.PF_A * x + LY.PF_B, LY.PF_C * z + LY.PF_D
    px = im[int(v), int(u)]
    rp = r * LY.PF_A
    ys, xs = np.mgrid[-int(rp):int(rp) + 1, -int(rp):int(rp) + 1]
    inside = xs ** 2 + ys ** 2 <= (0.8 * rp) ** 2
    patch = im[np.clip(int(v) + ys, 0, H - 1), np.clip(int(u) + xs, 0, W - 1)]
    dark = float((patch[inside] < 40).mean())
    rows.append((gid, int(px), round(dark, 2)))
    if px > 60 or dark < 0.85:
        bad.append((gid, int(px), round(dark, 2)))
name = 'panel art: a dark hole under every real dial (centre pixel dark, >= 85 % dark within 0.8 r)'
res[name] = dict(ok=not bad, detail=json.dumps(dict(bad=bad, dials=rows))[:600])
print(('PASS ' if not bad else 'FAIL ') + name, res[name]['detail'][:300])
json.dump(res, open(out, 'w'), indent=1)
fails = [k for k, v in res.items() if not v['ok']]
print(f'[cockpit check] {len(res) - len(fails)}/{len(res)} PASS')
sys.exit(1 if fails else 0)
