"""Nimrod HUD weapon icons (1.4.0, user review 2: the Vickers showed the stock 12.7 mm sprite). Stock format (AssetRipper
weaponIcon_50cal / weaponIcon_bomb_125): 512 x 256 RGBA, opaque black, thin white line drawing of the weapon in side view, muzzle / nose
to the LEFT, the weapon about 0.95 (gun) / 0.57 (bomb) of the width, centred. Drawn from OUR fal models (vickers, cooper_single):
orthographic side render (workbench, studio light), then silhouette + shading-edge lines, thinned to ~2 px.

  blender --background --factory-startup --python blender/nimrod/make_weapon_icons.py -- --out assets/ui
"""
import bpy, sys, os, math
import numpy as np
from mathutils import Vector, Euler

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import nimrod_props as PR

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
OUT = os.path.abspath(argv[argv.index('--out') + 1]) if '--out' in argv else os.path.join(HERE, '..', '..', 'assets', 'ui')
os.makedirs(OUT, exist_ok=True)
TMP = os.path.join(os.environ.get('TEMP', OUT), 'nimrod_icon_tmp')
os.makedirs(TMP, exist_ok=True)


def build(name):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    pts, tris = PR.load(name)                          # tris: ([3 points], [3 uvs])
    vs = [tuple(q) for t in tris for q in t[0]]
    me = bpy.data.meshes.new(name); me.from_pydata(vs, [], [(3 * k, 3 * k + 1, 3 * k + 2) for k in range(len(tris))]); me.update()
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
    for p in me.polygons:
        p.use_smooth = False
    return ob, np.array([tuple(p) for p in pts])


def render_side(ob, P, frac, path, res=(2048, 1024)):
    """camera looking along model -x (side), model -y (muzzle / nose) to the image left, model +z up."""
    sc = bpy.context.scene
    lo, hi = P.min(0), P.max(0)
    c = (lo + hi) / 2
    L = hi[1] - lo[1]
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam)
    cam.data.type = 'ORTHO'; cam.data.ortho_scale = L / frac
    cam.location = Vector((c[0] + 5.0, c[1], c[2]))
    cam.rotation_euler = Euler((math.radians(90), 0, math.radians(90)))          # looks along -x, image right = +y
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
    a = np.array(img.pixels[:]).reshape(h, w, 4)[::-1]          # top row first
    if mirror:
        a = a[:, ::-1]
    al = a[..., 3] > 0.5
    lum = (a[..., 0] + a[..., 1] + a[..., 2]) / 3 * al
    edge = al ^ (np.roll(al, 1, 0) & np.roll(al, -1, 0) & np.roll(al, 1, 1) & np.roll(al, -1, 1))       # silhouette
    gx = np.abs(np.roll(lum, 1, 1) - np.roll(lum, -1, 1)); gy = np.abs(np.roll(lum, 1, 0) - np.roll(lum, -1, 0))
    edge |= (np.maximum(gx, gy) > 0.22) & al                                                          # shading creases
    ink = edge.astype(np.float32)
    # 2048 -> 512: max-pool 4x4 keeps the lines ~1-2 px wide like the stock icons
    ink = ink.reshape(h // 4, 4, w // 4, 4).max(axis=(1, 3))
    ink = np.maximum(ink, 0.55 * np.maximum(np.roll(ink, 1, 1), np.roll(ink, 1, 0)))                  # slight thickening
    rgba = np.zeros((h // 4, w // 4, 4), np.float32)
    rgba[..., 0] = rgba[..., 1] = rgba[..., 2] = np.clip(ink, 0, 1); rgba[..., 3] = 1.0
    out = bpy.data.images.new('icon', w // 4, h // 4, alpha=True)
    out.pixels[:] = rgba[::-1].ravel()
    out.filepath_raw = dst; out.file_format = 'PNG'; out.save()
    print('[icon]', dst, f'{w // 4}x{h // 4}, ink px {int((ink > 0.5).sum())}')


for name, key, frac in (('vickers', 'vickers', 0.93), ('cooper_single', 'cooper', 0.57)):
    ob, P = build(name)
    tmp = os.path.join(TMP, key + '.png')
    render_side(ob, P, frac, tmp)
    # the fal models' muzzle / nose is model -y; the camera puts +y to the right, so -y is already on the left
    lines(tmp, os.path.join(OUT, f'nimrod_icon_{key}.png'), mirror=False)
