"""1.9.9: rename the key MSB1780 -> MSB17 inside the saved .blend without rebuilding the model (no geometry, UV or material change).

  blender --background assets/model_msb1780/msb1780.blend --python-exit-code 1 --python blender/msb1780/rename_key199.py

Renames every datablock whose name is OLD or starts with OLD + '_' (objects: the centre fuselage, the root and extras empties; their mesh
data; collections), and custom properties that hold OLD (a string, or a part name inside an info group / JSON text). Saves the .blend in place. A full rebuild
(build_msb1780.py with msb_spec.KEY = 'MSB17') gives the same names; this script only spares the rebuild + texture re-bake.
Prints the per-object geometry fingerprint count before / after so the caller can see nothing else moved.
"""
import bpy, hashlib, struct
OLD, NEW = 'MSB1780', 'MSB17'


def fp():
    out = {}
    for o in bpy.data.objects:
        if o.type != 'MESH':
            continue
        h = hashlib.sha256()
        for v in o.data.vertices:
            h.update(struct.pack('<3f', *v.co))
        for p in o.data.polygons:
            h.update(struct.pack(f'<{len(p.vertices)}i', *p.vertices))
        out[o.name.replace(OLD, NEW)] = h.hexdigest()
    return out


a = fp()
n = 0
for coll in (bpy.data.objects, bpy.data.meshes, bpy.data.collections, bpy.data.materials, bpy.data.images):
    for d in coll:
        if d.name == OLD or d.name.startswith(OLD + '_') or d.name.startswith(OLD + '.'):
            print('rename', coll.rna_type.identifier if hasattr(coll, 'rna_type') else '', d.name, '->', NEW + d.name[len(OLD):])
            d.name = NEW + d.name[len(OLD):]; n += 1
def fix(v):
    """custom property value with the key renamed (strings: exact value or a quoted JSON token; groups and lists: recursively)"""
    if isinstance(v, str):
        return NEW if v == OLD else v.replace('"' + OLD + '"', '"' + NEW + '"').replace("'" + OLD + "'", "'" + NEW + "'")
    if hasattr(v, 'to_dict'):
        v = v.to_dict()
    if isinstance(v, dict):
        return {k: fix(x) for k, x in v.items()}
    if hasattr(v, 'to_list'):
        v = v.to_list()
    if isinstance(v, (list, tuple)):
        return [fix(x) for x in v]
    return v


def plain(v):
    if hasattr(v, 'to_dict'):
        return plain(v.to_dict())
    if hasattr(v, 'to_list'):
        return plain(v.to_list())
    if isinstance(v, dict):
        return {k: plain(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [plain(x) for x in v]
    return v


for o in bpy.data.objects:
    for k in list(o.keys()):
        if k.startswith('_'):
            continue
        old_v = plain(o[k]); new_v = fix(o[k])
        if new_v != old_v:
            o[k] = new_v; n += 1; print('prop', o.name, k)
b = fp()
assert a == b, 'geometry changed'
left = [d.name for coll in (bpy.data.objects, bpy.data.meshes, bpy.data.collections) for d in coll if '1780' in d.name]
left += [o.name + '.' + k for o in bpy.data.objects for k in o.keys() if not k.startswith('_') and OLD in repr(plain(o[k]))]
print(f'RENAME199 {n} renamed, {len(a)} mesh objects, geometry fingerprints identical, names with 1780 left: {left}')
assert not left     # n may be 0 on a second run
bpy.ops.wm.save_mainfile()
