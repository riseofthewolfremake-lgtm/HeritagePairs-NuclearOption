"""Heritage Pairs 1.8.13 round 2 (offline L): our own Browning AN/M2 .50, hand-modelled in Blender Python with baked texture.
No fal, no game or War Thunder geometry / textures: the WT B-17G guns (local study copy, nuclearoption-ref/study/anm2_ref) were used for shape
and proportions only, read off their side / top / front views at 1 px = 1 mm (gun axis s from the trunnion front, v up from the bore).

  blender -b --factory-startup -P blender/anm2/anm2_model.py -- [--out assets/model_anm2] [--res 1024]

Builds four bodies and the grips, all in one gun frame (origin ON THE BORE at the trunnion = front of the receiver, +fire, up):
  flex  : the flexible gun (hand-held positions): retracting slide + charging lever with a wooden knob on the FEED side, perforated
          barrel jacket (holes = alpha cut-out in its own material, the barrel inside), booster, front sight
  turret: the turret gun: short retracting slide only, plain barrel, buffer-tube stub behind the backplate
  each in a left-feed version (feed cover / slide on -X) and a baked mirror (right feed): flex_L / flex_R / turret_L / turret_R
  grips : U-shaped spade-grip frame, two wooden handles, butterfly trigger (separate mesh, hand-held positions only)
Common: stepped receiver outline (rear section taller, step down at the trunnion block), side-plate rails round a recessed panel, rivet
rows and panel lines (texture), top cover with front latch and rear hinge, rear-sight leaf, feed-way cover with the feed-pawl housing,
link-ejection lip on the other side, trunnion block with barrel-support ring and trunnion pin, mounting eye under the receiver, backplate.
Texture: UV unwrap (smart project, jacket / barrels cylindrical), Cycles bake of AO, edges (bevel-normal difference) and object
position; composed in numpy: parkerized steel with edge wear, darker recesses, rivets / panel lines placed by gun-frame position, blued
barrel, wood grain on the knob and grips; jacket texture with real cut-out holes (alpha) in two staggered rows each side.
Writes assets/model_anm2/anm2_mesh.json (Unity gun frame, winding / normals converted), anm2_b.png, anm2_jacket.png.
"""
import bpy, bmesh, sys, os, json, math
import numpy as np
from mathutils import Vector, Matrix

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
OUT = os.path.abspath(argv[argv.index('--out') + 1]) if '--out' in argv else os.path.join(ROOT, 'assets', 'model_anm2')
RES = int(argv[argv.index('--res') + 1]) if '--res' in argv else 1024
TIP = 0.725
os.makedirs(OUT, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
# Blender gun frame: X = the gun's right, Y = fire (s), Z = up (v)


class Part:
    """bmesh accumulator with per-face material index: 0 steel, 1 jacket (cut-out), 2 wood, 3 dark (bore / slots)."""
    def __init__(s):
        s.bm = bmesh.new()

    def box(s, x0, x1, s0, s1, v0, v1, mat=0):
        r = bmesh.ops.create_cube(s.bm, size=1.0)
        vs = r['verts']
        for v in vs:
            v.co = Vector(((x0 + x1) / 2 + v.co.x * (x1 - x0), (s0 + s1) / 2 + v.co.y * (s1 - s0), (v0 + v1) / 2 + v.co.z * (v1 - v0)))
        s._mat(vs, mat)

    def prism_x(s, x0, x1, poly, mat=0, bevel=0.0):
        """extrude a side-profile polygon [(s, v), ...] (counter-clockwise seen from +X) between x0 and x1."""
        n = len(poly)
        a = [s.bm.verts.new((x0, p[0], p[1])) for p in poly]
        b = [s.bm.verts.new((x1, p[0], p[1])) for p in poly]
        f0 = s.bm.faces.new(list(reversed(a))); f1 = s.bm.faces.new(b)
        fs = [f0, f1]
        for i in range(n):
            j = (i + 1) % n
            fs.append(s.bm.faces.new([a[i], a[j], b[j], b[i]]))
        for f in fs:
            f.material_index = mat
        bmesh.ops.recalc_face_normals(s.bm, faces=fs)
        if bevel > 0:                                          # chamfered edges: catch the light / edge wear like a machined part
            es = list({e for f in fs for e in f.edges})
            r = bmesh.ops.bevel(s.bm, geom=es + list({v for e in es for v in e.verts}), offset=bevel, segments=1, affect='EDGES', profile=0.5)
            for f in r['faces']:
                f.material_index = mat

    def cyl(s, p0, p1, r0, r1=None, n=12, mat=0, cap0=True, cap1=True):
        r1 = r0 if r1 is None else r1
        p0, p1 = Vector(p0), Vector(p1); ax = (p1 - p0).normalized()
        t = Vector((1, 0, 0)) if abs(ax.x) < 0.9 else Vector((0, 0, 1)); u = ax.cross(t).normalized(); w = ax.cross(u)
        a = [s.bm.verts.new(p0 + (u * math.cos(2 * math.pi * k / n) + w * math.sin(2 * math.pi * k / n)) * r0) for k in range(n)]
        b = [s.bm.verts.new(p1 + (u * math.cos(2 * math.pi * k / n) + w * math.sin(2 * math.pi * k / n)) * r1) for k in range(n)]
        fs = [s.bm.faces.new([a[k], a[(k + 1) % n], b[(k + 1) % n], b[k]]) for k in range(n)]
        if cap0: fs.append(s.bm.faces.new(list(reversed(a))))
        if cap1: fs.append(s.bm.faces.new(b))
        for f in fs:
            f.material_index = mat
        bmesh.ops.recalc_face_normals(s.bm, faces=fs)
        return fs

    def ring(s, c, axis, r_out, r_in, half_w, n=12, mat=0):
        """thick ring (eye / support ring) around axis through c."""
        c = Vector(c); ax = Vector(axis).normalized()
        t = Vector((0, 1, 0)) if abs(ax.y) < 0.9 else Vector((0, 0, 1)); u = ax.cross(t).normalized(); w = ax.cross(u)
        pts = lambda r, o: [s.bm.verts.new(c + ax * o + (u * math.cos(2 * math.pi * k / n) + w * math.sin(2 * math.pi * k / n)) * r) for k in range(n)]
        oa, ob, ia, ib = pts(r_out, -half_w), pts(r_out, half_w), pts(r_in, -half_w), pts(r_in, half_w)
        fs = []
        for k in range(n):
            j = (k + 1) % n
            fs += [s.bm.faces.new([oa[k], oa[j], ob[j], ob[k]]), s.bm.faces.new([ib[k], ib[j], ia[j], ia[k]]),
                   s.bm.faces.new([ob[k], ob[j], ib[j], ib[k]]), s.bm.faces.new([ia[k], ia[j], oa[j], oa[k]])]
        for f in fs:
            f.material_index = mat
        bmesh.ops.recalc_face_normals(s.bm, faces=fs)

    def _mat(s, vs, mat):
        for f in {f for v in vs for f in v.link_faces}:
            f.material_index = mat

    def obj(s, name):
        me = bpy.data.meshes.new(name); s.bm.to_mesh(me); s.bm.free()
        o = bpy.data.objects.new(name, me); sc.collection.objects.link(o)
        return o


# proportions read off the WT flex gun (gun6, its bore frame: blender/anm2 study, wt_profile): receiver v -0.062 .. +0.080 at the rear,
# front section top +0.075, trunnion block bottom -0.069, side plates x +-0.041, jacket r 0.026
HW = 0.039                       # receiver half width (side plates)
RT, RB = 0.080, -0.058           # receiver top (rear section) / bottom, from the bore
FT = 0.070                       # front section top (step)
TB_T, TB_B = 0.044, -0.066       # trunnion block top / bottom (the step down)
S_REAR, S_STEP, S_TB = -0.645, -0.250, -0.055


def receiver(p, feed=-1, flex=True):
    """common receiver; feed = -1: feed / slide side is -X (left-feed body)."""
    prof = [(S_REAR, RB), (S_TB, RB), (S_TB, FT), (S_STEP, FT), (S_STEP, RT), (S_REAR, RT)]
    p.prism_x(-HW + 0.002, HW - 0.002, prof, bevel=0.0025)                          # body, recessed between the rails
    for sgn in (-1, 1):                                                              # side-plate rails (top / bottom) and the rear frame
        x0, x1 = (HW - 0.002, HW + 0.002) if sgn > 0 else (-HW - 0.002, -HW + 0.002)
        p.box(x0, x1, S_REAR, S_TB, RB, RB + 0.014)
        p.box(x0, x1, S_REAR, S_STEP, RT - 0.014, RT)
        p.box(x0, x1, S_STEP, S_TB, FT - 0.012, FT)
        p.box(x0, x1, S_REAR, S_REAR + 0.045, RB, RT)
    # trunnion block (step down), barrel-support ring, trunnion pin through it
    p.prism_x(-0.040, 0.040, [(S_TB, TB_B), (0.0, TB_B), (0.0, TB_T), (S_TB, TB_T)])
    p.ring((0, 0.010, 0), (0, 1, 0), 0.030, 0.0165, 0.012, n=16)
    p.cyl((-0.046, -0.028, -0.022), (0.046, -0.028, -0.022), 0.0075, n=10)          # trunnion pin
    p.cyl((-0.0465, -0.028, -0.022), (-0.0475, -0.028, -0.022), 0.004, n=8, mat=3)   # pin hole end (dark)
    p.cyl((0.0465, -0.028, -0.022), (0.0475, -0.028, -0.022), 0.004, n=8, mat=3)
    # mounting eye under the receiver (web + ring)
    p.box(-0.006, 0.006, -0.445, -0.415, RB - 0.020, RB)
    p.ring((0, -0.430, RB - 0.032), (1, 0, 0), 0.016, 0.008, 0.006, n=12)
    # top cover: plate, front latch, rear hinge, rear-sight leaf
    p.box(-HW + 0.003, HW - 0.003, -0.515, -0.255, RT, RT + 0.006)
    p.box(-HW + 0.003, HW - 0.003, -0.255, -0.065, FT, FT + 0.006)
    p.box(-0.014, 0.014, -0.105, -0.068, FT + 0.006, FT + 0.018)                     # latch
    p.cyl((-0.030, -0.522, RT + 0.002), (0.030, -0.522, RT + 0.002), 0.007, n=10)    # rear hinge
    if flex:                                                                         # rear-sight leaf (hand-held guns; turret guns use the turret sight)
        p.box(-0.012, 0.012, -0.470, -0.462, RT + 0.006, RT + 0.034)
        p.box(-0.004, 0.004, -0.470, -0.462, RT + 0.034, RT + 0.040)
    # feed side: feed-way cover / feed-pawl housing with its slot, belt tray lip; other side: link-ejection lip
    fx = feed * (HW + 0.002)
    p.box(min(fx, fx + feed * 0.016), max(fx, fx + feed * 0.016), -0.215, -0.075, -0.004, 0.050)
    p.box(min(fx, fx + feed * 0.022), max(fx, fx + feed * 0.022), -0.200, -0.090, -0.012, -0.004)
    p.box(min(fx + feed * 0.016, fx + feed * 0.017), max(fx + feed * 0.016, fx + feed * 0.017), -0.200, -0.090, 0.012, 0.030, mat=3)   # feed slot
    ox = -feed * (HW + 0.002)
    p.box(min(ox, ox - feed * 0.006), max(ox, ox - feed * 0.006), -0.200, -0.085, -0.030, -0.014)
    # feed-way opening (dark, both sides) at the top of the front section
    for sgn in (-1, 1):
        x0 = sgn * (HW + 0.002); x1 = sgn * (HW + 0.0035)
        p.box(min(x0, x1), max(x0, x1), -0.235, -0.095, FT - 0.036, FT - 0.016, mat=3)
    # feed tray / cover block across the top of the front section (wider than the receiver: both sides), side-plate slot at mid height
    p.box(-HW - 0.010, HW + 0.010, -0.235, -0.150, FT - 0.004, FT + 0.010)
    for sgn in (-1, 1):
        x0 = sgn * (HW + 0.002); x1 = sgn * (HW + 0.0032)
        p.box(min(x0, x1), max(x0, x1), -0.590, -0.420, -0.004, 0.006, mat=3)
    # backplate
    p.box(-0.038, 0.038, S_REAR - 0.016, S_REAR, RB + 0.002, RT - 0.004)


def slide(p, feed=-1, flex=True):
    """retracting slide on the feed side; flex: charging lever + wooden knob, turret: short slide only."""
    x = feed * (HW + 0.002)
    xo = lambda d: (min(x, x + feed * d), max(x, x + feed * d))
    if flex:
        p.box(*xo(0.006), -0.600, -0.330, 0.004, 0.018)                              # slide bar in its guide
        p.box(*xo(0.004), -0.600, -0.330, -0.002, 0.004, mat=3)                       # guide slot
        p.cyl((x + feed * 0.006, -0.470, 0.024), (x + feed * 0.014, -0.470, 0.024), 0.010, n=10)   # lever pivot boss
        piv = Vector((x + feed * 0.012, -0.470, 0.024)); end = piv + Vector((0, 0.050, -0.045))
        p.cyl(piv, end, 0.005, n=8)                                                   # lever
        p.cyl(end, end + Vector((feed * 0.055, 0, 0)), 0.011, n=10, mat=2)            # wooden knob, out sideways
    else:
        p.box(*xo(0.008), -0.420, -0.330, 0.004, 0.020)
        p.cyl((x + feed * 0.008, -0.345, 0.012), (x + feed * 0.020, -0.345, 0.012), 0.006, n=8)


def barrel(p, flex=True):
    # both variants: perforated jacket over the barrel (the WT turret gun2 and flex gun6 both carry it, the turret one painted holes)
    p.cyl((0, 0.0, 0), (0, 0.665, 0), 0.026, n=20, mat=1, cap0=False, cap1=False)                    # perforated jacket (cut-out)
    p.ring((0, 0.664, 0), (0, 1, 0), 0.026, 0.0160, 0.004, n=20)                                         # jacket front end
    p.ring((0, 0.004, 0), (0, 1, 0), 0.0275, 0.0145, 0.006, n=20)                                        # jacket rear collar
    p.cyl((0, -0.02, 0), (0, 0.690, 0), 0.0145, n=12, cap0=False)                                         # barrel inside
    if flex:
        p.box(-0.0025, 0.0025, 0.618, 0.632, 0.024, 0.046)                                               # front sight blade
    p.cyl((0, 0.680, 0), (0, TIP, 0), 0.0195, 0.0165, n=16)                                              # booster cone
    p.cyl((0, TIP - 0.0005, 0), (0, TIP + 0.0, 0), 0.0075, n=10, mat=3, cap0=False)                      # bore (dark)
    if not flex:
        p.cyl((0, S_REAR - 0.016, 0.010), (0, S_REAR - 0.036, 0.010), 0.018, n=12)                        # buffer-tube stub (20 mm: fits the domes)


def grips():
    p = Part()
    gs = S_REAR - 0.016
    # WT gun6 rear / top: a U frame on the backplate wider than the receiver (handles at x +-0.09), handles at its rear ends
    for vv in (0.052, -0.070):
        p.box(-0.094, 0.094, gs - 0.012, gs, vv, vv + 0.010)                         # cross bars on the backplate (top / bottom)
    for sx in (-1, 1):
        x = sx * 0.088
        p.box(x - 0.006, x + 0.006, gs - 0.070, gs - 0.010, 0.052, 0.062)            # top arm of the U
        p.box(x - 0.006, x + 0.006, gs - 0.070, gs - 0.010, -0.070, -0.060)          # bottom arm
        p.cyl((x, gs - 0.064, -0.060), (x, gs - 0.064, 0.052), 0.0145, n=10, mat=2)   # wooden spade handle
        p.cyl((x, gs - 0.064, 0.062), (x, gs - 0.064, 0.068), 0.008, n=8)             # handle cap
    p.box(-0.008, 0.008, gs - 0.040, gs, 0.012, 0.030)                               # trigger stem
    for sx in (-1, 1):                                                                # butterfly trigger lobes
        p.box(sx * 0.008 if sx > 0 else -0.030, 0.030 if sx > 0 else -0.008, gs - 0.044, gs - 0.034, 0.008, 0.036)
    return p.obj('grips')


def grips_twin(spacing=0.17):
    """1.8.13 r3: ONE spade-grip set for a close twin (B-25H tail, guns 0.17 m apart), centred between the guns (origin = the twin's centre
    line at the trunnion plane): cross bars over both backplates, one pair of wooden handles outboard, one trigger bar between them."""
    p = Part()
    gs = S_REAR - 0.016
    hx = spacing / 2 + 0.030
    for vv in (0.052, -0.070):
        p.box(-hx - 0.006, hx + 0.006, gs - 0.012, gs, vv, vv + 0.010)
    for sx in (-1, 1):
        x = sx * hx
        p.box(x - 0.006, x + 0.006, gs - 0.070, gs - 0.010, 0.052, 0.062)
        p.box(x - 0.006, x + 0.006, gs - 0.070, gs - 0.010, -0.070, -0.060)
        p.cyl((x, gs - 0.064, -0.060), (x, gs - 0.064, 0.052), 0.0145, n=10, mat=2)
        p.cyl((x, gs - 0.064, 0.062), (x, gs - 0.064, 0.068), 0.008, n=8)
    p.box(-hx + 0.016, hx - 0.016, gs - 0.050, gs - 0.040, 0.010, 0.020)              # trigger bar (both guns)
    for sx in (-1, 1):
        p.box(sx * 0.03 - 0.004, sx * 0.03 + 0.004, gs - 0.044, gs, 0.012, 0.020)       # its links to the two backplates' trigger stems
    return p.obj('grips_twin')


def body(name, flex, feed):
    # flex: the retracting slide + charging lever on the side AWAY from the feed (feed outboard from the wall box, lever toward the gunner's
    # free hand / the cabin: r2 - outboard it ran into the cheek / waist walls); turret: the short slide on the feed side
    p = Part(); receiver(p, feed, flex); slide(p, -feed if flex else feed, flex); barrel(p, flex)
    return p.obj(name)


def finish(o):
    """split sharp edges (35 deg) so flat panels shade flat and the barrels round."""
    bm = bmesh.new(); bm.from_mesh(o.data)
    sharp = [e for e in bm.edges if e.calc_face_angle(0) > math.radians(35)]
    bmesh.ops.split_edges(bm, edges=sharp)
    bm.to_mesh(o.data); bm.free()
    for f in o.data.polygons:
        f.use_smooth = True


# ---------------------------------------------------------------------------------------------------------------- UVs + bake
def uv_layout(o, jacket_only_mat=1):
    """smart project for everything; jacket faces get their own cylindrical UV in 0..1 (own texture)."""
    bpy.context.view_layer.objects.active = o
    for x in bpy.context.view_layer.objects: x.select_set(x == o)
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(55), island_margin=0.012, area_weight=0.0, scale_to_bounds=True)
    bpy.ops.object.mode_set(mode='OBJECT')
    uv = o.data.uv_layers.active
    for poly in o.data.polygons:
        if poly.material_index != jacket_only_mat:
            continue
        for li in poly.loop_indices:
            co = o.data.vertices[o.data.loops[li].vertex_index].co
            ang = (math.atan2(co.z, co.x) / (2 * math.pi)) % 1.0
            uv.data[li].uv = (ang, co.y / 0.665)
    # seam fix for the jacket wrap: faces crossing u 0 / 1
    for poly in o.data.polygons:
        if poly.material_index != jacket_only_mat:
            continue
        us = [uv.data[li].uv[0] for li in poly.loop_indices]
        if max(us) - min(us) > 0.5:
            for li in poly.loop_indices:
                if uv.data[li].uv[0] < 0.5:
                    uv.data[li].uv = (uv.data[li].uv[0] + 1.0, uv.data[li].uv[1])


def bake(o, kind, res):
    """Cycles bake of AO / edge mask / gun-frame position / material id into float arrays (res x res x 3), main UV, non-jacket faces."""
    sc.render.engine = 'CYCLES'; sc.cycles.samples = 64 if kind == 'ao' else 4; sc.cycles.device = 'CPU'
    if sc.world is None:
        sc.world = bpy.data.worlds.new('w')
    sc.world.light_settings.distance = 0.04
    img = bpy.data.images.new(f'{o.name}_{kind}', res, res, float_buffer=True)
    mat = bpy.data.materials.new(f'bk_{kind}'); mat.use_nodes = True; nt = mat.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial'); tex = nt.nodes.new('ShaderNodeTexImage'); tex.image = img; nt.nodes.active = tex
    if kind == 'ao':
        bs = nt.nodes.new('ShaderNodeBsdfDiffuse'); bs.inputs['Color'].default_value = (1, 1, 1, 1); nt.links.new(bs.outputs[0], out.inputs[0])
    else:
        em = nt.nodes.new('ShaderNodeEmission'); nt.links.new(em.outputs[0], out.inputs[0])
        if kind == 'pos':
            tc = nt.nodes.new('ShaderNodeTexCoord'); ma = nt.nodes.new('ShaderNodeVectorMath'); ma.operation = 'MULTIPLY_ADD'
            ma.inputs[1].default_value = (0.5, 0.5, 0.5); ma.inputs[2].default_value = (0.5, 0.5, 0.5)      # -1..1 m -> 0..1 (no negative emission)
            nt.links.new(tc.outputs['Object'], ma.inputs[0]); nt.links.new(ma.outputs[0], em.inputs['Color'])
        elif kind == 'edge':
            bv = nt.nodes.new('ShaderNodeBevel'); bv.inputs['Radius'].default_value = 0.0012; bv.samples = 16      # small: the rails / cover are 4-6 mm plates
            gm = nt.nodes.new('ShaderNodeNewGeometry'); dp = nt.nodes.new('ShaderNodeVectorMath'); dp.operation = 'DOT_PRODUCT'
            nt.links.new(bv.outputs[0], dp.inputs[0]); nt.links.new(gm.outputs['Normal'], dp.inputs[1])
            inv = nt.nodes.new('ShaderNodeMath'); inv.operation = 'SUBTRACT'; inv.inputs[0].default_value = 1.0
            nt.links.new(dp.outputs['Value'], inv.inputs[1]); nt.links.new(inv.outputs[0], em.inputs['Color'])
        elif kind == 'mat':
            at = nt.nodes.new('ShaderNodeAttribute'); at.attribute_name = 'matid'; nt.links.new(at.outputs['Color'], em.inputs['Color'])
    o.data.materials.clear(); o.data.materials.append(mat)
    bpy.context.view_layer.objects.active = o
    for x in bpy.context.view_layer.objects:
        x.select_set(x == o); x.hide_render = (x != o)        # the bodies share one frame: bake each alone (else AO sees the others)
    if kind == 'ao':
        bpy.ops.object.bake(type='AO', margin=4)
    else:
        bpy.ops.object.bake(type='EMIT', margin=4)
    a = np.array(img.pixels[:], dtype=np.float32).reshape(res, res, 4)[..., :3]
    return a                                                               # rows bottom-up (v up)


def matid_attr(o):
    """colour attribute with the material index per face corner (0 steel, 1 jacket, 2 wood, 3 dark) for the bake."""
    me = o.data
    attr = me.color_attributes.new('matid', 'FLOAT_COLOR', 'CORNER')
    for poly in me.polygons:
        c = (poly.material_index / 3.0, 0, 0, 1)
        for li in poly.loop_indices:
            attr.data[li].color = c


def noise2(res, scale, seed, w=None):
    """smooth value noise 0..1 (bilinear upsampling of a random grid; numpy only, Blender's Python has no PIL)."""
    w = res if w is None else w
    rng = np.random.default_rng(seed)
    g = rng.random((res // scale + 2, w // scale + 2)).astype(np.float32)
    yi = np.linspace(0, g.shape[0] - 1.001, res); xi = np.linspace(0, g.shape[1] - 1.001, w)
    y0 = yi.astype(int); x0 = xi.astype(int); fy = (yi - y0)[:, None]; fx = (xi - x0)[None, :]
    a = g[y0][:, x0]; b = g[y0][:, x0 + 1]; c = g[y0 + 1][:, x0]; d = g[y0 + 1][:, x0 + 1]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def to_srgb(c):
    """linear albedo (what compose works in) -> the sRGB bytes a colour texture holds (Unity imports anm2_b / jacket as sRGB)."""
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1 / 2.4) - 0.055)


def save_png(arr, path, srgb=False):
    """arr: rows top-down, RGB or RGBA 0..1 -> PNG through a Blender byte image (pixels stored as given; srgb: linear -> sRGB first)."""
    h, w = arr.shape[:2]
    if srgb:
        arr = np.concatenate([to_srgb(arr[..., :3]), arr[..., 3:]], axis=2)
    if arr.shape[2] == 3:
        arr = np.concatenate([arr, np.ones((h, w, 1), np.float32)], axis=2)
    im = bpy.data.images.new(os.path.basename(path), w, h, alpha=True)
    im.pixels[:] = np.flipud(arr).astype(np.float32).ravel()
    im.filepath_raw = path; im.file_format = 'PNG'; im.save()


def compose(ao, edge, pos, mid, res):
    """parkerized steel + wear + rivets / panel lines by gun-frame position; wood; dark ids; blued barrel near the bore axis."""
    ao = np.clip(ao[..., 0], 0, 1); edge = np.clip((edge[..., 0] - 0.04) * 5.0, 0, 1)
    pos = pos * 2.0 - 1.0
    X, S, Vv = pos[..., 0], pos[..., 1], pos[..., 2]
    m = np.rint(mid[..., 0] * 3.0)
    n1, n2, n3 = noise2(res, 4, 1), noise2(res, 32, 2), noise2(res, 6, 3)
    base = np.array([0.030, 0.030, 0.031], np.float32)    # r3: parkerized near-black, neutral (stock door gun basemap ~sRGB 33 x its AO ~0.6)
    steel = base[None, None, :] * (0.85 + 0.30 * n1[..., None]) * (0.9 + 0.2 * n2[..., None])
    # side faces of the receiver: rivet rows (top / bottom rail), panel lines, the recess darker
    side = (np.abs(X) > HW - 0.004) & (S < 0.0) & (S > -0.66)
    riv = np.zeros_like(X); hgt = np.zeros_like(X)                  # hgt: relief for the normal map (rivet domes +, panel lines -)
    for vrow, sa, sb in ((RT - 0.007, -0.60, -0.26), (RB + 0.007, -0.60, -0.07), (FT - 0.006, -0.24, -0.07), (-0.022, -0.22, -0.07)):
        sx = np.arange(sa, sb, 0.024 if vrow != -0.022 else 0.016)
        d_s = np.min(np.abs(S[..., None] - sx[None, None, :]), axis=-1)
        d = np.sqrt(d_s ** 2 + (Vv - vrow) ** 2)
        riv = np.maximum(riv, (d < 0.0028).astype(np.float32) * side)
        hgt = np.maximum(hgt, np.sqrt(np.clip(1 - (d / 0.0030) ** 2, 0, 1)) * side)
    pl = side & ((np.abs(S + 0.40) < 0.0012) | (np.abs(S + 0.25) < 0.0012) | (np.abs(S + 0.09) < 0.0012))
    recess = side & (Vv > RB + 0.014) & (Vv < RT - 0.014) & (np.abs(X) < HW + 0.0005)
    col = steel * (0.35 + 0.65 * ao[..., None] ** 1.4)
    col *= np.where(recess[..., None], 0.78, 1.0)
    col = np.where(pl[..., None], col * 0.45, col)
    col = np.where(riv[..., None] > 0, np.array([0.060, 0.060, 0.062], np.float32) * (0.6 + 0.4 * ao[..., None]), col)
    wear = (edge * np.clip((n3 - 0.35) * 4.0, 0, 1)).astype(np.float32)
    col = col * (1 - wear[..., None]) + np.array([0.16, 0.16, 0.16], np.float32) * wear[..., None] * (0.7 + 0.3 * ao[..., None])
    # blued barrel / booster (near the bore axis ahead of the trunnion)
    bar = (S > 0.0) & (np.sqrt(X ** 2 + Vv ** 2) < 0.022)
    col = np.where(bar[..., None], np.array([0.026, 0.026, 0.028], np.float32) * (0.6 + 0.4 * ao[..., None]) * (0.9 + 0.2 * n1[..., None]), col)
    # wood: grain along the handle / knob, darker in the grooves
    grain = 0.5 + 0.5 * np.sin((Vv * 900 + X * 300 + n2 * 9))
    wood = np.array([0.20, 0.095, 0.040], np.float32)[None, None, :] * (0.75 + 0.35 * grain[..., None]) * (0.8 + 0.3 * n1[..., None])
    wood = wood * (0.5 + 0.5 * ao[..., None]) + np.array([0.12, 0.07, 0.035], np.float32) * wear[..., None]
    col = np.where((m == 2)[..., None], wood, col)
    col = np.where((m == 3)[..., None], np.array([0.012, 0.012, 0.013], np.float32), col)
    hgt = hgt - 0.8 * pl
    hgt = hgt + 0.15 * (n1 - 0.5) * (m == 0)                        # cast / parkerized grain
    # tangent-space normal from the relief (u = columns, v = rows bottom-up as baked); no slope across UV-island borders
    gu = np.zeros_like(hgt); gv = np.zeros_like(hgt)
    gu[:, 1:-1] = (hgt[:, 2:] - hgt[:, :-2]) / 2; gv[1:-1, :] = (hgt[2:, :] - hgt[:-2, :]) / 2
    jump_u = np.zeros_like(hgt, bool); jump_v = np.zeros_like(hgt, bool)
    jump_u[:, 1:-1] = np.linalg.norm(pos[:, 2:] - pos[:, :-2], axis=-1) > 0.01
    jump_v[1:-1, :] = np.linalg.norm(pos[2:, :] - pos[:-2, :], axis=-1) > 0.01
    gu[jump_u] = 0; gv[jump_v] = 0
    k = 1.6
    n = np.stack([-gu * k, -gv * k, np.ones_like(hgt)], axis=-1); n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return np.clip(col, 0, 1), n * 0.5 + 0.5


HOLE_R, HOLE_PITCH = 0.0095, 0.054
HOLE_ROWS = ((0.06, 0.0), (0.94, 0.5), (0.44, 0.0), (0.56, 0.5))   # (angle round the jacket / 1 turn, stagger): two rows each side, +-22 deg


def jacket_texture(res=512):
    """jacket strip: u = around (0..1, 0 = the gun's right), v = along (0..1 = 0 .. 0.665 m); holes = alpha 0 with a dark lip, two staggered
    rows on each side as the WT flex gun shows them (rows ~ +-20 deg off the horizontal, ~20 mm holes at ~55 mm pitch)."""
    W, H = res, res * 2
    nz = noise2(H, 4, 11, W)
    col = np.array([0.034, 0.034, 0.035], np.float32)[None, None, :] * (0.85 + 0.3 * nz[..., None])
    al = np.ones((H, W), np.float32)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    circ = 2 * math.pi * 0.026
    for ang, off in HOLE_ROWS:
        for k in range(14):
            sv = 0.040 + (k + off) * HOLE_PITCH
            if sv > 0.635:
                continue
            for du in (-1, 0, 1):                                 # wrap round u
                cx = (ang + du) * W; cy = H - sv / 0.665 * H
                r = np.sqrt(((xx - cx) * circ / W) ** 2 + ((yy - cy) * 0.665 / H) ** 2)
                al = np.where(r < HOLE_R, 0.0, al)
                lip = (r >= HOLE_R) & (r < HOLE_R * 1.3)
                col = np.where(lip[..., None], col * 0.35, col)
    return np.concatenate([col, al[..., None]], axis=2)


# ---------------------------------------------------------------------------------------------------------------- export
def mesh_json(o, mirror=False):
    """Unity gun frame: (x, y, z)_U = (x, z, y)_Blender (and x -> -x for the mirror); the triangle winding is reversed once for the
    Blender (right-handed) -> Unity (left-handed) change and once more for the mirror."""
    me = o.data; me.calc_loop_triangles()
    uv = me.uv_layers.active.data
    V, N, UV, T = [], [], [], {0: [], 1: []}
    for tri in me.loop_triangles:
        sub = 1 if tri.material_index == 1 else 0
        idx = []
        for li in tri.loops:
            lp = me.loops[li]; co = me.vertices[lp.vertex_index].co; nr = lp.normal
            x = -co.x if mirror else co.x; nx = -nr.x if mirror else nr.x
            V.append([round(x, 5), round(co.z, 5), round(co.y, 5)]); N.append([round(nx, 5), round(nr.z, 5), round(nr.y, 5)])
            UV.append([round(uv[li].uv[0], 5), round(uv[li].uv[1], 5)]); idx.append(len(V) - 1)
        a, b, c = idx
        flip = not mirror                                    # handedness change alone: reverse; with the mirror: twice = keep
        T[sub] += [a, c, b] if flip else [a, b, c]
    return dict(v=V, n=N, uv=UV, t=T[0], t_jacket=T[1])


def main():
    objs = {'flex_L': body('flex_L', True, -1), 'turret_L': body('turret_L', False, -1), 'grips': grips(), 'grips_twin': grips_twin()}
    for o in objs.values():
        finish(o)
        uv_layout(o)
    res = RES
    for name in ('flex_L', 'turret_L', 'grips', 'grips_twin'):
        o = objs[name]
        matid_attr(o)
        o['_ids'] = [p.material_index for p in o.data.polygons]
    # one shared texture: bake the three objects into ONE atlas would need packing; instead each object gets its own region of a 2x2
    # atlas: flex 0, turret 1, grips 2 (u / v scaled into the quadrant after the smart projection)
    quads = {'flex_L': (0.0, 0.5), 'turret_L': (0.5, 0.5), 'grips': (0.0, 0.0), 'grips_twin': (0.5, 0.0)}
    full = np.zeros((res, res, 3), np.float32); fulln = np.tile(np.array([0.5, 0.5, 1.0], np.float32), (res, res, 1))
    for name, (u0, v0) in quads.items():
        o = objs[name]
        ids = o['_ids']
        uvd = o.data.uv_layers.active.data
        keep = {}
        for poly in o.data.polygons:
            if ids[poly.index] == 1:
                for li in poly.loop_indices:
                    keep[li] = tuple(uvd[li].uv)
                    uvd[li].uv = (0.97, 0.03)                    # out of the way during the bake (unused corner of quadrant 3)
        for poly in o.data.polygons:
            if ids[poly.index] != 1:
                for li in poly.loop_indices:
                    uvd[li].uv = (u0 + uvd[li].uv[0] * 0.5, v0 + uvd[li].uv[1] * 0.5)
        half = res // 2
        ao = bake(o, 'ao', res); edge = bake(o, 'edge', res); pos = bake(o, 'pos', res); mid = bake(o, 'mat', res)
        if '--debug' in argv:
            for k_, a_ in (('ao', ao), ('edge', edge), ('pos', pos), ('mat', mid)):
                save_png(np.clip(np.flipud(a_), 0, 1), os.path.join(OUT, f'dbg_{name}_{k_}.png'))
        col, nrm = compose(ao, edge, pos, mid, res)
        r0, c0 = int(v0 * res), int(u0 * res)
        full[r0:r0 + half, c0:c0 + half] = col[r0:r0 + half, c0:c0 + half]
        fulln[r0:r0 + half, c0:c0 + half] = nrm[r0:r0 + half, c0:c0 + half]
        for li, u in keep.items():
            uvd[li].uv = u
        for poly in o.data.polygons:                          # restore the material indices for the export
            poly.material_index = ids[poly.index]
    save_png(np.flipud(full), os.path.join(OUT, 'anm2_b.png'), srgb=True)
    save_png(np.flipud(fulln), os.path.join(OUT, 'anm2_n.png'))
    save_png(jacket_texture(), os.path.join(OUT, 'anm2_jacket.png'), srgb=True)
    data = dict(spec=dict(tip_z=TIP, rear_z=S_REAR - 0.016, grip_z=S_REAR - 0.016 - 0.078, frame='Unity gun frame: +X right, +Y up, +Z fire; origin on the bore at the trunnion',
                          feed_side=dict(flex_L='left (-X), lever right', flex_R='right (+X), lever left', turret_L='left (-X)', turret_R='right (+X)'),
                          tex='anm2_b.png', normal_tex='anm2_n.png', jacket_tex='anm2_jacket.png', submeshes='t = steel / wood / dark (anm2_b), t_jacket = perforated jacket (anm2_jacket, alpha cut-out)'))
    data['flex_L'] = mesh_json(objs['flex_L']); data['flex_R'] = mesh_json(objs['flex_L'], mirror=True)
    data['turret_L'] = mesh_json(objs['turret_L']); data['turret_R'] = mesh_json(objs['turret_L'], mirror=True)
    data['grips'] = mesh_json(objs['grips'])
    data['grips_twin'] = mesh_json(objs['grips_twin'])
    data['spec']['overall'] = round(TIP - data['spec']['grip_z'], 4)
    data['spec']['tris'] = {k: (len(data[k]['t']) + len(data[k]['t_jacket'])) // 3 for k in ('flex_L', 'flex_R', 'turret_L', 'turret_R', 'grips', 'grips_twin')}
    json.dump(data, open(os.path.join(OUT, 'anm2_mesh.json'), 'w'), separators=(',', ':'))
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'anm2.blend'))
    print('ANM2', json.dumps(data['spec']))


main()
