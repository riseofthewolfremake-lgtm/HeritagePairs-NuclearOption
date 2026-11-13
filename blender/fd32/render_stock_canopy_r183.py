"""1.8.3 polish (offline B): side / 3-4 renders of stock canopies (FS-12 SmallFighter1, KR-67 Fighter1) for the side-by-side with the FD-32.
Reads the user's own AssetRipper export in memory (tools/unity_mesh_asset.py); nothing is saved or committed. Same Workbench look as
render_r183.py (glass faint, frames by material slot: skin = light, everything else darker).

  blender --background --factory-startup --python blender/fd32/render_stock_canopy_r183.py -- --out <png prefix>
"""
import bpy, sys, os, math
from mathutils import Vector as V
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
from unity_mesh_asset import read_mesh, submesh_tris
A = r"C:\Users\User\nuclearoption-ref\tools\assetripper\NUCLEAROPTIONEXPORTS\ExportedProject\Assets\Mesh"
argv = sys.argv[sys.argv.index('--') + 1:]
OUT = argv[argv.index('--out') + 1]
sc = bpy.context.scene
sc.render.engine = 'BLENDER_WORKBENCH'
sh = sc.display.shading
sh.light = 'STUDIO'; sh.color_type = 'MATERIAL'; sh.show_cavity = True; sh.cavity_type = 'BOTH'; sh.show_backface_culling = False
sh.background_type = 'VIEWPORT'; sh.background_color = (0.62, 0.68, 0.74)
sc.display.render_aa = '8'


def mat(n, c):
    m = bpy.data.materials.get(n) or bpy.data.materials.new(n)
    m.diffuse_color = c
    return m


SKIN, DARK, GLASS = mat('skin', (0.50, 0.53, 0.55, 1)), mat('dark', (0.10, 0.10, 0.11, 1)), mat('glass', (0.45, 0.62, 0.75, 0.38))


def place(name, off, mats):
    m = read_mesh(os.path.join(A, name + '.asset'))
    pos = m['pos']
    verts = [(-p[0] + off[0], p[2] + off[2], p[1] + off[1]) for p in pos]       # Unity (x, y up, z fwd) -> Blender (x, y fwd, z up), mirrored x
    me = bpy.data.meshes.new(name); faces = []; fm = []
    for k in range(len(m['submeshes'])):
        t = submesh_tris(m, k)
        for tri in t:
            faces.append((int(tri[0]), int(tri[2]), int(tri[1]))); fm.append(min(k, len(mats) - 1))
    me.from_pydata(verts, [], faces)
    for mm in mats:
        me.materials.append(mm)
    for p, k in zip(me.polygons, fm):
        p.material_index = k; p.use_smooth = True
    ob = bpy.data.objects.new(name, me); sc.collection.objects.link(ob)
    return ob


def cam(loc, tgt, lens, nm):
    c = bpy.data.cameras.new(nm); c.lens = lens
    o = bpy.data.objects.new(nm, c); sc.collection.objects.link(o)
    o.location = V(loc); o.rotation_euler = (V(tgt) - V(loc)).normalized().to_track_quat('-Z', 'Y').to_euler()
    return o


def shot(path, c, res=(1200, 800)):
    sc.camera = c; sc.render.resolution_x, sc.render.resolution_y = res; sc.render.filepath = path
    bpy.ops.render.render(write_still=True); print('[stock]', path)


SETS = {
    'fs12': ([('smallFighter1_cockpit', (0, 0.051, 4.633), [SKIN, DARK, DARK]), ('smallFighter1_canopyFrame', (0, 0.051, 4.633), [SKIN]),
              ('smallFighter1_canopy', (0, 0.051, 4.633), [GLASS])], (0, 4.4, 0.75)),
    'kr67': ([('fighter1_cockpit', (0, -0.010, 7.180), [SKIN, DARK]), ('fighter1_canopyFrame', (0, 0.624, 7.163), [SKIN, DARK]),
              ('fighter1_canopyglass', (0, 0.624, 7.163), [GLASS, GLASS])], (0, 6.4, 0.75)),
}
for key, (objs, c) in SETS.items():
    made = [place(n, o, m) for n, o, m in objs]
    C = V(c)
    shot(f'{OUT}_{key}_side.png', cam(C + V((-4.6, 0, 0.2)), C, 40, key + 's'))
    shot(f'{OUT}_{key}_front34.png', cam(C + V((-3.3, 2.4, 0.55)), C + V((0, 0.05, 0.05)), 40, key + 'f'))
    shot(f'{OUT}_{key}_rear34.png', cam(C + V((-2.8, -3.6, 1.6)), C + V((0, 0.1, 0)), 40, key + 'r'))
    for o in made:
        o.hide_render = True
