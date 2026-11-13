"""Side-by-side of the B-25H cockpit renders with the user's reference photos (local only: the output contains the photos and
is git-ignored by media/b25h_cockpit_v3/.gitignore; the photos are never copied into the repo).

  python blender/v2/compose_side_by_side_b25h.py <render dir> <photo dir> <out.jpg>
"""
import os, sys
from PIL import Image, ImageDraw

rd, ph, out = sys.argv[1:4]
pairs = [('44', 'pilot_eye'), ('48', 'panel_front'), ('45', 'three_quarter')]
H = 420
rows = []
for p, r in pairs:
    src = [f for f in os.listdir(ph) if f.split('.')[0] == p][0]
    a = Image.open(os.path.join(ph, src)).convert('RGB')
    b = Image.open(os.path.join(rd, r + '.png')).convert('RGB')
    a = a.resize((int(a.width * H / a.height), H)); b = b.resize((int(b.width * H / b.height), H))
    row = Image.new('RGB', (a.width + b.width + 10, H + 24), (20, 20, 20))
    row.paste(a, (0, 24)); row.paste(b, (a.width + 10, 24))
    d = ImageDraw.Draw(row)
    d.text((6, 5), f'photo {p} (user reference, local only)', fill=(230, 230, 230))
    d.text((a.width + 16, 5), f'B-25H v3 render: {r}', fill=(230, 230, 230))
    rows.append(row)
W = max(r.width for r in rows)
img = Image.new('RGB', (W, sum(r.height for r in rows) + 6 * len(rows)), (20, 20, 20))
y = 0
for r in rows:
    img.paste(r, (0, y)); y += r.height + 6
img.save(out, quality=88)
print('wrote', out)
