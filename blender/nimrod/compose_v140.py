"""Compose the user-review-2 comparison sheets: War Thunder reference | ours 1.3.2 (before) | ours 1.4.0 (after) [| user shot].
Sheets contain War Thunder renders: they are written OUTSIDE the repo (nuclearoption-ref/study/nimrod_v140/sheets) and never go in git.

  python blender/nimrod/compose_v140.py <render dir> <sheet dir>
"""
import os, sys
from PIL import Image, ImageDraw, ImageFont

R, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)
USER = r'C:\Users\User\nuclearoption-ref\refs\nimrod_user_review_2'
try:
    FONT = ImageFont.truetype(os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts', 'arialbd.ttf'), 24)
except Exception:
    FONT = ImageFont.load_default()
SHOTS = {'s1_tail_top': 'shot1.jpg', 's2_tail_below': 'shot2.png', 's4_hook': 'shot4.png', 's6_radiator': 'shot6.png', 's8_guns': 'shot8.webp',
         's10_centre': 'shot10.webp', 's12_nose': 'shot12.png', 's13_seam_fus': 'shot13.jpg', 's14_seam_wing': 'shot14.jpg', 's16_side': 'shot16.png',
         's17_cockpit': 'shot17.jpg'}
names = sorted({f[len('wt_'):-4] for f in os.listdir(R) if f.startswith('wt_') and f.endswith('.png')})
W = 760
for n in names:
    cols = []
    for tag, fn in (('War Thunder (reference only)', f'wt_{n}.png'), ('ours 1.3.2 (before)', f'before_{n}.png'), ('ours 1.4.0 (after)', f'after_{n}.png'),
                    ('ours 1.4.0 workbench', f'afterwb_{n}.png')):
        p = os.path.join(R, fn)
        if os.path.exists(p):
            cols.append((tag, Image.open(p).convert('RGB')))
    if n in SHOTS and os.path.exists(os.path.join(USER, SHOTS[n])):
        cols.append(('user screenshot', Image.open(os.path.join(USER, SHOTS[n])).convert('RGB')))
    H = max(int(im.height * W / im.width) for _, im in cols)
    sheet = Image.new('RGB', (W * len(cols), H + 34), (255, 255, 255))
    d = ImageDraw.Draw(sheet)
    for k, (tag, im) in enumerate(cols):
        im = im.resize((W, int(im.height * W / im.width)))
        sheet.paste(im, (k * W, 34))
        d.text((k * W + 8, 4), tag, fill=(0, 0, 0), font=FONT)
    sheet.save(os.path.join(OUT, f'sheet_{n}.jpg'), quality=88)
    print('[sheet]', n, len(cols))
