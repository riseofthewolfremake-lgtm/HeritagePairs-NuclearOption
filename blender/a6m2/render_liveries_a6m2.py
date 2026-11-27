"""A6M2 round 5 livery review: every livery of assets/textures_a6m2/a6m2_liveries.json on the model (the paint material gets the livery
texture through the `livery` UV layer), two 3/4 views each (front-left gear down, rear-right) + a contact sheet.

  blender --background assets/model_a6m2/a6m2.blend --python blender/a6m2/render_liveries_a6m2.py -- --out <dir> [--tex assets/textures_a6m2]
"""
import bpy, sys, os, json, math
from mathutils import Vector
argv = sys.argv[sys.argv.index('--') + 1:]
OUT = os.path.abspath(argv[argv.index('--out') + 1])
HERE = os.path.dirname(os.path.abspath(__file__))
TEX = os.path.abspath(argv[argv.index('--tex') + 1]) if '--tex' in argv else os.path.join(HERE, '..', '..', 'assets', 'textures_a6m2')
os.makedirs(OUT, exist_ok=True)
sys.argv = [sys.argv[0], '--', '--out', OUT]
src = os.path.join(HERE, 'render_a6m2.py')
G = {'__name__': 'lib', '__file__': src}
code = open(src, encoding='utf-8').read().split("\nif MODE == 'views':")[0]
exec(compile(code, src, 'exec'), G)
G['setup_render']()
for o in bpy.data.objects:
    if o.name.startswith('store_'):
        o.hide_render = True
pm = bpy.data.materials['paint']
pm.use_nodes = True
nt = pm.node_tree
bsdf = [n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'][0]
img_node = nt.nodes.new('ShaderNodeTexImage')
uvn = nt.nodes.new('ShaderNodeUVMap'); uvn.uv_map = 'livery'
nt.links.new(uvn.outputs['UV'], img_node.inputs['Vector'])
nt.links.new(img_node.outputs['Color'], bsdf.inputs['Base Color'])
table = json.load(open(os.path.join(TEX, 'a6m2_liveries.json')))
shots = [('q34', (1.0, 0.95, 0.45), 'down'), ('rear', (-1.0, -0.95, 0.5), 'down'), ('top', (0.0, 0.0, 1.0), 'down'), ('under', (0.0, 0.0, -1.0), 'down')]
meshes = [o for o in bpy.data.objects if o.type == 'MESH' and not o.hide_render]
for key, e in table.items():
    img_node.image = bpy.data.images.load(os.path.join(TEX, e['texture']), check_existing=True)
    bsdf.inputs['Roughness'].default_value = 1.0 - 0.5 * float(e.get('glossiness', 0))
    for tag, d, gear in shots:
        G['set_gear'](gear)
        cam = G['camera'](tag in ('top', 'under'), 50)
        G['fit'](cam, G['wt_dir'](d), G['world_pts'](meshes), 1.08, G['wt_dir']((1, 0, 0)) if tag in ('top', 'under') else None)
        G['render'](f'{key}_{tag}')
print('[liv] done', len(table))
