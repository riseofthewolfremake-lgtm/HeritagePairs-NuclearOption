"""1.7.12: analytic skin normals around the turret openings.

The round-hole cut (b17g_detail.round_hole) splits the faces the opening crosses into small pieces. Vertex normals averaged over
those pieces differ from the averages over the big neighbouring faces (and T-junction points on the parent edges only see one side),
so the cut region shaded as stepped lighter rectangles (in game 1.7.7-1.7.11, and in a normals-only render of the blend and of the
exported FBX: nuclearoption-ref/study/b17g/r1712). Fix at the root: every smooth paint corner of the fuselage skin near an opening
gets the normal of the true (uncut) fuselage surface - the superellipse section of b17g_spec.fus_station - as a custom split normal.
The region is wide enough (RADIUS) that its edge lies on unsplit faces, where the analytic and the averaged normals agree within
a fraction of a degree. The FBX exporter writes custom normals, Unity imports them (ModelImporter importNormals = Import).
"""
import math
import bpy
from mathutils import Vector as V
import b17g_spec as S

# (object, opening centre (x, y), radius around it, z test)
REGIONS = [('B17G', (0.0, S.TURRETS['top']['pos'][1]), 1.30, lambda z: z > 1.30),
           ('fus_nose', (0.0, S.TURRETS['chin']['pos'][1]), 1.10, lambda z: z < 0.10)]
if S.NOSE1817:
    # 1.8.17: the exact window / opening cuts of the nose (b17g_nose1817.cut) split skin triangles the same way: analytic normals over the
    # nose and the forward cockpit section (y > 4.30), on the skin only (the keel fairing / K-5 frames are their own surfaces)
    REGIONS += [('fus_nose', (0.0, 5.8), 2.0, lambda z: True), ('fus_cockpit', (0.0, 4.85), 0.75, lambda z: True)]


def _on_skin(w, tol=0.03):
    top, bot, hw, n = S.fus_station(w.y)
    cz, hz = (top + bot) / 2, (top - bot) / 2
    return abs((abs(w.x) / hw) ** n + (abs(w.z - cz) / hz) ** n - 1.0) < tol


def skin_normal(p):
    top, bot, hw, n = S.fus_station(p.y)
    cz, hz = (top + bot) / 2, (top - bot) / 2
    dx, dz = p.x, p.z - cz
    gx = n * abs(dx) ** (n - 1) * math.copysign(1.0, dx) / hw ** n if abs(dx) > 1e-9 else 0.0
    gz = n * abs(dz) ** (n - 1) * math.copysign(1.0, dz) / hz ** n if abs(dz) > 1e-9 else 0.0
    g = V((gx, 0.0, gz))
    return g.normalized() if g.length > 1e-12 else None


def apply(objs_by_name):
    report = {}
    for name, (cx, cy), rad, ztest in REGIONS:
        o = objs_by_name.get(name)
        if o is None or o.type != 'MESH':
            continue
        me = o.data; M = o.matrix_world; Mi3 = M.to_3x3().inverted()
        mats = [m.name if m else '' for m in me.materials]
        cn = [V(l.vector) for l in me.corner_normals]
        changed = 0
        for p in me.polygons:
            if not p.use_smooth or mats[p.material_index] != 'paint':
                continue
            for li in p.loop_indices:
                w = M @ me.vertices[me.loops[li].vertex_index].co
                if math.hypot(w.x - cx, w.y - cy) > rad or not ztest(w.z):
                    continue
                if S.NOSE1817 and name in ('fus_nose', 'fus_cockpit') and (not _on_skin(w) or w.y > S.NOSE_GLASS_Y - 0.005):
                    continue
                nw = skin_normal(w)
                if nw is None or nw.dot(M.to_3x3() @ cn[li]) < 0.9:      # only the outer skin (the inner copies face inwards)
                    continue
                cn[li] = (Mi3 @ nw).normalized()      # rotation-only object matrices: inverse = transpose
                changed += 1
        me.normals_split_custom_set(cn)
        report[name] = changed
    print('[normals] analytic skin normals set:', report)
    return report
