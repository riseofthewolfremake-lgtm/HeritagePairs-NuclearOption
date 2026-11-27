"""A6M2 r8c: the cockpit atlas (coordinator r8c item 3: the cockpit read uniformly lit pale sage; WT is darker and grimier low down).

Stock route (measured 2026-11-19 on the user's install, study/a6m2/r8c/ckmat.py: every stock cockpit material - SFB_cockpit, COIN_cockpit,
smallFighter1_cockpit, trainer_cockpit, ... - is Universal Render Pipeline/Lit with ONE unique-UV 2048 x 1024 set: _BaseMap <name>_b,
_BumpMap _n, _MetallicGlossMap _m, _OcclusionMap _ao, keywords _METALLICSPECGLOSSMAP _NORMALMAP _OCCLUSIONMAP). URP Lit samples every map
on UV0, so our tiling cockpit UVs (UV1 'detail') cannot carry a baked occlusion map. The cockpit-view faces therefore get a third UV set
'ckatlas' (UV2 in Unity): unique, packed islands; the Unity build moves those faces to one material A6M2_ckatlas with UV0 = UV2 and the
four baked maps (blender/a6m2/textures/bake_ck_atlas_a6m2.py). Faces outside the atlas carry ckatlas UV (-1, -1).

The vertex-colour route (stock Shader Graphs/Lit_vertexcolor, which also has an _AO_UV2 slot) was rejected: no stock cockpit uses it, its
metallic / smoothness come from a map (1.8.5 lesson: warm probe reflections on stock-structure faces), and vertex AO on our sparse cockpit
meshes would be blotchy.
"""

RES = (2048, 2048)
OUTSIDE = (-1.0, -1.0)

# materials drawn from the atlas: name -> (tile or None, base colour sRGB, metallic, smoothness). Mirrors A6M2Build.cs TileMats / LitMats
# (tools/stub_tests_a6m2_r8c.py checks the two tables agree).
CK_MATS = {
    'interior':   ('ckgreen', (1.0, 1.0, 1.0), 0.05, 0.30),
    'ck_dark':    ('ckgreen', (0.62, 0.64, 0.62), 0.05, 0.25),
    'ck_panel':   ('ckpanel', (1.0, 1.0, 1.0), 0.10, 0.50),
    'ck_gun':     ('ckgun', (2.35, 2.35, 2.42), 0.75, 0.66),   # r8e (game r8d: breeches read as dark blocks): tile ~0.16 -> gunmetal ~0.38 sRGB, glossier
    'gear':       ('metal_dark', (0.90, 0.92, 0.90), 0.60, 0.45),
    'ck_black':   (None, (0.055, 0.055, 0.058), 0.20, 0.45),
    'ck_leather': (None, (0.13, 0.08, 0.05), 0.0, 0.35),
    'ck_blue':    (None, (0.12, 0.32, 0.62), 0.10, 0.60),
    'ck_wood':    (None, (0.26, 0.13, 0.06), 0.0, 0.50),
    'ck_white':   (None, (0.82, 0.80, 0.74), 0.0, 0.50),
}

# r8d: the cockpit green in the atlas is tinted toward WT's darker blue-grey green (measured on the WT front render: frame ~ (90, 99, 88)
# sRGB vs ours (118, 124, 116)); the Unity tiling materials (faces outside the atlas) keep the tile colour
ATLAS_TINT = (0.76, 0.81, 0.82)

# which faces: every CK_MATS face of the cockpit objects and the cockpit-view canopy, and CK_MATS faces of the fuselage parts inside the
# cockpit box (tub walls, sills, floor). The exterior canopy (hidden in the cockpit view) keeps its tiling materials.
COCKPIT_PREFIXES = ('cockpit_', 'ckcanopy_')
BOX_PREFIXES = ('fus_',)
BOX = dict(y0=-2.10, y1=-0.15, z0=-0.40, z1=1.20, x=0.75)     # built metres


def face_in_atlas(obj_name, mat, centre):
    if mat not in CK_MATS:
        return False
    if obj_name.startswith(COCKPIT_PREFIXES):
        return True
    if obj_name.startswith(BOX_PREFIXES):
        x, y, z = centre
        return BOX['y0'] <= y <= BOX['y1'] and BOX['z0'] <= z <= BOX['z1'] and abs(x) <= BOX['x']
    return False
