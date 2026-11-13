"""Stock-part preview for offline renders and checks (GA-25X 0.3.1 cockpit kitbash).

The 0.3.1 cockpit KITBASHES stock parts (same pattern as the community mods OA-27 / F-99 / MC-260): the stock SFB-81 ejection
seat, flight stick and throttle are NOT in our FBX. GA25XBuild.cs references them in Unity through the Blueprinter project's
placeholder assets (resolved to the game's own assets at runtime). For offline renders / clearance checks this module reads
the same placeholder meshes from the USER'S Blueprinter project at run time (tools/unity_mesh_asset.py) and drops them into
the open Blender scene. Nothing is copied into the repo; preview objects are never saved or exported.

Placement rules (Unity frame, x right, y up, z fwd; measured from the stock prefabs with tools in the session scratchpad):
  * crew figure root = eye - FIG_EYE_TO_ROOT (COIN pilot/WSO figure: helmetCamPoint at (0, 0.7147, -0.0651) in the figure);
  * EjectionSeat child at SEAT_IN_FIG (COIN and SFB-81: (0, 0.0218, -0.041), mesh ejectionSeat, material Seats);
  * SFB-81 joystick_L/R: Pilot root + (-/+0.042, -0.3926, 0.4555) (Darkreach.prefab cockpit/cockpit_int/joystick_*);
  * SFB-81 throttle: Pilot root + (0.494, -0.1705, 0.4579) = centred between the seats.
"""
import os, sys, math
import bpy
from mathutils import Vector, Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
PH = os.environ.get('NO_PLACEHOLDERS', r'C:\Users\User\nuclearoption-ref\BlueprinterProject\Blueprinter-Editor\Assets\Blueprinter\_donotship')

FIG_EYE_TO_ROOT = (0.0, -0.7147, 0.0651)     # Unity: figure root = eye + this
SEAT_IN_FIG = (0.0, 0.0218, -0.041)

# stock material previews: placeholder base-colour texture or flat colour (sRGB-ish linear values)
MATS = {'Seats': 'seats_b', 'hotas': 'hotas_b', 'SFB_cockpit': 'sfb_cockpit_b', 'Matte_black': (0.01, 0.01, 0.01),
        'aircraft_structure': 'aircraft_structure_b'}
STOCK = {'ejectionSeat': ['Seats'], 'sfb_joystick': ['hotas', 'SFB_cockpit'], 'sfb_throttle': ['SFB_cockpit']}


def available():
    return os.path.isdir(os.path.join(PH, 'Mesh'))


def u2b(v):
    """Unity vector (x, y up, z fwd) -> Blender (x, y fwd, z up) (a mirror: triangle winding is reversed below)."""
    return Vector((v[0], v[2], v[1]))


def b2u(v):
    return (v[0], v[2], v[1])


def _material(name):
    mn = 'stock_' + name
    if mn in bpy.data.materials:
        return bpy.data.materials[mn]
    m = bpy.data.materials.new(mn)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get('Principled BSDF')
    src = MATS.get(name, (0.2, 0.2, 0.2))
    if isinstance(src, str):
        p = os.path.join(PH, 'Texture2D', src + '_PLACEHOLDER.png')
        if os.path.exists(p):
            tx = m.node_tree.nodes.new('ShaderNodeTexImage')
            tx.image = bpy.data.images.load(p, check_existing=True)
            m.node_tree.links.new(tx.outputs['Color'], bsdf.inputs['Base Color'])
    else:
        bsdf.inputs['Base Color'].default_value = (*src, 1.0)
    bsdf.inputs['Roughness'].default_value = 0.6
    return m


def add_stock(mesh_name, at_blender, name, mats=None, vcol=None):
    """object from the placeholder mesh, origin at at_blender (Blender world), Unity-identity orientation."""
    from unity_mesh_asset import read_mesh, submesh_tris
    m = read_mesh(os.path.join(PH, 'Mesh', mesh_name + '_PLACEHOLDER.asset'))
    me = bpy.data.meshes.new(name)
    verts = [u2b(p) for p in m['pos']]
    faces, fmat = [], []
    for k in range(len(m['submeshes'])):
        for t in submesh_tris(m, k):
            faces.append((int(t[0]), int(t[2]), int(t[1])))      # mirror -> reverse winding
            fmat.append(k)
    me.from_pydata(verts, [], faces)
    if m['uv'] is not None:
        uvl = me.uv_layers.new(name='uv0')
        for poly in me.polygons:
            for li in poly.loop_indices:
                vi = me.loops[li].vertex_index
                uvl.data[li].uv = (m['uv'][vi][0], m['uv'][vi][1])
    for mn in (mats or STOCK.get(mesh_name, [])):
        me.materials.append(_material(mn))
    for poly, k in zip(me.polygons, fmat):
        poly.material_index = min(k, max(len(me.materials) - 1, 0))
    me.update()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = Vector(at_blender)
    ob['stock_preview'] = mesh_name
    return ob


def seat_origin_blender(eye_blender):
    e = Vector(eye_blender)
    r = e + u2b(FIG_EYE_TO_ROOT)
    return r + u2b(SEAT_IN_FIG)


def add_cockpit_preview():
    """stock seats at both crew figures + stock sticks / throttle at the stick_L/R, cockpit_throttle empties."""
    O = bpy.data.objects
    out = []
    for L, eye in (('L', 'cockpit_eye'), ('R', 'crew_wso_eye')):
        if eye in O:
            out.append(add_stock('ejectionSeat', seat_origin_blender(O[eye].matrix_world.translation), f'preview_seat_{L}'))
        if f'stick_{L}' in O:
            out.append(add_stock('sfb_joystick', O[f'stick_{L}'].matrix_world.translation, f'preview_stick_{L}'))
    if 'cockpit_throttle' in O and 'stock_mesh' in (O['cockpit_throttle'].get('b25_info') or ''):   # 0.3.3: no stock throttle
        out.append(add_stock('sfb_throttle', O['cockpit_throttle'].matrix_world.translation, 'preview_throttle'))
    bpy.context.view_layer.update()
    return out
