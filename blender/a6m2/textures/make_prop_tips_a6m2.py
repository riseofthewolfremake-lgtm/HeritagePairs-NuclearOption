"""A6M2 r7: 1-D prop blade texture (plain Python: PIL). u = radius / tip radius (build_a6m2.prop_tip_uvs), v unused.

  python blender/a6m2/textures/make_prop_tips_a6m2.py [--out assets/textures_a6m2]

White (the prop material colour multiplies it) with two red warning stripes near the tip, as on the War Thunder A6M2 reference renders
(the reference shows red, not yellow). One texture for every livery: the blade has ONE material (memory prop-blade-one-renderer).
"""
import os, sys
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
argv = sys.argv[1:]
OUT = os.path.abspath(argv[argv.index('--out') + 1]) if '--out' in argv else os.path.join(HERE, '..', '..', '..', 'assets', 'textures_a6m2')
W, H = 512, 8
STRIPES = [(0.865, 0.900), (0.920, 0.955)]       # u ranges of the two stripes (tip at u 1.0); r7b: 5 cm each (r7 3.7 cm)
RED = (196, 28, 22)
# r7b (game: stripes not visible on a stopped prop): the blade material is metallic 0.8 - a metallic surface shows its albedo only in its
# reflections, so the red barely read (Inference). The stripes now get their own metallic / smoothness through a URP metallic map:
# a6m2_prop_tips_m.png, R = metallic (0.8 metal, 0 paint), A = smoothness (0.65 metal, 0.35 paint); linear import (name ends in _m).
img = Image.new('RGB', (W, H), (255, 255, 255))
met = Image.new('RGBA', (W, H), (204, 204, 204, 115))     # r8b: smoothness 0.45 (0.65 read chalk-white in the cockpit view)
# r8d (coordinator: the blades read white from the cockpit; stock props are dark): the rear face (v < 0.5, the half of the texture the
# cockpit sees: build_a6m2.prop_tip_uvs puts the aft-facing faces at v 0.25) is the A6M2's dark brown anti-glare finish, matte; the front
# stays natural metal. PIL row 0 is v = 1 (top): rows H/2..H-1 are v < 0.5.
REAR = (58, 44, 34)
for x in range(W):
    u = (x + 0.5) / W
    stripe = any(a <= u < b for a, b in STRIPES)
    for y in range(H):
        rear = y >= H // 2
        if stripe:
            img.putpixel((x, y), RED)
            met.putpixel((x, y), (0, 0, 0, 89))
        elif rear:
            img.putpixel((x, y), REAR)
            met.putpixel((x, y), (0, 0, 0, 64))
os.makedirs(OUT, exist_ok=True)
p = os.path.join(OUT, 'a6m2_prop_tips.png')
img.save(p)
pm = os.path.join(OUT, 'a6m2_prop_tips_m.png')
met.save(pm)
print('[a6prop]', p, pm, img.size)
