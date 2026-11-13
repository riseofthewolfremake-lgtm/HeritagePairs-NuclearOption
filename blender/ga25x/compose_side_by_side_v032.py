"""Side-by-side cockpit comparison (0.3.2): our pilot / WSO eye renders next to the user's reference screenshots.

  python blender/ga25x/compose_side_by_side_v032.py <our_dir> <ref_dir> <out.jpg>

The reference screenshots are the user's local captures of OTHER mods (MC-260, F-204): the output image contains them and
must stay local (media/ga25x_v032_cockpit/.gitignore excludes side_by_side*), never committed or shared.
"""
import sys, os
from PIL import Image, ImageDraw

ours, refs, out = sys.argv[1], sys.argv[2], sys.argv[3]
W, H = 1000, 500
tiles = [(os.path.join(refs, 'user_34.jpg'), 'REFERENCE  MC-260 Chimera (user_34)'),
         (os.path.join(ours, 'pilot_eye.png'), 'OURS  GA-25X 0.3.2 pilot eye (Blender, stock parts previewed, screens = stand-in)'),
         (os.path.join(refs, 'user_31.jpg'), 'REFERENCE  user_31 (F-204 per the brief)'),
         (os.path.join(ours, 'wso_eye.png'), 'OURS  GA-25X 0.3.2 WSO eye (Blender)')]
img = Image.new('RGB', (2 * W, 2 * (H + 28)), (20, 20, 20))
d = ImageDraw.Draw(img)
for k, (p, lab) in enumerate(tiles):
    im = Image.open(p).convert('RGB')
    # crop to 2:1 around the centre (references are 2000x837 game captures; ours 1600x900)
    w, h = im.size
    th = int(w / 2)
    if th <= h:
        y0 = (h - th) // 2
        im = im.crop((0, y0, w, y0 + th))
    im = im.resize((W, H))
    x, y = (k % 2) * W, (k // 2) * (H + 28)
    img.paste(im, (x, y + 28))
    d.text((x + 8, y + 8), lab, fill=(255, 255, 255))
img.save(out, quality=90)
print('wrote', out)
