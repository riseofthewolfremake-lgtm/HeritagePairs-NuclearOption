"""1.9.14 round 7: GA-25X throttle lever vs the radio panel / pedestal over the lever's whole travel, measured on the MESH.

  blender --background <ga25x.blend> --python check_throttle_clear1914.py -- <out.json> [--step 0.5] [--shift-y <m>]

--shift-y moves the lever mesh forward before the sweep: the stub test's FAILURE PATH (the detector must report a collision with
the radio panel when the lever is pushed into it).

How the game moves it (decompiled Cockpit.cs:41, Cockpit.Throttle with rotation = true): transform.localEulerAngles =
(inputs.throttle * range, 0, 0), throttle 0..1; unity/Editor/GA25XBuild.cs CockpitAnimation wires the 'levers' entry of the
contract (cockpit_throttle, range 52) through DrivenFrame (identity pivot here, so no extra frame). cockpit_throttle sits at
identity in the blend, so its local X = world X, and a positive Unity X rotation turns up (+Y) toward forward (+Z): the lever
top swings FORWARD by throttle * 52 deg (IDLE -46 deg -> MAX +6 deg from up, ga25x_cockpit.py ART_DEG / LEVER_DEG). The script
checks that sense on the mesh (the arm's top must move to +y) instead of assuming it.

The moving mesh = cockpit_throttle_arm (our split lever + fal grip heads; StockThrottleMesh = false: no stock sfb_throttle lever).
Fixed geometry = cockpit_interior, in groups:
  radio      the radio / IFF panel art + its knobs and toggles (faces wholly at y >= 4.245 and under the radio top z 0.4595)
  pedestal   the quadrant housing, trim rails, deck in front of the arc, friction knob (|x| < 0.135, y < 4.24) except the slot
  slot       the quadrant slot walls / floor the stalk runs in (|x| <= slot half width + 2 mm) - by design a few mm
  panel      the instrument panel incl. its underside / sub strips / anything else ahead of y 4.15 not in the groups above
  other      everything else in cockpit_interior
For every step: the minimum distance arm -> group (arm vertices to the group's faces AND group vertices to the arm's faces,
BVH nearest), and whether any arm triangle intersects a group triangle (BVH overlap).
"""
import bpy, sys, os, json, math
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

args = sys.argv[sys.argv.index('--') + 1:]
out = args[0]
step = float(args[args.index('--step') + 1]) if '--step' in args else 0.5
shift_y = float(args[args.index('--shift-y') + 1]) if '--shift-y' in args else 0.0
RANGE = 52.0
O = bpy.data.objects
piv = O['cockpit_throttle']
arm = O['cockpit_throttle_arm']
ci = O['cockpit_interior']
pv = piv.matrix_world.translation.copy()
axis = (piv.matrix_world.to_3x3() @ Vector((1, 0, 0))).normalized()


def world_mesh(ob):
    me = ob.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
    mw = ob.matrix_world
    V = np.array([tuple(mw @ v.co) for v in me.vertices])
    F = [tuple(p.vertices) for p in me.polygons]
    return V, F


AV, AF = world_mesh(arm)
AV[:, 1] += shift_y
IV, IF = world_mesh(ci)
SLOT_HX = 0.025
fz_top = 0.459                                            # radio panel top (PANEL_BOTTOM + 0.004)


def group_of(ids):
    c = IV[list(ids)].mean(0)
    x, y, z = c
    if abs(x) <= SLOT_HX + 0.002 and y < 4.24 and z < fz_top:
        return 'slot'
    vs = IV[list(ids)]
    if abs(x) < 0.12 and vs[:, 1].min() >= 4.245 and vs[:, 2].max() <= fz_top + 0.0005:
        return 'radio'
    if abs(x) < 0.135 and y < 4.24 and z < fz_top:
        return 'pedestal'
    if y > 4.15:
        return 'panel'
    return 'other'


groups = {}
for f in IF:
    groups.setdefault(group_of(f), []).append(f)
trees = {}
for g, fs in groups.items():
    used = sorted({i for f in fs for i in f})
    remap = {i: k for k, i in enumerate(used)}
    gv = [Vector(IV[i]) for i in used]
    trees[g] = (BVHTree.FromPolygons(gv, [tuple(remap[i] for i in f) for f in fs]), np.array([tuple(v) for v in gv]))


def rot(theta):
    return Matrix.Rotation(theta, 3, axis)


# sense check: which sign of rotation moves the arm's top forward (+y)?
top = Vector(AV[np.argmax(((AV - np.array(pv)) ** 2).sum(1))])
sgn = 1.0 if (rot(math.radians(10)) @ (top - pv)).y > (top - pv).y else -1.0
rows, worst = [], {}
n = int(round(RANGE / step))
for k in range(n + 1):
    deg = k * step
    R = rot(sgn * math.radians(deg))
    av = [pv + R @ (Vector(v) - pv) for v in AV]
    at = BVHTree.FromPolygons(av, AF)
    rec = dict(deg=deg, throttle=round(deg / RANGE, 4))
    for g, (t, gv) in trees.items():
        d1 = min(((r_[3], tuple(v), tuple(r_[0])) for v in av for r_ in (t.find_nearest(v),)), key=lambda q: q[0])
        d2 = min(((r_[3], tuple(r_[0]), tuple(v)) for v in gv for r_ in (at.find_nearest(Vector(v)),)), key=lambda q: q[0])
        d = min(d1, d2, key=lambda q: q[0])          # (distance, point on the lever, point on the fixed group)
        hit = len(at.overlap(t)) > 0
        rec[g] = dict(min_mm=round(d[0] * 1000, 2), at=[round(float(c), 4) for c in d[1]], fixed=[round(float(c), 4) for c in d[2]], intersect=hit)
    rows.append(rec)
for g in trees:
    b = min(rows, key=lambda r: r[g]['min_mm'])
    worst[g] = dict(min_mm=b[g]['min_mm'], deg=b['deg'], at=b[g]['at'], fixed=b[g]['fixed'], intersect=any(r[g]['intersect'] for r in rows),
                    at_max_mm=rows[-1][g]['min_mm'])
tip0 = top
tipM = pv + rot(sgn * math.radians(RANGE)) @ (top - pv)
import hashlib
res = dict(blend=bpy.data.filepath, blend_sha1=hashlib.sha1(open(bpy.data.filepath, 'rb').read()).hexdigest(), shift_y=shift_y, pivot=[round(c, 4) for c in pv], axis=[round(c, 4) for c in axis], sense=sgn, range_deg=RANGE, step_deg=step,
           arm_verts=len(AV), group_faces={g: len(f) for g, f in groups.items()},
           top_idle=[round(c, 4) for c in tip0], top_max=[round(c, 4) for c in tipM], worst=worst, sweep=rows)
json.dump(res, open(out, 'w'), indent=1)
for g, w in sorted(worst.items()):
    print(f"[throttle_clear] {g:6s} min {w['min_mm']:7.2f} mm at {w['deg']:5.1f} deg ({w['deg'] / RANGE:.2f} throttle) lever {w['at']} fixed {w['fixed']} intersect {w['intersect']}")
print(f"[throttle_clear] sense {sgn:+.0f}: lever top idle {res['top_idle']} -> max {res['top_max']}; {len(rows)} steps -> {out}")
