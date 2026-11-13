"""1.8.13 round 2 (offline L): where the War Thunder B-17G guns sit relative to OUR turret pivots (study only; the WT OBJ is the user's local
reference copy, read here, never copied or shipped).

  blender -b assets/model_b17g/b17g.blend -P blender/anm2/measure_wt_mounts.py -- <WT gun obj dir> <out json>

WT -> ours: (x, y, z)_WT -> (-x K, z K, y K), K = 31.62 / 31.258 (blender/b17g/render_b17g.py, the scale the airframe was built to).
Per WT gun: bore axis (PCA of the gun's vertices, muzzle = the thinner end), muzzle tip, receiver rear; split twins by side. Per station:
the trunnion (muzzle - 0.725 m on the bore: our gun's trunnion-to-muzzle length) in OUR el frame at rest, i.e. along the bore from the
elevation pivot (d), sideways (x) and up (y), and how far the WT bore direction is from our rest aim.
"""
import bpy, sys, os, json, math
import numpy as np
from mathutils import Vector

a = sys.argv[sys.argv.index('--') + 1:]
OBJDIR, OUTJ = a[0], a[1]
K = 31.62 / 31.258
TIP = 0.725
STATIONS = {'chin': ['gun1_79_0', 'gun1_79_1'], 'top': ['gun2_77_0', 'gun2_77_1'], 'ball': ['gun3_3_0', 'gun3_3_1', 'gun3_3_2', 'gun3_3_3'],
            'tail': ['gun4_71_0', 'gun4_71_1'], 'radio': ['gun5_85_0'], 'waist_R': ['gun6_73_0'], 'waist_L': ['gun7_75_0'],
            'cheek_R': ['gun8_83_0', 'gun8_83_1'], 'cheek_L': ['gun9_81_0', 'gun9_81_1']}


def load(name):
    V = []
    for l in open(os.path.join(OBJDIR, name + '.obj'), errors='ignore'):
        if l.startswith('v '):
            x, y, z = map(float, l.split()[1:4]); V.append((-x * K, z * K, y * K))
    return np.array(V)


def axis_of(P):
    c = P.mean(0); u, s, vt = np.linalg.svd(P - c, full_matrices=False); ax = vt[0]
    t = (P - c) @ ax; lo, hi = t.min(), t.max()
    def spread(m):
        q = P[m]; r = (q - q.mean(0)) - np.outer((q - q.mean(0)) @ ax, ax); return np.linalg.norm(r, axis=1).mean()
    if spread(t > hi - 0.25) > spread(t < lo + 0.25):
        ax = -ax; t = -t; lo, hi = t.min(), t.max()
    tip = P[t > hi - 0.01].mean(0)                     # muzzle face centre
    return ax, tip, hi - lo


out = {}
for st, names in STATIONS.items():
    P = np.vstack([load(n) for n in names if os.path.exists(os.path.join(OBJDIR, n + '.obj'))])
    ax, _, L = axis_of(P)
    # split twins: project on the axis-perpendicular direction of largest spread
    c = P.mean(0); Q = (P - c) - np.outer((P - c) @ ax, ax)
    u, s, vt = np.linalg.svd(Q, full_matrices=False); side = vt[0]
    guns = [P]
    if st in ('chin', 'top', 'ball', 'tail') and s[0] > 0.05 * len(P) ** 0.5:
        k = Q @ side; guns = [P[k < 0], P[k >= 0]]
    el = bpy.data.objects.get(f'{st}_el')
    if el is None:
        print('MISSING', st); continue
    M = el.matrix_world; R = M.to_3x3().normalized(); piv = M.translation
    aim = R @ Vector((0, 1, 0))                         # Blender local Y = our rest aim (Unity +Z)
    rows = []
    for g in guns:
        gax, tip, L = axis_of(g)
        tr = Vector(tip) - Vector(gax) * TIP
        rel = R.inverted() @ (tr - piv)                 # el-local (Blender: x right, y aim, z up)
        rear = min(((Vector(p) - piv) @ Vector(gax)) for p in g)
        # frame-free description (the WT turrets are not all at our rest aim): along the WT bore from our pivot (d), sideways (x, + = the
        # gun's right) and up (y) in the gun frame whose up is our el up projected off the bore
        gv = Vector(gax); upv = R @ Vector((0, 0, 1)); upv = (upv - upv.dot(gv) * gv).normalized(); sv = gv.cross(upv)
        dvec = tr - piv
        rows.append(dict(gun_frame=dict(x=round(dvec.dot(sv), 3), y=round(dvec.dot(upv), 3), d=round(dvec.dot(gv), 3)),
                         trunnion_local=[round(rel.x, 3), round(rel.y, 3), round(rel.z, 3)], muzzle=[round(v, 3) for v in tip],
                         length=round(float(L), 3), rear_along_bore=round(float(rear), 3),
                         bore_vs_rest_aim_deg=round(math.degrees(Vector(gax).angle(aim)), 1)))
    out[st] = dict(pivot=[round(v, 3) for v in piv], guns=rows)
    print('WT', st, json.dumps(out[st]))
json.dump(out, open(OUTJ, 'w'), indent=1)
