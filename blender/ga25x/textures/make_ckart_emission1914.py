"""1.9.14 (user suggestion: lit cockpit buttons should glow): emission map for the GA-25X panel-art atlas.

  python blender/ga25x/textures/make_ckart_emission1914.py [<atlas _b.png> <out _e.png>]

Lit = painted lamps only: inside the annunciator strip (ga25x_ckart_layout 'annunciator' rect) the saturated bright cells
(MASTER CAUTION amber, GEAR green); anywhere in the atlas the bright green LED digits (CMDS 0120, ALT 29.92, radio
frequencies). The yellow / red placards and hazard stripes are NOT lit. Output = the base colour where lit, black elsewhere
(URP Lit _EmissionMap x _EmissionColor). Prints the lit fraction and the bounding box of each lit region group.
"""
import os, sys
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import ga25x_ckart_layout as LY

ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
src = sys.argv[1] if len(sys.argv) > 2 else os.path.join(ROOT, 'assets', 'textures_ga25x', 'ga25x_ckart_b.png')
dst = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, 'assets', 'textures_ga25x', 'ga25x_ckart_e.png')
im = Image.open(src).convert('RGB')
a = np.asarray(im).astype(np.float32) / 255.0
mx, mn = a.max(2), a.min(2)
sat = (mx - mn) / np.maximum(mx, 1e-3)
lamp = (sat > 0.45) & (mx > 0.55)
x0, y0, x1, y1 = LY.PANELS['annunciator'][0]
s = im.size[0] / LY.ATLAS
ann = np.zeros_like(lamp)
ann[int(y0 * s):int(y1 * s), int(x0 * s):int(x1 * s)] = True
r, g, b = a[..., 0], a[..., 1], a[..., 2]
led = (g > 0.45) & (g > r * 1.35) & (g > b * 1.2) & (sat > 0.35)
lit = (lamp & ann) | led
# soften by one pixel so the glow edge follows the art's anti-aliasing
from PIL import ImageFilter
m = Image.fromarray((lit * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(1.0))
mf = np.asarray(m).astype(np.float32)[..., None] / 255.0
out = (a * mf * 255.0).clip(0, 255).astype(np.uint8)
Image.fromarray(out).save(dst, optimize=True)
print(f'[emission1914] {dst}: lit {100 * lit.mean():.3f} % (annunciator lamps {100 * (lamp & ann).mean():.3f} %, green LED {100 * led.mean():.3f} %)')
