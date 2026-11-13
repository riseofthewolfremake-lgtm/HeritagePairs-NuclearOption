"""Round 6 review helper (plain Python + PIL): --pattern writes the tac-page UV test pattern the renders put on the screens (regions of
the CI-22 tac page, labelled; NOT game art); --sheets composes the contact sheets listed by render_v7_fd32.py and deletes the frames.

  python blender/fd32/compose_v7_fd32.py --out <folder> --pattern | --sheets
"""
import os, sys, json
from PIL import Image, ImageDraw
OUT = os.path.abspath(sys.argv[sys.argv.index('--out') + 1])
os.makedirs(OUT, exist_ok=True)
if '--pattern' in sys.argv:
    pat = Image.new('RGB', (1024, 512), (10, 30, 20))
    dr = ImageDraw.Draw(pat)
    for gx in range(0, 810, 40):
        dr.line([(gx, 0), (gx, 512)], fill=(30, 110, 60))
    for gy in range(0, 512, 40):
        dr.line([(0, gy), (808, gy)], fill=(30, 110, 60))
    dr.text((300, 240), 'MAP / RADAR (camera on lock)', fill=(200, 255, 200))
    for (u0, u1, v0, v1), col, lab in (((0.802, 0.983, 0.718, 0.979), (200, 120, 30), 'POWER'), ((0.801, 0.985, 0.390, 0.697), (40, 120, 200), 'ENGINE'),
                                        ((0.789, 0.983, 0.025, 0.341), (180, 40, 160), 'FLIGHT')):
        b = (int(u0 * 1024), int((1 - v1) * 512), int(u1 * 1024), int((1 - v0) * 512))
        dr.rectangle(b, fill=col)
        dr.text((b[0] + 20, (b[1] + b[3]) // 2), lab, fill=(255, 255, 255))
    pat.save(os.path.join(OUT, '_tac_test_pattern.png'))
if '--sheets' in sys.argv:
    for name, (cols, files) in json.load(open(os.path.join(OUT, '_sheets.json'))).items():
        ims = [Image.open(f).convert('RGB') for f in files]
        w, h = ims[0].size
        rows = (len(ims) + cols - 1) // cols
        out = Image.new('RGB', (w * cols, h * rows), 'white')
        for i, im in enumerate(ims):
            out.paste(im, ((i % cols) * w, (i // cols) * h))
            ImageDraw.Draw(out).text(((i % cols) * w + 10, (i // cols) * h + 10), os.path.basename(files[i]), fill=(0, 0, 0))
        out.save(os.path.join(OUT, name + '.png'))
        for f in files:
            os.remove(f)
        print('[compose]', name)
