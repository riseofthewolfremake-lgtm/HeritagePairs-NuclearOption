"""1.9.14 round 4: GA-25X cockpit art vs modelled controls, measured on the MESH of a built blend (not on the generator's numbers).

  blender --background <ga25x.blend> --python check_ck_align1914.py -- <out.json>

1. art islands of cockpit_interior (linked ck_art faces, livery UV layer): panel (ga25x_ckart_layout rect the UVs fall in), its
   0-1 sub-rect, centre, normal; visibility from both crew eyes (cockpit_eye / crew_wso_eye): 7 x 7 samples per island, ray to
   the eye, occluded fraction, and the fraction of samples whose face points toward the eye. Canopy glass and extras do not
   occlude; the stock seats and sticks are added from the user's placeholders (stock_preview.py) when available.
2. controls: small ck_black islands standing in front of an art face (-2 .. 35 mm along its normal), classified by shape in
   the panel frame: 'round' (toggle boss / knob: in-plane extents equal within 1.5 mm, 8 .. 30 mm,
   outline a circle: farthest point <= 1.15 x half the extent, a square box reads 1.41), 'rect' (rocker paddle /
   lever handle: both in-plane extents >= 6 mm, 4 .. 12 mm thick, < 15 mm proud), else 'other' (guard cheeks and lids). Each gets
   its panel (u, v) (0-1 over the whole panel art, from the face UVs) and the panel's metres per u / per v there.
The stub test (tools/stub_tests_1914.py) compares these with the painted positions measured on the art.
"""
import bpy, bmesh, sys, os, json
from mathutils import Vector
from mathutils.geometry import barycentric_transform, intersect_point_tri

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ga25x_ckart_layout as LY

out = sys.argv[sys.argv.index('--') + 1]
O = bpy.data.objects
ob = O['cockpit_interior']
mw = ob.matrix_world
R3 = mw.to_3x3()
me = ob.data
bm = bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table()
uvl = bm.loops.layers.uv['livery']
mats = [m.name.split('.')[0] if m else '' for m in me.materials]
ART = mats.index('ck_art')
BLACK = mats.index('ck_black')


def panel_of(u, v):
    x, y = u * LY.ATLAS, (1 - v) * LY.ATLAS
    for n, ((x0, y0, x1, y1), _, _) in LY.PANELS.items():
        if x0 - 1 <= x <= x1 + 1 and y0 - 1 <= y <= y1 + 1:
            return n
    return None


def panel_uv(name, u, v):
    """atlas UV -> 0-1 inside the panel art (inverse of LY.uv, incl. its 2 px bleed)."""
    (x0, y0, x1, y1), _, _ = LY.PANELS[name]
    x0, y0, x1, y1 = x0 + 2, y0 + 2, x1 - 2, y1 - 2
    return (u * LY.ATLAS - x0) / (x1 - x0), 1 - ((1 - v) * LY.ATLAS - y0) / (y1 - y0)


def islands(sel):
    seen, res = set(), []
    for f in bm.faces:
        if f.index in seen or not sel(f):
            continue
        st, isl = [f], []
        seen.add(f.index)
        while st:
            g = st.pop(); isl.append(g)
            for e in g.edges:
                for h in e.link_faces:
                    if h.index not in seen and sel(h):
                        seen.add(h.index); st.append(h)
        res.append(isl)
    return res


# ---------------------------------------------------------------- art islands
tris, ART_ISL = [], []
for k, isl in enumerate(islands(lambda f: f.material_index == ART)):
    nrm, area, pans, uvs, pts = Vector(), 0.0, {}, [], []
    for f in isl:
        a = f.calc_area(); fn = (R3 @ f.normal).normalized()
        nrm += fn * a; area += a
        fu = [l[uvl].uv.copy() for l in f.loops]
        for u in fu:
            p = panel_of(u.x, u.y); pans[p] = pans.get(p, 0) + 1
        uvs += fu
        pts += [mw @ v.co for v in f.verts]
        lp = f.loops
        for i in range(1, len(lp) - 1):
            tri = (lp[0], lp[i], lp[i + 1])
            tris.append(([mw @ l.vert.co for l in tri], [Vector((l[uvl].uv.x, l[uvl].uv.y, 0)) for l in tri], fn, k))
    pan = max(pans, key=pans.get)
    pu = [panel_uv(pan, u.x, u.y) for u in uvs] if pan else [(0, 0)]
    lo = Vector([min(p[i] for p in pts) for i in range(3)]); hi = Vector([max(p[i] for p in pts) for i in range(3)])
    ART_ISL.append(dict(id=k, panel=pan, faces=len(isl), area_cm2=round(area * 1e4, 2), centre=[round(c, 4) for c in (lo + hi) / 2],
                        size=[round(c, 4) for c in hi - lo], normal=[round(c, 3) for c in nrm.normalized()],
                        sub=[round(min(p[0] for p in pu), 3), round(min(p[1] for p in pu), 3), round(max(p[0] for p in pu), 3), round(max(p[1] for p in pu), 3)],
                        _faces=isl))

# ---------------------------------------------------------------- visibility from the crew eyes
for o in O:
    if (o.users_collection and o.users_collection[0].name.endswith('_extras')) or o.name.startswith('canopy_glass'):
        o.hide_set(True); o.hide_viewport = True
preview = []
try:
    import stock_preview as SP
    if SP.available():
        preview = [p.name for p in SP.add_cockpit_preview()]
except Exception as e:                                     # placeholders missing: geometry of our own mesh only
    print('[ck_align] no stock preview:', e)
dg = bpy.context.evaluated_depsgraph_get(); dg.update()
sc = bpy.context.scene
eyes = {'pilot': O['cockpit_eye'].matrix_world.translation.copy(), 'wso': O['crew_wso_eye'].matrix_world.translation.copy()}
for rec in ART_ISL:
    if rec['panel'] == 'pedestal_gate':
        continue
    smp = []
    for f in rec['_faces']:                                # 7 x 7 barycentric grid on every triangle of the island's faces
        vs = [mw @ v.co for v in f.verts]; fn = (R3 @ f.normal).normalized()
        for t in range(1, len(vs) - 1):
            for i in range(7):
                for j in range(7 - i):
                    a, b = (i + 1 / 3) / 7, (j + 1 / 3) / 7
                    smp.append((vs[0] + (vs[t] - vs[0]) * a + (vs[t + 1] - vs[0]) * b + fn * 0.0015, fn))
    step = max(1, len(smp) // 60)
    smp = smp[::step]
    for tag, e in eyes.items():
        occ, facing, by = 0, 0, {}
        for p, fn in smp:
            d = e - p
            if fn.dot(d) > 0:
                facing += 1
            ok, loc, nr, idx, hob, _ = sc.ray_cast(dg, p, d.normalized(), distance=d.length - 0.01)
            if ok:
                occ += 1
                by[hob.name] = by.get(hob.name, 0) + 1
        rec[tag] = dict(occluded=round(occ / len(smp), 3), facing=round(facing / len(smp), 3), by=by)

# ---------------------------------------------------------------- labels beside the modelled controls (round 5)
# Painted label rects (panel u0, v0, u1, v1; u right, v up over the whole panel art), measured on the fal art, and the crew eye
# that uses the panel. Samples: a fixed barycentric grid on the panel's own art island (the big one, not the art-topped caps),
# kept where the panel (u, v) falls in the rect; occluded fraction of rays to the eye (stock seats / sticks present).
PANEL_MIN_CM2 = 8.0
LABELS = [('console_left', f'{n} ON/OFF', 'pilot', (u + 0.036, 0.438, u + 0.076, 0.538))
          for n, u in (('FUEL PUMP L', 0.1585), ('FUEL PUMP R', 0.3265), ('X-FEED', 0.496), ('ANTI-SKID', 0.669), ('NWS', 0.836))]
LABELS += [('console_left', 'MASTER ARM ARM/SAFE', 'pilot', (0.226, 0.709, 0.279, 0.842)),
           ('console_right', 'TGP PWR ON/STBY/OFF', 'wso', (0.502, 0.422, 0.552, 0.576)),
           ('console_right', 'LASER ARM ARM/SAFE', 'wso', (0.074, 0.164, 0.131, 0.334)),
           ('pedestal_radio', 'PWR 1 lower', 'pilot', (0.124, 0.087, 0.177, 0.123)),
           ('pedestal_radio', 'TEST 1 lower', 'pilot', (0.230, 0.087, 0.292, 0.123)),
           ('pedestal_radio', 'PWR 2 lower', 'pilot', (0.711, 0.087, 0.770, 0.123)),
           ('pedestal_radio', 'T/R+G 2 lower', 'pilot', (0.825, 0.087, 0.893, 0.123))]
LBL = []
for pan, name, eye, (lu0, lv0, lu1, lv1) in LABELS:
    e, smp = eyes[eye], []
    for (P, U, n, k) in tris:
        if ART_ISL[k]['panel'] != pan or ART_ISL[k]['area_cm2'] < PANEL_MIN_CM2:
            continue
        uvp = [panel_uv(pan, Ui.x, Ui.y) for Ui in U]
        G = 160
        for i in range(G):
            for j in range(G - i):
                a, b = (i + 1 / 3) / G, (j + 1 / 3) / G
                pu = uvp[0][0] + (uvp[1][0] - uvp[0][0]) * a + (uvp[2][0] - uvp[0][0]) * b
                pv = uvp[0][1] + (uvp[1][1] - uvp[0][1]) * a + (uvp[2][1] - uvp[0][1]) * b
                if lu0 <= pu <= lu1 and lv0 <= pv <= lv1:
                    smp.append(P[0] + (P[1] - P[0]) * a + (P[2] - P[0]) * b + n * 0.0008)
    occ, by = 0, {}
    for p in smp:
        dd = e - p
        ok, loc, nr, idx, hob, _ = sc.ray_cast(dg, p, dd.normalized(), distance=dd.length - 0.01)
        if ok:
            occ += 1
            by[hob.name] = by.get(hob.name, 0) + 1
    LBL.append(dict(panel=pan, label=name, eye=eye, samples=len(smp), occluded=round(occ / max(len(smp), 1), 3), by=by))

# ---------------------------------------------------------------- round 6: painted TEXT pixels beside the modelled controls
# The round-5 rects above count every sample in a label box; the round-5 verifier counted the label's text pixels (atlas
# lum > 0.55, sat < 0.15) and found 14-53 % of the console OFF labels hidden. Here: every text pixel (2 px step on the atlas, 1 px on the radio)
# inside each label region, mapped onto every big art island of that panel (>= 8 cm2) through the face UVs, ray-cast to the eye
# that uses it (left console pilot, right console WSO, radio by side, sub strips by side of the aircraft). Regions in px of the
# raw panel art (console 2528 x 1696, radio crop 1696 x 1288, sub strip 4128 x 1024), read off the art (study r6); 'ring' =
# scale ticks round a knob (cx, cy, r0, r1). Toggle bezel centres = blender/ga25x/textures/paint_out_levers1914.py (measured).
RAW = {'console_left': (2528, 1696), 'console_right': (2528, 1696), 'pedestal_radio': (1696, 1288), 'subpanel': (4128, 1024)}
TXT = []
for i, cx in enumerate((411, 837, 1264, 1692, 2118)):
    n = ('FUEL PUMP L', 'FUEL PUMP R', 'X-FEED', 'ANTI-SKID', 'NWS')[i]
    TXT += [('console_left', f'{n} ON', 'rect', (cx + 70, 772, cx + 200, 842)), ('console_left', f'{n} OFF', 'rect', (cx + 70, 888, cx + 210, 958))]
TXT += [('console_left', 'GEAR UP', 'rect', (1195, 222, 1335, 292)), ('console_left', 'GEAR DN', 'rect', (1195, 472, 1335, 542)),
        ('console_left', 'IGN title', 'rect', (755, 1222, 880, 1292)), ('console_left', 'DE-ICE title', 'rect', (1935, 1222, 2140, 1292)),
        ('console_left', 'BATT title', 'rect', (2185, 1222, 2340, 1292)), ('console_left', 'APU title', 'rect', (1040, 1200, 1140, 1268)),
        ('console_left', 'NAV LT OFF', 'rect', (1285, 1478, 1380, 1534)), ('console_left', 'NAV LT BRT', 'rect', (1485, 1478, 1575, 1534)),
        ('console_left', 'FORM LT OFF', 'rect', (1605, 1478, 1695, 1534)), ('console_left', 'FORM LT BRT', 'rect', (1800, 1478, 1890, 1534)),
        ('console_left', 'MASTER ARM ARM/SAFE', 'rect', (571, 268, 705, 493)),
        # round 6b (verifier on round 6): the OFF-BRT scale arcs round the APU / NAV LT / FORM LT knobs (circle fit to the arc's
        # text pixels on the raw art; radial histogram of text pixels: arc 82-118 / 92-124 / 88-124 px, titles and OFF / BRT >= 125)
        ('console_left', 'APU arc', 'ring', (1090, 1385, 80, 120)), ('console_left', 'NAV LT arc', 'ring', (1429, 1389, 88, 124)),
        ('console_left', 'FORM LT arc', 'ring', (1745, 1386, 86, 124)),
        ('console_right', 'CHNL ticks', 'ring', (1894, 1370, 100, 142)), ('console_right', 'FREQ ticks', 'ring', (2234, 1370, 100, 142)),
        ('console_right', 'CHNL label', 'rect', (1815, 1160, 1975, 1232)), ('console_right', 'FREQ label', 'rect', (2155, 1160, 2305, 1232)),
        ('console_right', 'RDR MODE SRCH', 'rect', (1285, 1205, 1425, 1268)), ('console_right', 'RDR MODE TRK', 'rect', (1445, 1175, 1545, 1238)),
        ('console_right', 'RDR MODE GMTI', 'rect', (1565, 1205, 1695, 1268)),
        ('console_right', 'TGP PWR ON/STBY/OFF', 'rect', (1269, 728, 1395, 989)), ('console_right', 'LASER ARM ARM/SAFE', 'rect', (187, 1129, 331, 1418))]
# round 7 (blender/ga25x/textures/relabel_art1914_r7.py): one label under each radio control: big knob FREQ (row 695-755), small
# knobs VOL / SQL (row 920-980, was PWR / TEST / TEST / T/R+G), toggles PWR / TEST / PWR / T/R+G (row 1120-1180, unchanged)
for x, nt, nb in ((253, 'VOL 1', 'PWR 1'), (443, 'SQL 1', 'TEST 1'), (1255, 'VOL 2', 'PWR 2'), (1448, 'SQL 2', 'T/R+G 2')):
    TXT += [('pedestal_radio', f'{nt} label', 'rect', (x - 70, 920, x + 70, 980)), ('pedestal_radio', f'{nb} label', 'rect', (x - 70, 1120, x + 70, 1180))]
TXT += [('pedestal_radio', 'FREQ 1 label', 'rect', (190, 695, 318, 755)), ('pedestal_radio', 'FREQ 2 label', 'rect', (1378, 695, 1506, 755)),
        ('pedestal_radio', 'IFF OFF', 'rect', (630, 930, 720, 990)), ('pedestal_radio', 'IFF OFF upper', 'rect', (685, 865, 775, 925)),
        ('pedestal_radio', 'IFF STBY', 'rect', (785, 840, 885, 900)), ('pedestal_radio', 'IFF NORM', 'rect', (910, 865, 1055, 925)),
        ('pedestal_radio', 'IFF LOW', 'rect', (970, 930, 1085, 990)),
        ('subpanel', 'LDG LT', 'rect', (2025, 258, 2248, 332)), ('subpanel', 'TAXI LT', 'rect', (2315, 258, 2547, 332)),
        ('subpanel', 'STBY INST', 'rect', (2738, 252, 2908, 408)),
        # round 7 (in-game review: HUD MODE knob over "A-G"; LASER ARM lid over "SAFE"): HUD panel labels and scale marks, the
        # LASER ARM labels one by one. HUD MODE ticks: 5 marks on a circle centred (389, 551) r 157-181 px; BRT arc: circle fit
        # (753, 706) r 110 (98-132) on the text pixels
        ('subpanel', 'HUD MODE title', 'rect', (300, 224, 478, 292)), ('subpanel', 'HUD OFF', 'rect', (195, 325, 305, 390)),
        ('subpanel', 'HUD NAV', 'rect', (330, 298, 452, 362)), ('subpanel', 'HUD A-A', 'rect', (463, 325, 573, 390)),
        ('subpanel', 'HUD A-G', 'rect', (543, 398, 652, 463)), ('subpanel', 'HUD MODE ticks', 'ring', (389, 551, 150, 190)),
        ('subpanel', 'HUD BRT title', 'rect', (694, 519, 811, 582)), ('subpanel', 'HUD BRT arc', 'ring', (753, 706, 98, 132)),
        ('console_right', 'LASER ARM label', 'rect', (192, 1127, 372, 1190)), ('console_right', 'LASER SAFE label', 'rect', (184, 1350, 372, 1416))]
eye_of = lambda pan, u, x3: ('pilot' if pan == 'console_left' else 'wso' if pan == 'console_right'
                            else ('pilot' if u < 0.5 else 'wso') if pan == 'pedestal_radio' else ('pilot' if x3 < 0 else 'wso'))
atlas_path = sys.argv[sys.argv.index('--atlas') + 1] if '--atlas' in sys.argv else os.path.join(HERE, '..', '..', 'assets', 'textures_ga25x', 'ga25x_ckart_b.png')
_img = bpy.data.images.load(os.path.abspath(atlas_path))
import numpy as np
_W, _H = _img.size
_px = np.array(_img.pixels[:], dtype=np.float32).reshape(_H, _W, 4)[::-1, :, :3]
_TEXT = (_px.mean(2) > 0.55) & ((_px.max(2) - _px.min(2)) < 0.15)
_S = LY.ATLAS / _W


def atlas_px(pan, u, v):
    (x0, y0, x1, y1), _, _ = LY.PANELS[pan]
    return (x0 + 2 + u * (x1 - 4 - x0)) / _S, (y0 + 2 + (1 - v) * (y1 - 4 - y0)) / _S


TXTL = []
for pan, name, kind, g in TXT:
    RW, RH = RAW[pan]
    if kind == 'rect':
        a0 = atlas_px(pan, g[0] / RW, 1 - g[1] / RH); a1 = atlas_px(pan, g[2] / RW, 1 - g[3] / RH)
        inreg = lambda x, y: True
    else:
        cxr, cyr, r0, r1 = g
        a0 = atlas_px(pan, (cxr - r1) / RW, 1 - (cyr - r1) / RH); a1 = atlas_px(pan, (cxr + r1) / RW, 1 - (cyr + r1) / RH)
        c_ = atlas_px(pan, cxr / RW, 1 - cyr / RH); sx = (a1[0] - a0[0]) / (2 * r1); sy = (a1[1] - a0[1]) / (2 * r1)
        inreg = lambda x, y, c_=c_, sx=sx, sy=sy, r0=r0, r1=r1: r0 <= ((((x - c_[0]) / sx) ** 2 + ((y - c_[1]) / sy) ** 2) ** 0.5) <= r1
    X0, Y0, X1, Y1 = int(min(a0[0], a1[0])), int(min(a0[1], a1[1])), int(max(a0[0], a1[0])) + 1, int(max(a0[1], a1[1])) + 1
    per = {}
    for (P, U, n, k) in tris:
        if ART_ISL[k]['panel'] != pan or ART_ISL[k]['area_cm2'] < PANEL_MIN_CM2:
            continue
        T2 = [Vector((Ui.x * _W, (1 - Ui.y) * _H, 0)) for Ui in U]
        tx0, ty0 = max(X0, int(min(t.x for t in T2))), max(Y0, int(min(t.y for t in T2)))
        tx1, ty1 = min(X1, int(max(t.x for t in T2)) + 1), min(Y1, int(max(t.y for t in T2)) + 1)
        area = (T2[1] - T2[0]).cross(T2[2] - T2[0]).z
        if tx0 >= tx1 or ty0 >= ty1 or abs(area) < 1e-9:
            continue
        st = 1 if pan == 'pedestal_radio' else 2           # the radio art is packed at 0.29 px per raw px: every atlas pixel
        for y in range(ty0 - ty0 % st, ty1, st):
            for x in range(tx0 - tx0 % st, tx1, st):
                if not _TEXT[y, x] or not inreg(x, y):
                    continue
                q2 = Vector((x + 0.5, y + 0.5, 0))
                b = [((T2[(j + 1) % 3] - q2).cross(T2[(j + 2) % 3] - q2)).z / area for j in range(3)]
                if min(b) < -1e-6:
                    continue
                q = P[0] * b[0] + P[1] * b[1] + P[2] * b[2] + n * 0.0008
                per.setdefault(k, []).append(q)
    for k, pts in per.items():
        x3 = ART_ISL[k]['centre'][0]
        uu = (g[0] if kind == 'ring' else (g[0] + g[2]) / 2) / RW
        eye = eye_of(pan, uu, x3)
        res = {}
        for tag, e in eyes.items():
            occ, by = 0, {}
            for p in pts:
                dd = e - p
                ok, loc, nr, idx, hob, _ = sc.ray_cast(dg, p, dd.normalized(), distance=dd.length - 0.01)
                if ok:
                    occ += 1
                    by[hob.name] = by.get(hob.name, 0) + 1
            res[tag] = dict(occluded=round(occ / len(pts), 3), by=by)
        TXTL.append(dict(panel=pan, label=name, island=k, x=round(x3, 3), eye=eye, text_px=len(pts), occluded=res[eye]['occluded'],
                         by=res[eye]['by'], other_eye=res['wso' if eye == 'pilot' else 'pilot']['occluded']))

# ---------------------------------------------------------------- controls
CTRL = []
# MeshBuf.poly gives every box face / cylinder cap its own vertices: join small ck_black islands
# into one part when they share a vertex position (a box = 6 faces, a knob = side + caps).
small = []
for isl in islands(lambda f: f.material_index == BLACK):
    pts = [mw @ v.co for f in isl for v in f.verts]
    lo = Vector([min(p[i] for p in pts) for i in range(3)]); hi = Vector([max(p[i] for p in pts) for i in range(3)])
    if max(hi - lo) <= 0.045 and len(isl) <= 80:
        small.append([pts, lo, hi])
par = list(range(len(small)))
def find(i):
    while par[i] != i:
        par[i] = par[par[i]]; i = par[i]
    return i
owner = {}
for i, (pts, _, _) in enumerate(small):                   # islands sharing a vertex position (10 um grid) are one part
    for p in pts:
        key = (round(p.x * 1e5), round(p.y * 1e5), round(p.z * 1e5))
        if key in owner:
            par[find(i)] = find(owner[key])
        else:
            owner[key] = i
groups = {}
for i in range(len(small)):
    groups.setdefault(find(i), []).append(i)
for gi in groups.values():
    pts = [p for i in gi for p in small[i][0]]
    lo = Vector([min(p[i] for p in pts) for i in range(3)]); hi = Vector([max(p[i] for p in pts) for i in range(3)])
    if max(hi - lo) > 0.045:
        continue
    c = (lo + hi) / 2
    best = None
    for (P, U, n, k) in tris:
        if ART_ISL[k]['area_cm2'] < PANEL_MIN_CM2:         # round 5: art-topped caps / lids are not the panel under a control
            continue
        d = (c - P[0]).dot(n)
        if d < -0.002 or d > 0.035:
            continue
        q = c - n * d
        if intersect_point_tri(q, *P) is None:
            continue
        if best is None or d < best[0]:
            best = (d, q, P, U, n, k)
    if best is None:
        continue
    d, q, P, U, n, k = best
    pan = ART_ISL[k]['panel']
    # panel frame on this tri: directions of +u and +v in 3D, metres per panel-u / panel-v
    uvp = [Vector(panel_uv(pan, Ui.x, Ui.y) + (0.0,)) for Ui in U]
    e1, e2 = P[1] - P[0], P[2] - P[0]
    t1, t2 = uvp[1] - uvp[0], uvp[2] - uvp[0]
    det = t1.x * t2.y - t1.y * t2.x
    du = (e1 * t2.y - e2 * t1.y) / det                     # dP/du
    dv = (e2 * t1.x - e1 * t2.x) / det                     # dP/dv
    # centre of the part's footprint (bbox in the panel frame, not the world AABB)
    au, av = du.normalized(), dv.normalized()
    cu = [(p - q).dot(au) for p in pts]; cv = [(p - q).dot(av) for p in pts]; cn = [(p - q).dot(n) for p in pts]
    q2 = q + au * ((max(cu) + min(cu)) / 2) + av * ((max(cv) + min(cv)) / 2)
    uv = barycentric_transform(q2, P[0], P[1], P[2], uvp[0], uvp[1], uvp[2])
    eu, ev, en = max(cu) - min(cu), max(cv) - min(cv), max(cn) - min(cn)
    lift = (min(cn) + max(cn)) / 2
    mu, mv = (max(cu) + min(cu)) / 2, (max(cv) + min(cv)) / 2
    corner = max(((a - mu) ** 2 + (b - mv) ** 2) ** 0.5 for a, b in zip(cu, cv)) / max(eu / 2, 1e-9)   # circle 1.0, square 1.41
    if abs(eu - ev) < 0.0015 and 0.008 <= eu <= 0.030 and corner < 1.15:
        cls = 'round'
    elif min(eu, ev) >= 0.006 and 0.004 <= en <= 0.012 and lift < 0.015:
        cls = 'rect'
    else:
        cls = 'other'
    CTRL.append(dict(panel=pan, island=k, cls=cls, u=round(uv.x, 4), v=round(uv.y, 4), m_per_u=round(du.length, 5), m_per_v=round(dv.length, 5),
                     ext_mm=[round(eu * 1000, 1), round(ev * 1000, 1), round(en * 1000, 1)], centre=[round(x, 4) for x in q2],
                     panel_centre=ART_ISL[k]['centre']))

for r in ART_ISL:
    r.pop('_faces')
import hashlib
json.dump(dict(blend=bpy.data.filepath, blend_sha1=hashlib.sha1(open(bpy.data.filepath, 'rb').read()).hexdigest(), preview=preview, eyes={k: [round(x, 4) for x in v] for k, v in eyes.items()},
               art=ART_ISL, controls=CTRL, labels=LBL, atlas=os.path.abspath(atlas_path), text_labels=TXTL), open(out, 'w'), indent=1)
for r in LBL:
    print(f"[ck_align] label {r['panel']:15s} {r['label']:22s} {r['eye']:5s} n={r['samples']:4d} occluded {r['occluded']:.3f} {r['by']}")
for r in TXTL:
    print(f"[ck_align] text  {r['panel']:15s} {r['label']:22s} x {r['x']:+.3f} {r['eye']:5s} px={r['text_px']:4d} occluded {r['occluded']:.3f} (other eye {r['other_eye']:.3f}) {r['by']}")
print(f'[ck_align] {len(ART_ISL)} art islands, {len(CTRL)} controls ({sum(c["cls"] != "other" for c in CTRL)} round/rect), preview {preview} -> {out}')
