"""3-blade propeller blur texture for the B-25H in the CI-22 (COIN_propblur_b) layout, 512 x 1024 RGBA:
top half = motion-blurred blades (mesh propdisc_blur, uv v 0.5-1), bottom half = translucent full disc
(mesh propdisc_full, uv v 0-0.5). Both discs: centre u 0.5 / v 0.75 or 0.25, radius 1.93 m -> 248 px, hub hole
0.17 m (assets/model_v2/b25h_v2_propdisc.fbx, model contract "Prop discs"). Black Hamilton Standard blades
with yellow tips. Also writes b25h_propblur.json (material settings copied from the stock COIN_propdisc1).

  blender --background --factory-startup --python blender/v2/textures/make_propblur.py -- [--out <dir>]
"""
import bpy, sys, os, math, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tex_lib as T

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
out = os.path.abspath(argv[argv.index('--out') + 1]) if '--out' in argv else T.OUT
F32 = np.float32
W, H = 512, 1024
R_PX = 0.485 * W                      # disc radius in px (uv 0.015..0.985)
HUB = 0.17 / 1.93                     # hub radius / disc radius
TIP = 1.0 - 0.16 / 1.93               # yellow tip band: outer ~6 in (0.16 m)
BLADE = np.array([0.075, 0.075, 0.07], F32)
YELLOW = np.array([0.85, 0.68, 0.12], F32)
SS = 2


def half(v_centre, kind):
    """RGBA of one half (rows bottom-up like Blender), supersampled."""
    h = H // 2
    ys, xs = np.mgrid[0:h * SS, 0:W * SS].astype(F32)
    px = ((xs + 0.5) / SS - W / 2) / R_PX
    py = ((ys + 0.5) / SS - (v_centre * H - (0 if v_centre < 0.5 else h))) / R_PX
    r = np.sqrt(px * px + py * py)
    th = np.degrees(np.arctan2(py, px))
    inside = T.smoothstep(1.0, 0.985, r) * T.smoothstep(HUB - 0.005, HUB + 0.01, r)
    tipw = T.smoothstep(TIP - 0.01, TIP + 0.01, r)
    col = BLADE * (1 - tipw[..., None]) + YELLOW * tipw[..., None]
    if kind == 'blur':
        a = np.zeros_like(r)
        for k in range(3):
            d = (th - 90 - 120 * k + 180) % 360 - 180          # signed angle from the blade axis
            # chord in degrees shrinks outward (constant ~0.3 m chord); blur trails on the -d side
            chord = np.degrees(0.30 / 1.93 / np.maximum(r, 0.1)) * 0.5
            core = np.exp(-0.5 * (d / (chord + 2.0)) ** 2)
            trail = np.exp(-np.maximum(-d, 0) / 14.0) * (d < 0) * 0.35
            a = np.maximum(a, np.maximum(core * 0.9, trail))
        a *= (0.55 + 0.45 * T.smoothstep(0.1, 0.35, r))            # blades thicker toward the root
        alpha = a * inside
    else:
        n = T.vnoise(np.stack([px.ravel() * 30, py.ravel() * 30, np.zeros(px.size, F32)], 1).astype(F32), 1.0, seed=5)
        n = n.reshape(r.shape)
        alpha = (0.42 - 0.2 * r + 0.04 * (n - 0.5)) * inside
        alpha = np.maximum(alpha, 0.38 * tipw * inside)              # faint yellow tip ring
    rgba = np.dstack([col, alpha])
    return rgba.reshape(h, SS, W, SS, 4).mean(axis=(1, 3))


img = np.zeros((H, W, 4), F32)
img[:H // 2] = half(0.25, 'full')        # rows bottom-up: v 0-0.5 = disc
img[H // 2:] = half(0.75, 'blur')        # v 0.5-1 = blurred blades
# premultiplied-looking edges: keep colour where alpha is zero (avoids dark fringes under bilinear filtering)
T.save_png(img[..., :3], os.path.join(out, 'b25h_propblur.png'), alpha=img[..., 3])
meta = {
    'texture': 'b25h_propblur.png',
    'layout': 'CI-22 COIN_propblur_b: v 0.5-1 = blurred blades (propdisc_blur), v 0-0.5 = translucent disc (propdisc_full); '
              'disc centre u 0.5, radius 0.485 uv (1.93 m), hub hole 0.17 m',
    'import': {'sRGB': True, 'alphaIsTransparency': True, 'wrap': 'Clamp', 'filter': 'Bilinear', 'mipmaps': True},
    'material': {
        'note': 'copy the stock COIN_propdisc1 material (URP Lit, transparent) and swap _BaseMap/_MainTex; values as stock',
        'shader': 'Universal Render Pipeline/Lit', 'renderQueue': 3000, 'RenderType': 'Transparent',
        '_Surface': 1, '_Blend': 0, '_SrcBlend': 5, '_DstBlend': 10, '_SrcBlendAlpha': 1, '_DstBlendAlpha': 10,
        '_ZWrite': 0, '_Cull': 2, '_AlphaClip': 0, '_Metallic': 0, '_Smoothness': 0.63, '_SpecularHighlights': 1,
        '_BaseColor': [1, 1, 1, 0.102], 'disabledShaderPasses': ['SHADOWCASTER', 'DepthOnly'],
        '_OcclusionMap': 'none (stock uses COIN_propblur_ao; not needed)',
    },
}
with open(os.path.join(out, 'b25h_propblur.json'), 'w') as f:
    json.dump(meta, f, indent=1)
print('[propblur] done')
