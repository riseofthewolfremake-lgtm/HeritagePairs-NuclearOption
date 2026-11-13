"""1.8.16 re-bake proof: share of the skin that the damage hole map opens at each HP step, on the model's own paint islands.

  blender --background <model.blend> --python-exit-code 1 --python blender/hole_cover1816.py -- <skin_dmg_b.png> <out.json> [--res 2048]

The game's AircraftSkin shader discards a skin pixel when the _BasecolorDmg alpha < 0.52 - 0.02 / D (D = 1 - HP / 100):
HP 90 -> 0.32, 80 -> 0.42, 50 -> 0.48, 0 -> 0.50 (docs/damage_model_study.md). Coverage = alpha texels below the threshold / texels
inside the paint triangles of the livery atlas (rasterised here at --res from the loaded model). Run on the 1.8.12 model + its damage
map and on the current model + the re-baked map; tools/stub_tests_1816o.py compares the two (+-2 percentage points per step).
"""
import bpy, sys, os, json, math
import numpy as np

argv = sys.argv[sys.argv.index('--') + 1:]
PNG, OUT = argv[0], argv[1]
R = int(argv[argv.index('--res') + 1]) if '--res' in argv else 2048
THRESH = {90: 0.32, 80: 0.42, 50: 0.48, 0: 0.50}

mask = np.zeros((R, R), bool)
for ob in bpy.data.objects:
    if ob.type != 'MESH':
        continue
    me = ob.data
    pis = {i for i, m in enumerate(me.materials) if m and (m.name == 'paint' or m.name.startswith('paint.'))}
    if not pis or 'livery' not in me.uv_layers:
        continue
    uv = me.uv_layers['livery'].data
    me.calc_loop_triangles()
    for lt in me.loop_triangles:
        if lt.material_index not in pis:
            continue
        px = np.array([[uv[l].uv[0] * R - 0.5, uv[l].uv[1] * R - 0.5] for l in lt.loops])
        x0, x1 = int(max(math.floor(px[:, 0].min()), 0)), int(min(math.ceil(px[:, 0].max()), R - 1))
        y0, y1 = int(max(math.floor(px[:, 1].min()), 0)), int(min(math.ceil(px[:, 1].max()), R - 1))
        if x1 < x0 or y1 < y0:
            continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1), np.arange(y0, y1 + 1))
        (ax, ay), (bx, by), (cx, cy) = px
        den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(den) < 1e-12:
            continue
        w0 = ((by - cy) * (gx - cx) + (cx - bx) * (gy - cy)) / den
        w1 = ((cy - ay) * (gx - cx) + (ax - cx) * (gy - cy)) / den
        ins = (w0 >= 0) & (w1 >= 0) & (1 - w0 - w1 >= 0)
        mask[gy[ins], gx[ins]] = True

im = bpy.data.images.load(os.path.abspath(PNG))
w, h = im.size
px = np.empty(w * h * 4, np.float32)
im.pixels.foreach_get(px)
a = px.reshape(h, w, 4)[..., 3]                     # Blender rows: bottom = v 0, as the mask
k = h // R
a = a[k // 2::k, k // 2::k][:R, :R]
res = dict(png=os.path.basename(PNG), model=os.path.basename(bpy.data.filepath), res=R, island_share=round(float(mask.mean()), 4),
           open_pct={str(hp): round(100.0 * float((a[mask] < t).mean()), 2) for hp, t in THRESH.items()})
json.dump(res, open(OUT, 'w'), indent=1)
print('[holes]', json.dumps(res))
