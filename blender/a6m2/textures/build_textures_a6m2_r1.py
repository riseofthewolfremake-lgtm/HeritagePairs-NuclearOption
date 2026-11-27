"""A6M2 round-1 placeholder textures (design 10 round 1: "placeholder single livery or simple grey"). Our own numpy bake; the seven
liveries of design 9 come in round 5 once the geometry is final (memory geometry-change-rebakes-skin).

  blender --background assets/model_a6m2/a6m2.blend --python-exit-code 1 --python blender/a6m2/textures/build_textures_a6m2_r1.py -- [--out assets/textures_a6m2]

Writes a6m2_skin_b / _n / _m / _ao / _dmg_b / _dmg_n (2048, on the livery atlas of THIS model), a6m2_livery_grey.png (= skin_b),
a6m2_liveries.json (one entry, both factions), a6m2_propblur.png (3-blade disc / smear) and a6m2_atlas_manifest.json (atlas guard).
Skin = flat ame-iro-like grey #A8A48A with the cowl s 0.43-1.40 (from the spinner tip) blue-black, a little low-frequency tone noise,
panel-free (round 5 paints the real schemes). Damage = blender/v2/textures/hole_damage189.build (stock hole-order coverage bands).
"""
import bpy, os, sys, json, math
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'blender', 'v2', 'textures'))
sys.path.insert(0, os.path.join(ROOT, 'blender'))
import tex_lib as T
import atlas_guard as AG
F32 = np.float32
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
RES = 2048
OUT = os.path.abspath(argv[argv.index('--out') + 1]) if '--out' in argv else os.path.join(ROOT, 'assets', 'textures_a6m2')
os.makedirs(OUT, exist_ok=True)
K = 9.06 / 9.009
NOSE_Y = 2.381 * K


def log(*a):
    print('[a6tex]', *a)


def rasterise():
    R = RES
    pos = np.zeros((R, R, 3), F32); nrm = np.zeros((R, R, 3), F32); pid = np.full((R, R), -1, np.int16)
    names = []
    for ob in bpy.data.objects:
        if ob.type != 'MESH':
            continue
        me = ob.data
        mats = [m.name if m else '' for m in me.materials]
        if 'paint' not in mats:
            continue
        pi = mats.index('paint')
        names.append(ob.name); k = len(names) - 1
        uv = me.uv_layers['livery'].data
        M = ob.matrix_world; N3 = M.to_3x3().inverted().transposed()
        me.calc_loop_triangles()
        for lt in me.loop_triangles:
            if lt.material_index != pi:
                continue
            P = [M @ me.vertices[v].co for v in lt.vertices]
            U = [uv[l].uv for l in lt.loops]
            n = (N3 @ lt.normal).normalized()
            px = np.array([[u.x * R - 0.5, u.y * R - 0.5] for u in U], F32)
            x0, x1 = int(max(math.floor(px[:, 0].min()) - 1, 0)), int(min(math.ceil(px[:, 0].max()) + 1, R - 1))
            y0, y1 = int(max(math.floor(px[:, 1].min()) - 1, 0)), int(min(math.ceil(px[:, 1].max()) + 1, R - 1))
            if x1 < x0 or y1 < y0:
                continue
            gx, gy = np.meshgrid(np.arange(x0, x1 + 1, dtype=F32), np.arange(y0, y1 + 1, dtype=F32))
            (ax, ay), (bx, by), (cx, cy) = px
            den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
            if abs(den) < 1e-9:
                continue
            w0 = ((by - cy) * (gx - cx) + (cx - bx) * (gy - cy)) / den
            w1 = ((cy - ay) * (gx - cx) + (ax - cx) * (gy - cy)) / den
            w2 = 1 - w0 - w1
            e = -0.6 / max(abs(den), 1.0) ** 0.5
            ins = (w0 >= e) & (w1 >= e) & (w2 >= e)
            if not ins.any():
                continue
            Pa = np.array([tuple(p) for p in P], F32)
            W = np.stack([w0[ins], w1[ins], w2[ins]], -1)
            yy, xx = gy[ins].astype(int), gx[ins].astype(int)
            pos[yy, xx] = W @ Pa
            nrm[yy, xx] = (n.x, n.y, n.z)
            pid[yy, xx] = k
    mask = pid >= 0
    log(f'{len(names)} paint objects, atlas coverage {mask.mean():.3f}')
    return pos, nrm, pid, names, mask


def to_img(mask, vals, fill=0.0):
    ch = 1 if vals.ndim == 1 else vals.shape[1]
    img = np.full((RES, RES, ch), fill, F32)
    img[mask] = vals.reshape(-1, ch)
    return img if ch > 1 else img[..., 0]


def hexc(h):
    return np.array([int(h[i:i + 2], 16) / 255.0 for i in (1, 3, 5)], F32)


def main():
    pos, nrm, pid, names, mask = rasterise()
    P = pos[mask]
    s = NOSE_Y - P[:, 1]                                   # metres aft of the spinner tip
    base = np.tile(hexc('#A8A48A'), (len(P), 1))
    cowl = (s > 0.43 * K) & (s < 1.40 * K) & (np.abs(P[:, 0]) < 0.75)
    base[cowl] = hexc('#1C2124')
    tone = 1.0 + 0.035 * T.fbm(P.astype(F32), 0.8, 3, seed=7)
    col = np.clip(base * tone[:, None], 0, 1)
    img = T.fill_outside(to_img(mask, col), mask, 24)
    T.save_png(img, os.path.join(OUT, 'a6m2_skin_b.png'))
    T.save_png(img, os.path.join(OUT, 'a6m2_livery_grey.png'))
    flat = np.zeros((RES, RES, 3), F32); flat[..., 2] = 1.0
    T.save_png(T.encode_normal(flat), os.path.join(OUT, 'a6m2_skin_n.png'))
    met = np.where(cowl, 0.35, 0.25).astype(F32)
    sm = np.where(cowl, 0.45, 0.38).astype(F32)
    T.save_png(T.fill_outside(to_img(mask, np.stack([met] * 3, -1)), mask, 24), os.path.join(OUT, 'a6m2_skin_m.png'),
               alpha=T.fill_outside(to_img(mask, sm), mask, 24))
    T.save_png(np.full((RES, RES), 1.0, F32), os.path.join(OUT, 'a6m2_skin_ao.png'))
    import hole_damage189 as HD
    rgb, alpha, Hh, st = HD.build(T, P.astype(F32), scale=0.6, seed=1940, log=log)
    T.save_png(T.fill_outside(to_img(mask, rgb), mask, 24), os.path.join(OUT, 'a6m2_skin_dmg_b.png'), alpha=to_img(mask, alpha, fill=HD.FILL_ALPHA))
    stats = json.loads(bpy.context.scene.get('b25_build_stats', '{}'))
    ts = stats.get('metres_per_uv', 12.0) / RES
    Hd = T.fill_outside(to_img(mask, Hh), mask, 8)
    T.save_png(T.encode_normal(T.normal_from_height(Hd, ts, 3.0)), os.path.join(OUT, 'a6m2_skin_dmg_n.png'))
    q = (np.clip(img[mask], 0, 1) * 15).round().astype(int) * 16
    keys, cnt = np.unique(q[:, 0] * 65536 + q[:, 1] * 256 + q[:, 2], return_counts=True)
    order = np.argsort(-cnt)[:5]
    colors = [dict(color='#%02X%02X%02XFF' % ((k >> 16) & 255, (k >> 8) & 255, k & 255), count=int(c)) for k, c in zip(keys[order], cnt[order])]
    json.dump({'grey': dict(texture='a6m2_livery_grey.png', name='IJN Grey (round 1 placeholder)', label='IJN Grey (round 1 placeholder)',
                            faction='BDF', both=True, glossiness=0.35, colors=colors)}, open(os.path.join(OUT, 'a6m2_liveries.json'), 'w'), indent=1)
    propblur()
    m = AG.write_manifest(os.path.join(OUT, 'a6m2_atlas_manifest.json'), 'A6M2', AG.scene_parts(), bpy.data.filepath,
                          AG.atlas_textures(OUT, 'a6m2'), written_by='blender/a6m2/textures/build_textures_a6m2_r1.py')
    log('damage', json.dumps(st))
    log('atlas manifest', m['atlas_hash'])


def propblur():
    """512 x 1024: upper half = 3-blade smear, lower half = full disc; aluminium, alpha."""
    W = 512
    out = np.zeros((1024, W, 4), F32)
    for half, smear in ((0, False), (1, True)):
        yy, xx = np.mgrid[0:512, 0:W].astype(F32)
        cx, cy = (xx + 0.5 - 256) / 250, (yy + 0.5 - 256) / 250
        r = np.sqrt(cx * cx + cy * cy)
        edge = np.clip((1 - r) * 60, 0, 1) * np.clip((r - 0.17) * 30, 0, 1)
        if smear:
            th = np.degrees(np.arctan2(cy, cx))
            d = np.min(np.stack([np.abs(((th - a + 180) % 360) - 180) for a in (90, 210, 330)]), axis=0)
            a = (0.06 + 0.55 * np.exp(-(d / (8 + 22 * r)) ** 2)) * edge
        else:
            a = (0.16 + 0.03 * np.sin(r * 50)) * edge
        out[half * 512:(half + 1) * 512, :, :3] = np.array([0.70, 0.71, 0.72], F32)
        out[half * 512:(half + 1) * 512, :, 3] = a
    T.save_png(out[..., :3], os.path.join(OUT, 'a6m2_propblur.png'), alpha=out[..., 3])


main()
