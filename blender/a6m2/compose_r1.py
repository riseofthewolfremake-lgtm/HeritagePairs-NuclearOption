"""Side-by-side review sheets: our render (left) next to the WT reference render of the same name and camera rule (right).
  python blender/a6m2/compose_r1.py <our renders dir> <WT renders dir> <out dir> [round label, default 'round 1']
Sheets are review material only (they show the reference): written outside the repo, never committed (.gitignore side_by_side*).
"""
import os, sys
from PIL import Image, ImageDraw
ours, wt, out = sys.argv[1:4]
label = sys.argv[4] if len(sys.argv) > 4 else 'round 1'
os.makedirs(out, exist_ok=True)
n = 0
for f in sorted(os.listdir(ours)):
    if not f.endswith('.png') or f.startswith(('sil_', 'overlay_', 'side_by_side', 'dbg_')):
        continue
    a = Image.open(os.path.join(ours, f)).convert('RGB')
    w = os.path.join(wt, f)
    b = Image.open(w).convert('RGB') if os.path.exists(w) else Image.new('RGB', a.size, (60, 60, 60))
    b = b.resize(a.size)
    s = Image.new('RGB', (a.width * 2 + 10, a.height), (0, 0, 0))
    s.paste(a, (0, 0)); s.paste(b, (a.width + 10, 0))
    d = ImageDraw.Draw(s)
    d.text((12, 10), 'OURS (%s, placeholder grey)' % label, fill=(255, 255, 0)); d.text((a.width + 22, 10), 'WT reference' if os.path.exists(w) else 'no reference render at this angle', fill=(255, 255, 0))
    s.save(os.path.join(out, 'side_by_side_' + f)); n += 1
print('sheets', n)
