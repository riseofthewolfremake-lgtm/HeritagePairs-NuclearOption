"""Compose the silhouette overlays (ours filled blue, WT reference outline red) and report IoU / extents per view.
  python blender/nimrod/compose_overlays.py <dir with _sil_*.png> [--keep]
Writes overlay_<view>.png and overlay_report.json; deletes the raw masks unless --keep."""
import sys, os, json
import numpy as np
from PIL import Image, ImageDraw

d = sys.argv[1]
rep = {}
for v in ('side', 'top', 'front'):
    po, pr = os.path.join(d, f'_sil_ours_{v}.png'), os.path.join(d, f'_sil_ref_{v}.png')
    if not os.path.exists(po):
        continue
    a = np.asarray(Image.open(po).convert('RGBA'))[..., 3] > 40
    out = np.full(a.shape + (3,), 250, np.uint8)
    out[a] = (120, 160, 220)
    if os.path.exists(pr):
        b = np.asarray(Image.open(pr).convert('RGBA'))[..., 3] > 40
        edge = b & ~(np.roll(b, 1, 0) & np.roll(b, -1, 0) & np.roll(b, 1, 1) & np.roll(b, -1, 1))
        edge = edge | np.roll(edge, 1, 0) | np.roll(edge, 1, 1)
        out[edge] = (220, 30, 30)
        inter, uni = (a & b).sum(), (a | b).sum()
        ys, xs = np.nonzero(a); yr, xr = np.nonzero(b)
        rep[v] = dict(iou=round(float(inter / uni), 3), ours_px=dict(w=int(xs.max() - xs.min()), h=int(ys.max() - ys.min())),
                      ref_px=dict(w=int(xr.max() - xr.min()), h=int(yr.max() - yr.min())))
    im = Image.fromarray(out)
    ImageDraw.Draw(im).text((12, 10), f'{v}: ours (blue fill) vs War Thunder reference outline (red) - reference only, not ported', fill=(0, 0, 0))
    im.save(os.path.join(d, f'overlay_{v}.png'))
json.dump(rep, open(os.path.join(d, 'overlay_report.json'), 'w'), indent=1)
print(json.dumps(rep))
if '--keep' not in sys.argv:
    for f in os.listdir(d):
        if f.startswith('_sil_'):
            os.remove(os.path.join(d, f))
