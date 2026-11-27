"""A6M2 r8c: bake the cockpit atlas (UV set 'ckatlas', blender/a6m2/a6m2_ck_atlas.py) into the stock cockpit map set.

  blender --background assets/model_a6m2/a6m2.blend --python-exit-code 1 --python blender/a6m2/textures/bake_ck_atlas_a6m2.py -- [--out assets/textures_a6m2]

Writes a6m2_ck_b.png (sRGB base), a6m2_ck_n.png (tangent normal, OpenGL), a6m2_ck_m.png (R metallic, A smoothness), a6m2_ck_ao.png and
a6m2_ck_atlas.json (coverage, texel size, AO stats). Unity: A6M2_ckatlas, URP Lit + _METALLICSPECGLOSSMAP _NORMALMAP _OCCLUSIONMAP like
every stock cockpit material (study/a6m2/r8c/ckmat.py).

  base   = material colour x our tile (sampled on the 'detail' UV, as the Unity tiling materials did) x AO^0.85 (frames ^0.4) x height grime
           (0.42 at the floor -> 1.0 at the sill) x grime noise,
           with worn-through aluminium chips on the sill rails / canopy frames / lever tops
  normal = our tile normals rotated into the atlas tangent frame + rivet rows on the cockpit-view canopy frames (a6m2_canopy.FRAMES)
  ao     = Cycles AO (distance 0.30 m, glass removed, exterior canopy hidden) - the whole model occludes
Nothing from War Thunder: every value is ours (the WT cockpit was only looked at).
"""
import bpy, bmesh, os, sys, json, math
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path[:0] = [os.path.join(ROOT, 'blender', 'v2', 'textures'), os.path.join(ROOT, 'blender'), os.path.join(ROOT, 'blender', 'a6m2'), os.path.join(ROOT, 'blender', 'v2')]
import tex_lib as T
import a6m2_ck_atlas as CA
F32 = np.float32
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
OUT = os.path.abspath(argv[argv.index('--out') + 1]) if '--out' in argv else os.path.join(ROOT, 'assets', 'textures_a6m2')
TEXDIR = os.path.join(ROOT, 'assets', 'textures_a6m2')
NIMROD = os.path.join(ROOT, 'assets', 'textures_nimrod')
W, H = CA.RES
AO_SAMPLES = int(argv[argv.index('--samples') + 1]) if '--samples' in argv else 64


CK_FRAME_AO_ONCE = True   # r8g: frames take occlusion once (occlusion map, softened), not also in the albedo
CK_LIFT = 0.30   # r8e: frames / sills +30 % sRGB value (game lighting darkens them more than Blender)

def log(*a):
    print('[a6ck]', *a)


def srgb_to_lin(c):
    c = np.asarray(c, F32)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lin_to_srgb(c):
    c = np.clip(np.asarray(c, F32), 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


# ----------------------------------------------------------------------------------------------- rasteriser on 'ckatlas'
def rasterise():
    pos = np.zeros((H, W, 3), F32); nrm = np.zeros((H, W, 3), F32); mid = np.full((H, W), -1, np.int16)
    duv = np.zeros((H, W, 2), F32); jac = np.zeros((H, W, 4), F32); oid = np.full((H, W), -1, np.int16)
    mnames = list(CA.CK_MATS); onames = []
    area3, areauv = 0.0, 0.0
    for ob in bpy.data.objects:
        if ob.type != 'MESH' or 'ckatlas' not in ob.data.uv_layers:
            continue
        me = ob.data
        mats = [m.name if m else '' for m in me.materials]
        ca = me.uv_layers['ckatlas'].data; de = me.uv_layers['detail'].data if 'detail' in me.uv_layers else None
        M = ob.matrix_world; N3 = M.to_3x3().inverted().transposed()
        me.calc_loop_triangles()
        k = None
        for lt in me.loop_triangles:
            U = [ca[l].uv for l in lt.loops]
            if min(u.x for u in U) < 0:
                continue
            mn = mats[lt.material_index] if lt.material_index < len(mats) else ''
            if mn not in CA.CK_MATS:
                continue
            if k is None:
                onames.append(ob.name); k = len(onames) - 1
            P = [M @ me.vertices[v].co for v in lt.vertices]
            D = [de[l].uv for l in lt.loops] if de else [(0.0, 0.0)] * 3
            n = (N3 @ lt.normal).normalized()
            px = np.array([[u.x * W - 0.5, u.y * H - 0.5] for u in U], F32)
            a3 = ((P[1] - P[0]).cross(P[2] - P[0])).length / 2
            auv = abs((U[1].x - U[0].x) * (U[2].y - U[0].y) - (U[2].x - U[0].x) * (U[1].y - U[0].y)) / 2
            area3 += a3; areauv += auv
            # atlas <- detail Jacobian (columns: the detail u / v axes expressed in atlas uv), for rotating tile normals
            dA = np.array([[U[1].x - U[0].x, U[2].x - U[0].x], [U[1].y - U[0].y, U[2].y - U[0].y]], F32)
            dD = np.array([[D[1][0] - D[0][0], D[2][0] - D[0][0]], [D[1][1] - D[0][1], D[2][1] - D[0][1]]], F32)
            try:
                J = dA @ np.linalg.inv(dD)
                J = J / np.maximum(np.linalg.norm(J, axis=0, keepdims=True), 1e-9)
            except np.linalg.LinAlgError:
                J = np.eye(2, dtype=F32)
            x0, x1 = int(max(math.floor(px[:, 0].min()) - 1, 0)), int(min(math.ceil(px[:, 0].max()) + 1, W - 1))
            y0, y1 = int(max(math.floor(px[:, 1].min()) - 1, 0)), int(min(math.ceil(px[:, 1].max()) + 1, H - 1))
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
            Wb = np.stack([w0[ins], w1[ins], w2[ins]], -1)
            yy, xx = gy[ins].astype(int), gx[ins].astype(int)
            pos[yy, xx] = Wb @ np.array([tuple(p) for p in P], F32)
            duv[yy, xx] = Wb @ np.array([tuple(d) for d in D], F32)
            nrm[yy, xx] = (n.x, n.y, n.z)
            mid[yy, xx] = mnames.index(mn)
            jac[yy, xx] = J.ravel()
            oid[yy, xx] = k
    mask = mid >= 0
    ts = math.sqrt(area3 / max(areauv * W * H, 1e-9))          # metres per texel
    log(f'{len(onames)} objects, coverage {mask.mean():.3f}, texel {ts * 1000:.2f} mm')
    return pos, nrm, mid, duv, jac, oid, onames, mnames, mask, ts


# ----------------------------------------------------------------------------------------------- Cycles AO
def bake_ao():
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = AO_SAMPLES
    if sc.world is None:
        sc.world = bpy.data.worlds.new('ck_bake')
    sc.world.light_settings.distance = 0.30
    # the cockpit view: exterior canopy, pilot and stores hidden; glass faces removed (in memory only - this file is never saved)
    for ob in bpy.data.objects:
        if ob.type == 'MESH' and ob.name.startswith(('canopy_', 'pilot', 'store_')):
            ob.hide_render = True
    for ob in bpy.data.objects:
        if ob.type != 'MESH' or ob.hide_render:
            continue
        mats = [m.name if m else '' for m in ob.data.materials]
        gl = {i for i, m in enumerate(mats) if m.startswith(('glass', 'sightglass'))}
        if not gl:
            continue
        bm = bmesh.new(); bm.from_mesh(ob.data)
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index in gl], context='FACES')
        bm.to_mesh(ob.data); bm.free()
    img = bpy.data.images.new('ck_ao', W, H, alpha=False, float_buffer=True)
    img.colorspace_settings.name = 'Non-Color'
    for m in bpy.data.materials:
        m.use_nodes = True
        nt = m.node_tree
        tn = nt.nodes.new('ShaderNodeTexImage'); tn.image = img
        for n in nt.nodes:
            n.select = False
        tn.select = True; nt.nodes.active = tn
    targets = [ob for ob in bpy.data.objects if ob.type == 'MESH' and not ob.hide_render and 'ckatlas' in ob.data.uv_layers
               and any(d.uv.x >= 0 for d in ob.data.uv_layers['ckatlas'].data)]
    for ob in bpy.context.scene.objects:
        ob.select_set(False)
    for ob in targets:
        ob.hide_set(False); ob.select_set(True)
        ob.data.uv_layers.active = ob.data.uv_layers['ckatlas']
    bpy.context.view_layer.objects.active = targets[0]
    sc.render.bake.margin = 6
    bpy.ops.object.bake(type='AO', uv_layer='ckatlas', margin=6, use_clear=True)
    a = np.empty(W * H * 4, F32); img.pixels.foreach_get(a)
    log(f'AO baked on {len(targets)} objects, {AO_SAMPLES} samples')
    return a.reshape(H, W, 4)[..., 0]


# ----------------------------------------------------------------------------------------------- compose
def tile(name, sfx):
    for p in (os.path.join(TEXDIR, f'a6m2_tile_{name}_{sfx}.png'), os.path.join(NIMROD, f'nimrod_tile_{name}_{sfx}.png')):
        if os.path.exists(p):
            return T.load_image(p)
    return None


def sample(img, uv):
    h, w = img.shape[:2]
    x = np.mod(uv[:, 0], 1.0) * w - 0.5; y = np.mod(uv[:, 1], 1.0) * h - 0.5
    x0 = np.floor(x).astype(int); y0 = np.floor(y).astype(int); fx = (x - x0)[:, None]; fy = (y - y0)[:, None]
    x0 %= w; y0 %= h; x1 = (x0 + 1) % w; y1 = (y0 + 1) % h
    return (img[y0, x0] * (1 - fx) * (1 - fy) + img[y0, x1] * fx * (1 - fy) + img[y1, x0] * (1 - fx) * fy + img[y1, x1] * fx * fy)


def frame_rivets(P, oname_of):
    """height (m) of 2.6 mm rivet heads every 40 mm along the centre of every cockpit-view canopy frame's inner face."""
    import a6m2_canopy as CAN
    import a6m2_parts as AP
    if not CAN.FRAMES:
        AP.build_exterior()
    hgt = np.zeros(len(P), F32)
    sel = np.array([n.startswith('ckcanopy') for n in oname_of])
    if not sel.any():
        return hgt, 0
    Q = P[sel]; out = np.zeros(len(Q), F32)
    h_in = CAN.CK_FRAME[2]
    nmem = 0
    for fr in CAN.FRAMES:
        if fr['set'] != 'ck':
            continue
        nmem += 1
        pts = np.array(fr['path'], F32)
        if fr.get('closed'):
            pts = np.vstack([pts, pts[:1]])
        seg_a, seg_b = pts[:-1], pts[1:]
        L = np.linalg.norm(seg_b - seg_a, axis=1); cum = np.concatenate([[0.0], np.cumsum(L)])[:-1]
        for a_, b_, l_, c_ in zip(seg_a, seg_b, L, cum):
            if l_ < 1e-6:
                continue
            d_ = (b_ - a_) / l_
            t_ = np.clip((Q - a_) @ d_, 0, l_)
            near = a_ + t_[:, None] * d_
            dist = np.linalg.norm(Q - near, axis=1)
            lat2 = np.maximum(dist ** 2 - h_in ** 2, 0.0)
            on = (dist < math.sqrt(h_in ** 2 + 0.006 ** 2)) & (dist > h_in - 0.004)
            s_ = c_ + t_
            ds = np.abs(np.mod(s_ + 0.02, 0.040) - 0.020)
            r2 = lat2 + ds ** 2
            bump = np.where(on & (r2 < 0.0026 ** 2), 0.0009 * np.sqrt(np.clip(1 - r2 / 0.0026 ** 2, 0, 1)), 0.0)
            out = np.maximum(out, bump.astype(F32))
    hgt[sel] = out
    return hgt, nmem


def main():
    pos, nrm, mid, duv, jac, oid, onames, mnames, mask, ts = rasterise()
    ao_img = bake_ao()
    m = mask
    P = pos[m]; N = nrm[m]; MI = mid[m]; DUV = duv[m]; J = jac[m].reshape(-1, 2, 2); OI = oid[m]
    oname_of = [onames[i] for i in OI]
    ao = np.clip(ao_img[m], 0, 1)
    n = len(P)
    base = np.zeros((n, 3), F32); met = np.zeros(n, F32); smo = np.zeros(n, F32); tn = np.zeros((n, 3), F32); tn[:, 2] = 1
    for i, mn in enumerate(mnames):
        sel = MI == i
        if not sel.any():
            continue
        tl, col, me_, sm_ = CA.CK_MATS[mn]
        c = np.array(col, F32)
        if tl:
            tb, tnm = tile(tl, 'b'), tile(tl, 'n')
            b_ = sample(tb[..., :3], DUV[sel]) if tb is not None else np.full((sel.sum(), 3), 0.5, F32)
            # game r8b z_up_apex: the tile's panel seam fell on the arch apex (detail UV 0 at x = 0) and read as a crease: the canopy frames
            # take the tile's MEAN colour (smooth painted frames; their rivets come from frame_rivets) and no tile normal
            fr_ = np.array([oname_of[i].startswith('ckcanopy') for i in np.nonzero(sel)[0]])
            if tb is not None and fr_.any():
                b_[fr_] = tb[..., :3].reshape(-1, 3).mean(0)
            base[sel] = b_ * c
            if tnm is not None:
                nt_ = sample(tnm[..., :3], DUV[sel]) * 2 - 1
                xy = np.einsum('kij,kj->ki', J[sel], nt_[:, :2])
                v = np.concatenate([xy, nt_[:, 2:3]], 1)
                v = v / np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-6)
                v[fr_] = (0.0, 0.0, 1.0)
                tn[sel] = v
        else:
            base[sel] = c
        met[sel] = me_; smo[sel] = sm_
    # grime: darker low in the tub (z < 0.6) and in the occluded corners; large-scale dirty noise; brown-grey dust tint
    z = P[:, 2]
    tub = np.array([not nm.startswith('ckcanopy') for nm in oname_of])
    low = T.smoothstep(0.05, 0.62, z)
    hfac = np.where(tub, 0.42 + 0.58 * low, 1.0)
    # r8d (coordinator: the frames / sills carried big light and dark blotches - camouflage, not wear; base too olive and too light vs WT's
    # blue-grey green, measured WT frame ~ (90, 99, 88) sRGB vs ours (118, 124, 116)): an even base tinted toward WT, subtle fine grime,
    # wear only as small chips on edges and corners
    green = np.isin(MI, [mnames.index('interior'), mnames.index('ck_dark')])
    base[green] = base[green] * np.array(CA.ATLAS_TINT, F32)
    g = T.fbm(P.astype(F32), 22.0, 3, seed=31)
    gf = np.where(tub, 0.90 + 0.10 * T.smoothstep(0.30, 0.70, g), 0.95 + 0.05 * T.smoothstep(0.30, 0.70, g))
    aof = np.power(np.clip(ao, 0.0, 1.0), np.where(tub, 0.85, 0.40))
    if CK_FRAME_AO_ONCE:
        # r8g (game r8f z_cornerL: frames near-black in overcast, blue-green in sun): the frames were darkened twice by occlusion - AO
        # baked into the albedo AND the occlusion map (URP: ambient x AO; overcast light is all ambient). Measured: our frame albedo
        # median value 0.39-0.41 sRGB = stock COIN / CAS1 cockpit 0.37-0.45 (fine); fixed-canopy AO median 0.72. Frames: no AO in the
        # albedo, and their occlusion map softened to 0.5 + 0.5 x AO (the stock form keeps the AO in the occlusion map only).
        aof = np.where(tub, aof, 1.0)
    lin = srgb_to_lin(base) * (hfac * gf * aof)[:, None]
    dust = np.array([0.30, 0.27, 0.21], F32)
    dmask = (1 - aof) * 0.50 * T.smoothstep(0.55, 0.25, z / 1.0)
    lin = lin * (1 - dmask[:, None]) + srgb_to_lin(dust)[None, :] * 0.10 * dmask[:, None]
    # edges: on the canopy frames the rounded strip edges are where the face normal turns away from the frame's in/out direction
    # (the radial out_normal of a6m2_canopy); on the tub, the sill-rail tops and the console / plate edges facing up near the sill
    on_ = np.stack([P[:, 0], np.zeros(len(P), F32), P[:, 2] - 0.40], 1)
    on_ /= np.maximum(np.linalg.norm(on_, axis=1, keepdims=True), 1e-6)
    frame = ~tub
    edge_f = frame & (np.abs(np.sum(N * on_, 1)) < 0.45)
    edge_t = tub & (np.abs(N[:, 2]) > 0.55) & (z > 0.55) & (z < 0.66)
    w_ = T.fbm(P.astype(F32), 160.0, 2, seed=57)                     # ~6 mm chips
    chip = ((edge_f & (w_ > 0.74)) | (edge_t & (w_ > 0.80))) & green
    # r8f (r8e corner render: a large light ragged patch on the windscreen corner fitting - its faces turn away from the radial in/out
    # direction, so the edge test took whole faces as 'edges'): no wear chips within 70 mm of the cockpit-view windscreen top corners
    import a6m2_canopy as CAN_
    import a6m2_parts as AP_
    if not CAN_.FRAMES:
        AP_.build_exterior()
    for cB in CAN_.CK_CORNERS:
        near_c = frame & (np.linalg.norm(P - np.array(cB, F32), axis=1) < 0.07)
        log(f'corner {tuple(round(v, 3) for v in cB)}: {int((chip & near_c).sum())} chip texels removed')
        chip &= ~near_c
    lin[chip] = srgb_to_lin(np.array([0.40, 0.42, 0.41], F32)) * aof[chip, None]
    met[chip] = 0.70; smo[chip] = 0.45
    # r8e (game r8d: in the game's lighting the frames read near-black dark green): frames and sills lifted CK_LIFT (+30 %) in sRGB value,
    # hue kept; the lower tub fades back to the r8d value below the sill (z 0.45 -> 0.58)
    wl = np.where(frame, 1.0, T.smoothstep(0.45, 0.58, z)) * green * (~chip)
    lin = srgb_to_lin(np.clip(lin_to_srgb(lin) * (1.0 + CK_LIFT * wl)[:, None], 0.0, 1.0))
    log(f'frame / sill lift x{1 + CK_LIFT:.2f} (sRGB value) on {int((wl > 0.5).sum())} texels')
    smo = smo * (0.80 + 0.20 * aof)                                   # duller in the dirty corners
    # rivets on the cockpit-view frames
    rv, nmem = frame_rivets(P, oname_of)
    log(f'rivets on {nmem} ck frame members, {int((rv > 0).sum())} texels')
    Hm = np.zeros((H, W), F32); Hm[m] = rv
    nr = T.normal_from_height(Hm, ts, 1.0)[m]
    nx = tn[:, 0] + nr[:, 0]; ny = tn[:, 1] + nr[:, 1]; nz = tn[:, 2] * nr[:, 2]
    nn = np.stack([nx, ny, nz], 1); nn /= np.maximum(np.linalg.norm(nn, axis=1, keepdims=True), 1e-6)
    lin[rv > 0] *= 0.92
    # images (row 0 = v 0), padded outside the islands
    def img(vals, ch, fill):
        a = np.full((H, W, ch), fill, F32); a[m] = vals.reshape(-1, ch); return a
    B = T.fill_outside(img(lin_to_srgb(lin), 3, 0.3), m, 8)
    Nm = T.fill_outside(img(T.encode_normal(nn), 3, 0.5), m, 8)
    Mm = T.fill_outside(img(np.stack([met, met, met, smo], 1), 4, 0.0), m, 8)
    ao_w = np.where(~tub, 0.5 + 0.5 * ao, ao) if CK_FRAME_AO_ONCE else ao
    A = T.fill_outside(img(ao_w, 1, 1.0)[..., 0], m, 8)
    os.makedirs(OUT, exist_ok=True)
    T.save_png(B, os.path.join(OUT, 'a6m2_ck_b.png'))
    T.save_png(Nm, os.path.join(OUT, 'a6m2_ck_n.png'))
    T.save_png(Mm[..., :3], os.path.join(OUT, 'a6m2_ck_m.png'), alpha=Mm[..., 3])
    T.save_png(A, os.path.join(OUT, 'a6m2_ck_ao.png'))
    stats = dict(res=[W, H], coverage=round(float(m.mean()), 4), texel_mm=round(ts * 1000, 2), objects=onames, ao_mean=round(float(ao.mean()), 3),
                 ao_low_mean=round(float(ao[z < 0.35].mean()) if (z < 0.35).any() else -1, 3), base_mean_low=round(float(lin_to_srgb(lin)[z < 0.35].mean()), 3),
                 base_mean_high=round(float(lin_to_srgb(lin)[z > 0.55].mean()), 3), rivet_texels=int((rv > 0).sum()), chips=int(chip.sum()),
                 frame_members=nmem, samples=AO_SAMPLES)
    json.dump(stats, open(os.path.join(OUT, 'a6m2_ck_atlas.json'), 'w'), indent=1)
    log(json.dumps({k: v for k, v in stats.items() if k != 'objects'}))


main()
