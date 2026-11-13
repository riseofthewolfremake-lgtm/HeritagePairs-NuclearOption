"""Build the MSB-17/80 airframe (Heritage Pairs 1.9.0): the B-17G generator reused by import + the MSB parts, saved as a .blend + contract.

  blender --background --factory-startup --python-exit-code 1 --python blender/msb1780/build_msb1780.py -- --out assets/model_msb1780/msb1780.blend

Blender space: nose +Y, up +Z, right wing +X, metres, real size, gear DOWN, bay doors closed (as the B-17G). The B-17G modules are imported
read-only and steered through b17g_spec (patched in memory by msb_spec) and a few module-level hooks set here (face kinds, ring stations,
nacelle front, internals); no B-17G file is modified (tools/stub_tests_190.py hashes them).
"""
import bpy, sys, os, json, math
HERE = os.path.dirname(os.path.abspath(__file__))
B17 = os.path.abspath(os.path.join(HERE, '..', 'b17g'))
V2 = os.path.abspath(os.path.join(HERE, '..', 'v2'))
NIM = os.path.abspath(os.path.join(HERE, '..', 'nimrod'))
for p in (V2, NIM, B17, HERE):
    if p in sys.path:
        sys.path.remove(p)
    sys.path.insert(0, p)
for m in ('b17g_spec', 'msb_spec', 'b17g_parts', 'b17g_props', 'b17g_cockpit', 'b17g_detail', 'b17g_nacelle', 'b17g_nose1817', 'msb_parts', 'msb_cockpit', 'msb_stations', 'msb_deck195', 'msb_detail196'):
    sys.modules.pop(m, None)
from mathutils import Vector as V, Matrix
import b17g_spec as S
import msb_spec as M              # patches S in place: import before every b17g module below
import build_b25h_v2 as B
from b25h_parts import Part
from b25h_geom import MeshBuf
import b17g_parts as P
import b17g_detail as D
import b17g_nacelle as N
import b17g_nose1817 as NZ
import msb_parts as MP
import msb_cockpit as MC
import msb_stations as MST
import msb_deck195 as MDK
import nimrod_structure as NS

MATERIALS = {   # the B-17G material names (Unity builds one material per name; the MSB tiles are greys, built_textures_msb1780.py)
    'paint': ((0.42, 0.44, 0.45, 1.0), 0.1, 0.6), 'interior': ((0.36, 0.37, 0.38, 1.0), 0.1, 0.75), 'structure': ((0.55, 0.57, 0.58, 1.0), 0.5, 0.5),
    'glass': ((0.55, 0.62, 0.66, 0.25), 0.0, 0.05), 'cove': ((0.05, 0.05, 0.05, 1.0), 0.0, 0.9), 'well': ((0.30, 0.31, 0.32, 1.0), 0.2, 0.7),
    'gear': ((0.35, 0.36, 0.37, 1.0), 0.6, 0.45), 'chrome': ((0.85, 0.86, 0.88, 1.0), 1.0, 0.15), 'cowl': ((0.10, 0.10, 0.10, 1.0), 0.4, 0.5),
    'metal_dark': ((0.06, 0.06, 0.065, 1.0), 0.7, 0.4), 'exhaust': ((0.13, 0.11, 0.10, 1.0), 0.4, 0.6), 'turbo': ((0.26, 0.13, 0.06, 1.0), 0.15, 0.7),
    'cowl_ring': ((0.24, 0.25, 0.15, 1.0), 0.1, 0.6), 'prop': ((0.03, 0.03, 0.03, 1.0), 0.2, 0.5), 'engine': ((0.3, 0.3, 0.3, 1.0), 0.8, 0.4),
    'tyre': ((0.03, 0.03, 0.03, 1.0), 0.0, 0.9), 'turret': ((0.40, 0.42, 0.43, 1.0), 0.2, 0.6), 'pr_hsprop': ((0.09, 0.09, 0.10, 1.0), 0.3, 0.5),
    'ck_panel': ((0.10, 0.105, 0.11, 1.0), 0.1, 0.6), 'ck_wall': ((0.30, 0.31, 0.32, 1.0), 0.1, 0.6), 'ck_od': ((0.25, 0.26, 0.27, 1.0), 0.1, 0.6),
    'ck_floor': ((0.16, 0.165, 0.17, 1.0), 0.1, 0.8), 'ck_black': ((0.02, 0.02, 0.022, 1.0), 0.1, 0.6), 'ck_bezel': ((0.10, 0.10, 0.10, 1.0), 0.6, 0.4),
    'gauges': ((0.85, 0.85, 0.80, 1.0), 0.0, 0.4), 'needle': ((0.92, 0.92, 0.88, 1.0), 0.0, 0.5), 'screen': ((0.01, 0.012, 0.015, 1.0), 0.0, 0.8),
    'ck_legend': ((0.90, 0.90, 0.86, 1.0), 0.0, 0.5), 'ck_amber': ((0.85, 0.55, 0.10, 1.0), 0.0, 0.4), 'ck_green': ((0.25, 0.80, 0.35, 1.0), 0.0, 0.4),   # 1.9.6 legends / lamps (emissive in Unity)
}
MASS = {   # kg (CG estimate only; Unity sets the part masses, MSB1780Build Parts())
    'fus_nose': 1700, 'fus_cockpit': 2600, 'B17G': 6200, 'fus_waist': 1300, 'fus_tail': 420, 'tail_gun': 520,
    'wing_inner': 2200, 'wing_mid': 1500, 'wing_outer': 700, 'wing_tip': 70, 'nacelle': 350, 'engine': 1400, 'prop': 380,
    'stab': 140, 'elevator': 50, 'fin': 210, 'rudder': 70, 'flap_inner': 90, 'flap_outer': 100, 'aileron': 80, 'gear_main': 700, 'gear_tail': 120,
}


def mass_of(name):
    if name.startswith(('prop_hub_', 'prop_') ) and ('_aft' in name or name.startswith('prop_hub_')):
        return 0
    for k in sorted(MASS, key=len, reverse=True):
        if name == k or name.startswith(k + '_') or name.startswith(k):
            return MASS[k]
    return 0


# ============================================================================================ hooks into the B-17G fuselage builder
_TAIL_WELL_HW = P.TAIL_WELL_HW
P.BALL_HOLE_R = M.BALL_HOLE_R
P.PART_ANCHORS['B17G'] = dict(P.PART_ANCHORS['B17G'], w=((-3.45, 0.0), (-3.35, 1.0), (2.80, 1.0), (2.90, 0.0)))


def msb_face_kind(c, ring_c):
    """material / role of a fuselage skin face by its centre: MWS sensor windows (glass), side-bay doors and the EWO hatch ('door' faces:
    split off below), tail-wheel well and the ventral laser opening (holes). The B-17G waist / tail / radio openings are closed skin."""
    x, y, z = c
    top, bot, hw, n = S.fus_station(y)
    sw, sb, eh = M.SENSOR_WIN, M.SIDE_BAY, M.EWO_HATCH
    if sw['y'][0] < y < sw['y'][1] and abs(x) > 0.5 and sw['z'][0] < z < sw['z'][1]:
        return 'glass'
    if sb['y'][0] < y < sb['y'][1] and abs(x) > 0.5 and sb['z'][0] < z < sb['z'][1]:
        return 'door'
    if eh['y'][0] < y < eh['y'][1] and eh['x'][0] < x < eh['x'][1] and z > top - 0.35:
        return 'door'
    if S.TAIL_WELL[0] < y < S.TAIL_WELL[1] and z < bot + 0.25 and abs(x) < _TAIL_WELL_HW:
        return 'hole'
    if z < bot + 0.3 and x * x + (y - S.TURRETS['ball']['pos'][1]) ** 2 < M.BALL_HOLE_R ** 2:
        return 'hole'
    return 'paint'


P.fus_face_kind = msb_face_kind
if M.TAIL_PLATED197:
    # 1.9.7: the tail cab's glazing (b17g_parts.part_window for 'tail_gun', S.TAIL188) becomes ordinary skin and its frame bars are not
    # built; the cab's ring stations (P.TAIL_CAB_YS) stay, so the outline is the 1.9.6 one. The B-17G module is patched in memory only.
    _part_window_b17g = P.part_window
    P.part_window = lambda name, y0, y1, j: None if name == 'tail_gun' else _part_window_b17g(name, y0, y1, j)
    P.tail_frames = lambda mb, ys, rings: None
_EXTRA_Y = (M.EWO_HATCH['y'][0], M.EWO_HATCH['y'][1], M.SENSOR_WIN['y'][0], M.SENSOR_WIN['y'][1], M.SIDE_BAY['y'][0], M.SIDE_BAY['y'][1],
            M.PILOT_HATCH_Y[0], M.PILOT_HATCH_Y[1], S.BAY_Y[0], S.BAY_Y[1], 3.00, 3.25, 3.50, 3.85, 3.97, S.WINDSCREEN[1], S.NOSE_GLASS_Y)


def msb_fus_stations(y0, y1, step=0.28):
    req = sorted({y0, y1} | {r[0] for r in S.FUS if y1 < r[0] < y0} | {v for v in _EXTRA_Y + P.TAIL_CAB_YS if y1 < v < y0}, reverse=True)
    out = [req[0]]
    for a, b in zip(req, req[1:]):
        k = max(1, int(math.ceil((a - b) / step)))
        out += [a + (b - a) * i / k for i in range(1, k + 1)]
    return out


P.fus_stations = msb_fus_stations
# nacelles: the B-17G bodies / wells; no cowl flaps (the body starts where the drum ends), the MSB turboprop front instead of the radial lip
N.N_FLAPS = 0
N.FLAP_TE = N.FLAP_LE + 0.02
N.engine_front = MP.nacelle_front
NZ.mast = lambda mb: None


def _fus_excluded_msb(p, y, dome=True, _orig=D._fus_excluded):
    if _orig(p, y, dome):
        return True
    sb, eh = M.SIDE_BAY, M.EWO_HATCH
    if sb['y'][0] - 0.20 < y < sb['y'][1] + 0.20 and abs(p.x) > 0.45 and sb['z'][0] - 0.12 < p.z < sb['z'][1] + 0.12:
        return True
    if eh['y'][0] - 0.10 < y < eh['y'][1] + 0.10 and eh['x'][0] - 0.10 < p.x < eh['x'][1] + 0.10 and p.z > 1.55:
        return True
    if M.PILOT_HATCH_Y[0] - 0.10 < y < M.PILOT_HATCH_Y[1] + 0.10 and p.z > 1.80:
        return True
    if M.NOSE_HATCH[0] - 0.10 < y < M.NOSE_HATCH[1] + 0.10 and abs(p.x) < 0.42 and p.z > 0.9:
        return True
    if (p - V(S.TURRETS['tail']['pos'])).length < 0.62:
        return True
    return False


D._fus_excluded = _fus_excluded_msb


def _fuselage_internals_capped(fus_ring, _orig=D.fuselage_internals):
    """the B-17G frames + stringers, plus an end cap on every stringer that stops at an opening the MSB adds (hatches, side bays,
    the tail turret): the B-17G method leaves those bar ends open, and an open end lets a ray from inside meet a back face (n17 at
    y 6.35: a stringer stopping short of the WSO hatch). Ends shared by two bars and ends the B-17G code already capped are left alone."""
    bars, caps = [], set()
    ob, oc = D._bar, D._bar_cap
    key = lambda p: (round(p.x, 3), round(p.y, 3), round(p.z, 3))

    def rec_bar(mb, a, b, w, h, up, mat='structure'):
        bars.append((mb, V(a), V(b), w, h, V(up), mat)); return ob(mb, a, b, w, h, up, mat)

    def rec_cap(mb, p, ax, w, h, up, mat='structure'):
        caps.add((id(mb), key(V(p)))); return oc(mb, p, ax, w, h, up, mat)
    D._bar, D._bar_cap = rec_bar, rec_cap
    try:
        out = _orig(fus_ring)
    finally:
        D._bar, D._bar_cap = ob, oc
    ends = {}
    for mb, a, b, *_ in bars:
        for p in (a, b):
            ends[(id(mb), key(p))] = ends.get((id(mb), key(p)), 0) + 1
    n = 0
    for mb, a, b, w, h, up, mat in bars:
        for p, ax in ((a, a - b), (b, b - a)):
            k = (id(mb), key(p))
            if ends[k] == 1 and k not in caps and ax.length > 1e-5:
                oc(mb, p, ax, w, h, up, mat); n += 1
    print(f'[msb] stringer ends capped: {n} of {len(bars)} bars')
    return out


D.fuselage_internals = _fuselage_internals_capped


# ============================================================================================ internals (the B-17G set with turboshaft engines)
def add_internals(parts):
    by = {p.name: p for p in parts}
    stats = {}

    def put(name, mb):
        p = by.get(name)
        if p is None or p.mesh is None or not mb.faces:
            return
        p.mesh.extend(mb); stats[name] = stats.get(name, 0) + mb.tri_count()
    for side in (-1, 1):
        for name, mb in D.wing_internals(side, P.wing_station).items():
            put(name, mb)
        for kind in ('inner', 'outer'):
            num = S.ENGINE_NUM[(side, kind)]
            e, n = MP.engine_internals(kind, side)
            put(f'engine_{num}', e); put(f'nacelle_{num}', n)
    for name, n_ in N.le_intakes(parts, P.wing_station).items():
        stats[name] = stats.get(name, 0) + n_
    for name, mb in D.fuselage_internals(P.fus_ring).items():
        put(name, mb)
    put('B17G', D.bay_internals())
    nf = MeshBuf()
    ys = [5.06 + (6.74 - 5.06) * k / 12 for k in range(13)]
    zf = M.NOSE_FLOOR_Z
    from b25h_geom import oriented_quad
    for ya, yb in zip(ys, ys[1:]):
        wa, wb = P.fus_skin_x(ya, zf, 0.02), P.fus_skin_x(yb, zf, 0.02)
        if wa < 0.05 or wb < 0.05:
            continue
        q = [V((-wa, ya, zf)), V((wa, ya, zf)), V((wb, yb, zf)), V((-wb, yb, zf))]
        oriented_quad(nf, q, 'interior', V((0, 0, 1)))
        oriented_quad(nf, [p + V((0, 0, -0.006)) for p in q], 'interior', V((0, 0, -1)))
    put('fus_nose', nf)
    return stats


# ============================================================================================ hatches / doors taken out of the skin
def take_faces(mb, pred):
    """move the faces of mb whose centre satisfies pred(c, f) into a new MeshBuf (own vertices)."""
    out = MeshBuf(); keep = []
    for f in mb.faces:
        P_ = [mb.verts[k] for k in f['idx']]
        c = sum(P_, V()) / len(P_)
        if pred(c, f):
            out.face([out.v(p) for p in P_], f['mat'], f['uv'], f['smooth'])
        else:
            keep.append(f)
    mb.faces = keep
    return out


def hatch_part(name, parent, mb, hinge_axis_x=True):
    """hatch_<x> (mesh, rest identity under its hinge) + hatch_<x>_hinge at the hatch's forward edge (local +X = lateral hinge axis)."""
    ys = [p.y for f in mb.faces for p in (mb.verts[k] for k in f['idx'])]
    zs = [p.z for f in mb.faces for p in (mb.verts[k] for k in f['idx'])]
    xs = [p.x for f in mb.faces for p in (mb.verts[k] for k in f['idx'])]
    piv = V(((min(xs) + max(xs)) / 2, max(ys), max(zs)))
    return [Part(f'{name}_hinge', parent, pivot=piv, info={'kind': 'hatch_hinge'}),
            Part(name, f'{name}_hinge', pivot=piv, mesh=mb, info={'kind': 'hatch', 'jettison': True})]


def main():
    argv = sys.argv[sys.argv.index('--') + 1:]
    out = os.path.abspath(argv[argv.index('--out') + 1])
    bpy.ops.wm.read_factory_settings(use_empty=True)
    mats = {}
    for name, (col, met, rough) in MATERIALS.items():
        m = bpy.data.materials.new(name); m.diffuse_color = col; m.use_nodes = True
        bs = m.node_tree.nodes.get('Principled BSDF')
        bs.inputs['Base Color'].default_value = col; bs.inputs['Metallic'].default_value = met; bs.inputs['Roughness'].default_value = rough
        if col[3] < 1:
            bs.inputs['Alpha'].default_value = col[3]
            try:
                m.surface_render_method = 'BLENDED'
            except Exception:
                m.blend_method = 'BLEND'
        mats[name] = m
    parts = []
    fus, doors = P.build_fuselage()
    by = {p.name: p for p in fus}
    # doors: bay (belly) / EWO hatch (top, centre section) / side bays (fus_waist)
    bay_doors, side_doors, ewo = [], {}, MeshBuf()
    for side, dm in doors:
        zc = sum(v.z for v in dm.verts) / max(len(dm.verts), 1)
        yc = sum(v.y for v in dm.verts) / max(len(dm.verts), 1)
        top_part = take_faces(dm, lambda c, f: c.z > 1.0)
        if top_part.faces:
            ewo.extend(top_part)
        if not dm.faces:
            continue
        dm = take_faces(dm, lambda c, f: True)      # own vertices only: the EWO faces' vertices left in dm put the R bay door's hinge at z 1.67 (Unity door check)
        if M.SIDE_BAY['y'][0] - 0.05 < yc < M.SIDE_BAY['y'][1] + 0.05 and zc > -0.1:
            side_doors[side] = dm
        else:
            bay_doors.append((side, dm))
    print('[msb] doors: bay', [(s, len(d.faces)) for s, d in bay_doors], 'side', {s: len(d.faces) for s, d in side_doors.items()}, 'ewo hatch', len(ewo.faces))
    # pilots' overhead windows -> glazed escape hatches; nose top window -> the WSO's glazed hatch
    ck = by['fus_cockpit'].mesh
    hp = {s: take_faces(ck, lambda c, f, s=s: f['mat'] == 'glass' and M.PILOT_HATCH_Y[0] - 0.02 < c.y < M.PILOT_HATCH_Y[1] + 0.02 and c.z > 1.80
                        and (c.x < -0.05 if s == 'L' else c.x > 0.05)) for s in ('L', 'R')}
    nh = take_faces(by['fus_nose'].mesh, lambda c, f: f['mat'] == 'glass' and M.NOSE_HATCH[0] - 0.02 < c.y < M.NOSE_HATCH[1] + 0.02 and c.z > 1.0
                    and M.NOSE_HATCH[2] - 0.02 < c.x < M.NOSE_HATCH[3] + 0.02)
    print('[msb] hatch faces: pilot L', len(hp['L'].faces), 'R', len(hp['R'].faces), 'wso', len(nh.faces))
    NS.double_skin(ewo, t=0.006, mats=('paint',), inner=lambda f, c: 'interior')
    eh = M.EWO_HATCH      # the split frame ring 0.09 m inside y 2.90 (and stringer stubs) crossed the EWO's hatch: cut out of the opening
    cut = take_faces(by['B17G'].mesh, lambda c, f: f['mat'] == 'structure' and eh['y'][0] - 0.01 < c.y < eh['y'][1] + 0.03 and eh['x'][0] - 0.02 < c.x < eh['x'][1] + 0.02 and c.z > 1.70)
    print('[msb] structure faces cut out of the EWO hatch opening:', len(cut.faces))
    parts += fus
    parts += hatch_part('hatch_pilot_L', 'fus_cockpit', hp['L']) + hatch_part('hatch_pilot_R', 'fus_cockpit', hp['R'])
    parts += hatch_part('hatch_wso', 'fus_nose', nh) + hatch_part('hatch_ewo', 'B17G', ewo)
    parts += P.build_bay(bay_doors)
    parts += MP.bay_extras('B17G')
    parts += MP.side_bays(side_doors)
    for side in (-1, 1):
        parts += P.build_wing(side)
        for kind in ('inner', 'outer'):
            parts += [p for p in P.build_nacelle(kind, side) if not p.name.endswith('_hullsrc')]
            parts += MP.props(kind, side)
        parts += P.main_gear(side)
    parts += P.build_tail()
    parts += P.tail_gear()
    # turret openings / races from the B-17G (top race, ball ring band, chin ring + race); not the radio coaming or the ball yoke
    S.TURRETS['radio'] = dict(pos=(0.0, -99.0, 1.78), fwd=(0, -0.5, 0.866), guns=[(0.0, 0.0)], station='-', trav=0.0, emin=0.0, emax=0.0)
    rings = [p for p in P.build_turret_rings() if p.name not in ('radio_coaming', 'ball_yoke')]
    del S.TURRETS['radio']
    parts += rings
    parts += MP.turret_twin20('chin', 'fus_nose', S.TURRETS['chin']['pos'], V((0, 1, 0)), V((0, 0, 1)), (0.0, 0.30, -0.10), 0.27, MP.chin_drum)
    parts += MP.turret_twin20('tail', 'tail_gun', S.TURRETS['tail']['pos'], V((0, -1, 0)), V((0, 0, 1)), (0.0, 0.20, 0.0), 0.28, MP.tail_drum)
    parts += MP.laser_turret('top', 'B17G')
    parts += MP.laser_turret('ball', 'fus_waist')
    parts += MP.ventral_seal()                 # 1.9.1: closes the ring gap round the ventral laser drum
    parts += MP.pylons()
    parts += MP.sensors()
    if M.DECK195:          # 1.9.5: our own flight deck with single stock parts (msb_deck195) + the 1.9.1 WSO / EWO stations
        parts += MDK.build() + MST.build_stations() + MC.anchors()
    else:                  # 1.9.1-1.9.4: stock EW-25 flight deck + the WSO / EWO stations
        parts += (MST.build() if M.STOCK_DECK else MC.build_structure()) + MC.anchors()
    # CG estimate (information; the root stays at the B-17G CG: gear stance, flight model and ground model use that station)
    tot = 0.0; mom = V()
    for p in parts:
        mm = mass_of(p.name)
        if mm and p.mesh is not None and p.mesh.verts:
            c = sum(p.mesh.verts, V()) / len(p.mesh.verts)
            tot += mm; mom += c * mm
        elif mm:
            tot += mm; mom += p.pivot * mm
    cg_est = mom / tot
    for k_ in ('cheek_R', 'cheek_L'):          # b17g_detail._fus_excluded reads the cheek gun positions (none on the MSB)
        S.TURRETS[k_] = dict(pos=(0.0, -99.0, 0.0), fwd=(0, 1, 0), guns=[], station='-', trav=0.0, emin=0.0, emax=0.0)
    istats = add_internals(parts)
    for k_ in ('cheek_R', 'cheek_L'):
        del S.TURRETS[k_]
    print('[msb] internals tris per part:', sum(istats.values()))
    cg = V((0.00013848971866536885, 0.7153460383415222, 0.39707520604133606))
    # rename the centre section B17G -> M.KEY (MSB17; Unity: the FBX object MSB17 becomes fus_center)
    for p in parts:
        if p.name == 'B17G':
            p.name = M.KEY
        if p.parent == 'B17G':
            p.parent = M.KEY
        if p.info and p.info.get('part') == 'B17G':
            p.info['part'] = M.KEY
    root = Part(f'{M.KEY}_root', None, pivot=cg, info={'kind': 'root_at_cg'})
    parts.insert(0, root)
    for p in parts:
        if p.parent is None and p.name != root.name:
            p.parent = root.name
    names = {p.name for p in parts}
    bad = [(p.name, p.parent) for p in parts if p.parent and p.parent not in names]
    if bad:
        raise SystemExit(f'[msb] parts with a missing parent: {bad[:10]}')
    dropped = 0
    for p in parts:
        if p.mesh is None:
            continue
        keep = []
        for f in p.mesh.faces:
            P_ = [p.mesh.verts[k] for k in f['idx']]
            a2 = sum(((P_[k] - P_[0]).cross(P_[k + 1] - P_[0])).length for k in range(1, len(P_) - 1)) / 2
            if a2 > 1e-8:
                keep.append(f)
        dropped += len(p.mesh.faces) - len(keep); p.mesh.faces = keep
    print(f'[msb] zero-area faces dropped: {dropped}')
    area, mpu = B.pack_livery(parts)
    coll = bpy.data.collections.new(M.KEY); bpy.context.scene.collection.children.link(coll)
    objs = B.create_objects(parts, mats, coll)
    tex_dir = os.path.join(os.path.dirname(out), '..', 'textures_msb1780')
    os.makedirs(tex_dir, exist_ok=True)
    MP.write_prop_texture(os.path.abspath(os.path.join(tex_dir, 'msb17_pr_hsprop_b.png')))
    import b17g_zfix as ZF
    ZF.resolve([o for o in coll.objects if o.type == 'MESH'], log_path=os.path.join(os.path.dirname(out), 'msb1780_zfix.json'))
    if M.SMOOTH197:
        import msb_smooth197 as SM197
        SM197.apply([o for o in coll.objects if o.type == 'MESH'])
    import b17g_normals as NRM
    NRM.REGIONS = [(M.KEY if r[0] == 'B17G' else r[0],) + tuple(r[1:]) for r in NRM.REGIONS]
    NRM.apply({o.name: o for o in coll.objects})
    tris = sum(len(pp.vertices) - 2 for o in coll.objects if o.type == 'MESH' for pp in o.data.polygons)
    m_, le_mac, x_mac = (lambda: (None, None, None))()
    turrets = []
    for t in ('chin', 'top', 'ball', 'tail'):
        T = S.TURRETS[t]
        laser = t in M.LASERS
        guns = [dict(gun=dict(name=f'{t}_gun0'), muzzle=dict(name=f'{t}_muzzle{k}')) for k in range(2)] if not laser else []
        turrets.append(dict(key=t, weapon='laser' if laser else '20mm', mount=dict(name=f'{t}_mount'), az=dict(name=f'{t}_az'), el=dict(name=f'{t}_el'),
                            station=T['station'], guns=guns, aperture=dict(name=f'{t}_aperture') if laser else None,
                            Turret=dict(traverseRange=T['trav'], traverseRate=150 if laser else 50, minElevation=T['emin'], maxElevation=T['emax'], elevationRate=60 if laser else 45)))
    contract = dict(
        aircraft=M.KEY, frame='blender: x right, y forward, z up; metres; gear down', cg=list(cg), cg_estimate=list(cg_est), mass_estimate_kg=tot,
        prop=dict(radius=S.PROP_R, blades=S.PROP_BLADES, rows={'front': M.ROW_TURN['front'], 'aft': M.ROW_TURN['aft']},
                  engines={str(v): k for k, v in S.ENGINE_NUM.items()}, planes={k: list(M.prop_planes(k)) for k in ('inner', 'outer')}),
        gear=dict(main_pivot=S.MAIN_PIVOT, main_leg=S.MAIN_LEG, main_fold_deg=S.MAIN_FOLD, main_fold_sense='forward-up', wheel_r=S.WHEEL_R,
                  tail_pivot=S.TAIL_PIVOT, tail_axle_down=S.TAIL_AXLE_DOWN, tail_fold_deg=S.TAIL_FOLD, tail_fold_sense='aft-up'),
        bay=dict(y=S.BAY_Y, half_w=S.BAY_HALF_W, roof=S.BAY_ROOF_Z, hardpoints={k: list(v) for k, v in M.BAY_HP.items()},
                 stores={k: list(v) for k, v in M.STORES.items()}, door_open_deg=92),
        side_bays=dict(M.SIDE_BAY), pylons={f'hp_{k}_{s}': M.PYLONS[k] for k in M.PYLONS for s in ('L', 'R')},
        turrets=turrets, tris=tris, metres_per_uv=mpu,
        eyes=dict(pilot=list(M.EYE_PILOT), copilot=list(M.EYE_COPILOT), wso=list(M.EYE_WSO), ewo=list(M.EYE_EWO)),
        screens=[p.name for p in parts if p.info.get('kind') == 'screen'],
        stock_anchors={p.name: p.info.get('stock') for p in parts if p.info.get('kind') == 'stock_anchor'},
        stock_parts=([dict(name=n, mesh=m, template=t, pos=list(M.stock_pos(u)),
                          materials={'EW1_cockpit_int': ['EW1_cockpit', 'Touchscreen_off'], 'EW1_targetScreen': ['tacScreenDisplay'],
                                     'EW1_joystick': ['EW1_cockpit', 'hotas'], 'EW1_throttle': ['EW1_cockpit']}[m]) for n, m, t, u in M.STOCK_KIT] if M.STOCK_DECK else
                     [dict(name=n, mesh=m, materials=ms, pos=list(pp), layer=14 if n.startswith('warnlamp_') else None,
                           role={'sfb_joystick': 'stick', 'sfb_throttle': 'throttle', 'EW1_warningLights': 'missile_warning_lamp'}[m]) for n, m, ms, pp in MDK.kit()] if M.DECK195 else []),
        deck195=dict(screens={p.name: p.info['content'] for p in parts if p.info.get('deck')}, stick_range=M.SFB_STICK_RANGE, throttle_range=M.SFB_THROTTLE_RANGE,
                     panel_x=MDK.PANEL_X, pedestal_x=MDK.PED_X, floor_z=MDK.FLOOR_Z, well_z=MDK.WELL_Z) if M.DECK195 else None,
        controls=dict(objects=[]), levers=dict(movers=[dict(name='cockpit_throttle', stock_driver=dict(component='Cockpit.throttles', range=M.SFB_THROTTLE_RANGE if M.DECK195 else (54.0 if M.STOCK_DECK else 25.0)), rest_deg=0.0)]), gauges=dict(movers=[]),
        crew=dict(stations=[dict(role=p.info['role'], part=p.info['part'], eye=dict(name=p.name), exit_hatch=p.info['exit_hatch'])
                            for p in sorted(parts, key=lambda q: q.info.get('index', 99)) if p.info.get('kind') == 'crew_eye']),
        hatches=dict(hatches=[dict(hatch=dict(name=n), hinge=dict(name=n + '_hinge'), hingeAngle=0.0, parent_part=pp, jettison=True)
                              for n, pp in (('hatch_pilot_L', 'fus_cockpit'), ('hatch_pilot_R', 'fus_cockpit'), ('hatch_wso', 'fus_nose'), ('hatch_ewo', M.KEY))]),
    )
    bpy.context.scene['b25_build_stats'] = json.dumps(dict(metres_per_uv=mpu, tris=tris))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(contract, open(os.path.join(os.path.dirname(out), 'msb1780_contract.json'), 'w'), indent=1)
    bpy.ops.wm.save_as_mainfile(filepath=out)
    print(f'[msb] saved {out}: {len(coll.objects)} objects, {tris} tris, CG estimate {tuple(round(v, 3) for v in cg_est)} ({tot:.0f} kg in the table), '
          f'root at the B-17G CG {tuple(round(v, 3) for v in cg)}, {mpu:.2f} m per UV')


main()
