"""side_by_side_nimrod_cockpit_v2.jpg: the user's reference photos (top: 50 real panel, 51 / 53 / 55 game views of another Nimrod
cockpit, layout references only) over our cockpit v2 renders. Contains the user's photos: git-ignored (media/**/side_by_side*).
  python blender/nimrod/compose_side_by_side_nimrod.py [media dir, default media/nimrod_v2]"""
import os, sys
from PIL import Image, ImageDraw
REF = r"C:\Users\User\nuclearoption-ref\refs\nimrod_cockpit_user"
M = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'media', 'nimrod_v2')
W, H = 640, 382
rows = [[(REF, '50.png', 'user ref 50: real Nimrod/Hart panel'), (REF, '51.png', 'user ref 51'), (REF, '53.png', 'user ref 53'), (REF, '55.png', 'user ref 55')],
        [(M, 'cockpit_panel_close.png', 'v2: panel close-up'), (M, 'cockpit_pilot_eye.png', 'v2: pilot eye (90 deg FOV)'),
         (M, 'cockpit_left_wall.png', 'v2: left wall (quadrant, trim wheel)'), (M, 'cockpit_right_wall.png', 'v2: right wall (ammo box, pump, cocks)')],
        [(M, 'cockpit_floor.png', 'v2: floor (footboards, rudder bar, seat)'), (M, 'cockpit_above.png', 'v2: from above (cf. ref 51)')]]
out = Image.new('RGB', (W * 4, H * len(rows)), (20, 20, 20))
for r, items in enumerate(rows):
    for c, (d, f, label) in enumerate(items):
        p = os.path.join(d, f)
        if not os.path.exists(p):
            continue
        im = Image.open(p).convert('RGB')
        im.thumbnail((W - 4, H - 22))
        out.paste(im, (c * W + (W - im.width) // 2, r * H + 22))
        ImageDraw.Draw(out).text((c * W + 8, r * H + 5), label, fill=(240, 240, 240))
dst = os.path.join(M, 'side_by_side_nimrod_cockpit_v2.jpg')
out.save(dst, quality=88)
print('[compose]', dst)
