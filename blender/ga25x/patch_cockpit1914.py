"""1.9.14: put the rebuilt cockpit_interior mesh (annunciator caution-light crops, knobs / toggles on the painted ones) into the
SHIPPED GA-25X blend. A full run_ga25x.py rebuild re-packs the livery atlas (62 parts moved), so only this one mesh is swapped.

  blender --background <shipped ga25x.blend> --python patch_cockpit1914.py -- <fresh build blend> <out blend>

The object, its transform, parent and custom properties stay; only its mesh data is replaced. Materials are mapped back onto
the shipped blend's materials by name (the library load brings copies named 'x.001').
"""
import bpy, sys, json, re

argv = sys.argv[sys.argv.index('--') + 1:]
src_blend, out_blend = argv[0], argv[1]
NAMES = ['cockpit_interior']
shipped = {n: bpy.data.objects[n] for n in NAMES}
shipped_mats = {m.name: m for m in bpy.data.materials}

with bpy.data.libraries.load(src_blend, link=False) as (src, dst):
    dst.objects = [n for n in src.objects if n in NAMES]
rep = {}
for so in dst.objects:
    base = re.sub(r'\.\d{3}$', '', so.name)
    t = shipped[base]
    # the loaded copy is in no scene (its world matrix is not evaluated): compare the local frame and parent inverse
    for a, b in ((so.matrix_basis, t.matrix_basis), (so.matrix_parent_inverse, t.matrix_parent_inverse)):
        if max(abs(a[i][j] - b[i][j]) for i in range(4) for j in range(4)) > 1e-5:
            sys.exit(f'patch: {base} frame differs: {a} vs {b}')
    old = t.data
    me = so.data
    for i, m in enumerate(me.materials):
        if m is None:
            continue
        orig = shipped_mats.get(re.sub(r'\.\d{3}$', '', m.name))
        if orig is None:
            sys.exit(f'patch: material {m.name} has no shipped original')
        me.materials[i] = orig
    t.data = me
    rep[base] = dict(old_verts=len(old.vertices), new_verts=len(me.vertices), mats=[m.name for m in me.materials if m])
    bpy.data.objects.remove(so)
    old_name = old.name
    if old.users == 0:
        bpy.data.meshes.remove(old)
    me.name = old_name
for m in list(bpy.data.materials):
    if m.users == 0 and m.name not in shipped_mats:
        bpy.data.materials.remove(m)
bpy.ops.wm.save_as_mainfile(filepath=out_blend)
print('[patch1914]', json.dumps(rep))
