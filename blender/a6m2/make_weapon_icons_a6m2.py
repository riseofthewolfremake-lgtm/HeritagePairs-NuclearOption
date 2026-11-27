"""A6M2 HUD weapon icons (round 2): own 512 x 256 white-on-black line drawings, stock format (weaponIcon_50cal / weaponIcon_bomb_125:
opaque black, thin white lines, muzzle / nose to the LEFT, a gun ~0.93 of the width, a bomb ~0.57), drawn from OUR models:
  type97  Type 97 7.7 mm MG: slim barrel in a perforated jacket, Vickers-pattern receiver WITHOUT the Vickers water-jacket cup (distinct icon)
  type99  Type 99-1 20 mm: long thin barrel, recoil spring housing, 60-round drum on the receiver
  no6     Type 97 No.6 60 kg bomb (the store model, blender/a6m2/a6m2_parts.build_stores)
  tokko   250 kg special-attack charge (the store model)
Method = blender/nimrod/make_weapon_icons.py (orthographic side render, silhouette + shading creases, 4x max-pool).

  blender --background --factory-startup --python blender/a6m2/make_weapon_icons_a6m2.py -- --out assets/ui
"""
import bpy, sys, os, math
import numpy as np
from mathutils import Vector, Euler

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, '..', 'v2')]
from b25h_geom import V, MeshBuf, cylinder, box, tube   # noqa: E402
import a6m2_parts as AP                                  # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
OUT = os.path.abspath(argv[argv.index('--out') + 1]) if '--out' in argv else os.path.join(HERE, '..', '..', 'assets', 'ui')
os.makedirs(OUT, exist_ok=True)
TMP = os.path.join(os.environ.get('TEMP', OUT), 'a6m2_icon_tmp')
os.makedirs(TMP, exist_ok=True)


def gun97():
    mb = MeshBuf()
    cylinder(mb, V((0, 0.0, 0)), V((0, 0.62, 0)), 0.011, N=16)                       # barrel (muzzle +y)
    cylinder(mb, V((0, 0.10, 0)), V((0, 0.50, 0)), 0.024, N=16)                      # perforated jacket
    for k in range(9):
        y = 0.13 + 0.04 * k
        cylinder(mb, V((0, y, 0)), V((0, y + 0.012, 0)), 0.029, N=16)                # jacket ribs between the cooling holes (side-view lines)
    tube(mb, V((0, 0.60, 0)), V((0, 0.64, 0)), 0.015, 0.008, N=16)                   # flash hider ring
    box(mb, (0, -0.18, 0.0), (0.06, 0.36, 0.11), 'metal_dark')                      # receiver
    box(mb, (0, -0.16, 0.075), (0.03, 0.22, 0.03), 'metal_dark')                    # top cover / feed
    box(mb, (0, -0.10, -0.07), (0.05, 0.10, 0.04), 'metal_dark')                    # belt feed block
    cylinder(mb, V((0, -0.37, 0.0)), V((0, -0.42, 0.0)), 0.02, N=12)                 # back plate knob
    return mb


def gun99():
    mb = MeshBuf()
    cylinder(mb, V((0, 0.0, 0)), V((0, 1.10, 0)), 0.014, 0.012, N=16)                # long barrel
    cylinder(mb, V((0, 0.0, 0)), V((0, 0.34, 0)), 0.030, N=16)                       # recoil spring housing
    tube(mb, V((0, 1.06, 0)), V((0, 1.12, 0)), 0.019, 0.010, N=16)                   # muzzle
    box(mb, (0, -0.22, 0.0), (0.08, 0.44, 0.12), 'metal_dark')                      # receiver
    cylinder(mb, V((-0.04, -0.20, 0.17)), V((0.04, -0.20, 0.17)), 0.11, N=40)        # 60-round drum on the receiver (side view: a disc)
    cylinder(mb, V((0.04, -0.20, 0.17)), V((0.06, -0.20, 0.17)), 0.035, N=20)        # drum hub
    cylinder(mb, V((0, -0.46, 0.0)), V((0, -0.52, 0.0)), 0.03, N=12)                 # buffer
    return mb


def store(name):
    parts = {p.name: p for p in AP.build_stores()}
    mb = MeshBuf()
    p = parts[name + '_bomb']
    for f in p.mesh.faces:
        mb.face([mb.v(p.mesh.verts[i]) for i in f['idx']], f['mat'])
    vs = [V(v) for v in p.mesh.verts]
    ny = max(v.y for v in vs); c = sum(vs, V()) / len(vs); R = max(abs(v.z - c.z) for v in vs if abs(v.y - c.y) < 0.1)
    bands = (0.20,) if 'no6' in name else (0.30, 0.42)                  # icon lines for the nose bands (one on the 60 kg, two on the charge)
    for d in bands:
        cylinder(mb, V((c.x, ny - d, c.z)), V((c.x, ny - d - 0.03, c.z)), R * 1.04, N=32)
    if 'tokko' in name:                                                 # nose impact fuze
        cylinder(mb, V((c.x, ny - 0.01, c.z)), V((c.x, ny + 0.06, c.z)), 0.022, 0.016, N=16)
    return mb


def to_object(name, mb):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in mb.verts], [], [tuple(f['idx']) for f in mb.faces]); me.update()
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
    for p in me.polygons:
        p.use_smooth = False
    return ob, np.array([tuple(v) for v in mb.verts])


def render_side(P, frac, path, res=(2048, 1024)):
    """camera looking along -x: model +y (muzzle / nose) on the image RIGHT; lines() mirrors it to the left."""
    sc = bpy.context.scene
    lo, hi = P.min(0), P.max(0)
    c = (lo + hi) / 2
    L = hi[1] - lo[1]
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam)
    cam.data.type = 'ORTHO'; cam.data.ortho_scale = L / frac
    cam.location = Vector((c[0] + 5.0, c[1], c[2]))
    cam.rotation_euler = Euler((math.radians(90), 0, math.radians(90)))
    sc.camera = cam
    sc.render.engine = 'BLENDER_WORKBENCH'
    sh = sc.display.shading
    sh.light = 'STUDIO'; sh.color_type = 'SINGLE'; sh.single_color = (0.8, 0.8, 0.8); sh.show_cavity = True; sh.cavity_type = 'BOTH'
    sh.show_object_outline = False
    sc.render.film_transparent = True
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


def lines(src, dst, mirror):
    img = bpy.data.images.load(src)
    w, h = img.size
    a = np.array(img.pixels[:]).reshape(h, w, 4)[::-1]
    if mirror:
        a = a[:, ::-1]
    al = a[..., 3] > 0.5
    lum = (a[..., 0] + a[..., 1] + a[..., 2]) / 3 * al
    edge = al ^ (np.roll(al, 1, 0) & np.roll(al, -1, 0) & np.roll(al, 1, 1) & np.roll(al, -1, 1))
    gx = np.abs(np.roll(lum, 1, 1) - np.roll(lum, -1, 1)); gy = np.abs(np.roll(lum, 1, 0) - np.roll(lum, -1, 0))
    edge |= (np.maximum(gx, gy) > 0.22) & al
    ink = edge.astype(np.float32)
    ink = ink.reshape(h // 4, 4, w // 4, 4).max(axis=(1, 3))
    ink = np.maximum(ink, 0.55 * np.maximum(np.roll(ink, 1, 1), np.roll(ink, 1, 0)))
    rgba = np.zeros((h // 4, w // 4, 4), np.float32)
    rgba[..., 0] = rgba[..., 1] = rgba[..., 2] = np.clip(ink, 0, 1); rgba[..., 3] = 1.0
    out = bpy.data.images.new('icon', w // 4, h // 4, alpha=True)
    out.pixels[:] = rgba[::-1].ravel()
    out.filepath_raw = dst; out.file_format = 'PNG'; out.save()
    print('[icon]', dst, f'{w // 4}x{h // 4}, ink px {int((ink > 0.5).sum())}')


for key, make, frac in (('type97', gun97, 0.93), ('type99', gun99, 0.93), ('no6', lambda: store('store_no6'), 0.57), ('tokko', lambda: store('store_tokko'), 0.62)):
    ob, P = to_object(key, make())
    tmp = os.path.join(TMP, key + '.png')
    render_side(P, frac, tmp)
    lines(tmp, os.path.join(OUT, f'a6m2_icon_{key}.png'), mirror=True)     # +y (muzzle / nose) was on the right
