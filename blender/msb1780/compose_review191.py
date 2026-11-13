"""1.9.1 before / after sheets (PIL; plain python). Reads <r2>/before/msb1780_review_*.png (the 1.9.0 model), <r2>/after/msb1780_review_*.png
(the 1.9.1 model with the stock EW-25 parts loaded in memory, approximate flat materials) and <r2>/unity/unity_*.png (the BUILT 1.9.1
prefab in the Unity editor with the real stock meshes / placeholder materials) and writes one sheet per topic into <r2>.

  python blender/msb1780/compose_review191.py <r2 dir>
"""
import os, sys
from PIL import Image, ImageDraw

R = os.path.abspath(sys.argv[1])
W = 760


def tile(path, label, w=W):
    if not os.path.exists(path):
        im = Image.new('RGB', (w, int(w * 0.5625)), (60, 20, 20))
        ImageDraw.Draw(im).text((10, 10), 'missing: ' + os.path.basename(path), fill=(255, 200, 200))
    else:
        im = Image.open(path).convert('RGB')
        im = im.resize((w, int(im.height * w / im.width)))
    out = Image.new('RGB', (im.width, im.height + 26), (22, 22, 24))
    out.paste(im, (0, 26))
    ImageDraw.Draw(out).text((8, 6), label, fill=(235, 235, 235))
    return out


def sheet(rows, out, title, note=''):
    tiles = [[tile(p, l) for p, l in r] for r in rows]
    cols = max(len(r) for r in tiles)
    rh = [max(t.height for t in r) for r in tiles]
    S = Image.new('RGB', (W * cols, sum(rh) + 52), (14, 14, 16))
    d = ImageDraw.Draw(S)
    d.text((10, 8), title, fill=(255, 255, 255))
    d.text((10, 28), note, fill=(200, 200, 200))
    y = 52
    for r, h in zip(tiles, rh):
        for i, t in enumerate(r):
            S.paste(t, (i * W, y))
        y += h
    S.save(out)
    print('[sheet]', out, S.size)


b = lambda k: os.path.join(R, 'before', f'msb1780_review_{k}.png')
a = lambda k: os.path.join(R, 'after', f'msb1780_review_{k}.png')
u = lambda k: os.path.join(R, 'unity', f'unity_{k}.png')
NOTE_B = 'left: 1.9.0 (before)   right: 1.9.1 (after, Blender: stock EW-25 parts loaded in memory with flat stand-in colours)'
sheet([[(b('ck_pilot_eye'), '1.9.0 pilot eye'), (a('ck_pilot_eye'), '1.9.1 pilot eye')],
       [(b('ck_overview'), '1.9.0 flight deck, roof hidden'), (a('ck_overview'), '1.9.1 flight deck, roof hidden')],
       [(b('ck_side'), '1.9.0 deck from the left'), (a('ck_side'), '1.9.1 deck from the left')],
       [(u('pilot_eye'), '1.9.1 UNITY (built prefab): pilot eye'), (u('copilot_eye'), '1.9.1 UNITY: co-pilot eye')],
       [(u('pilot_eye_down'), '1.9.1 UNITY: pilot looking down (sticks, pedestal, throttle)'), (u('deck_overview'), '1.9.1 UNITY: deck, roof hidden')]],
      os.path.join(R, 'sheet_cockpit.png'), 'MSB-17/80 cockpit: before / after', NOTE_B + '; bottom rows: Unity editor capture of the built prefab (stock meshes, placeholder materials; crew bodies hidden, stock seats shown)')
sheet([[(b('wso_view'), '1.9.0 WSO, nose skin hidden'), (a('wso_view'), '1.9.1 WSO, nose skin hidden')],
       [(b('wso_eye'), '1.9.0 WSO eye'), (a('wso_eye'), '1.9.1 WSO eye')],
       [(u('wso_eye'), '1.9.1 UNITY: WSO eye'), (u('wso_overview'), '1.9.1 UNITY: WSO, nose skin hidden')]],
      os.path.join(R, 'sheet_wso.png'), 'MSB-17/80 WSO station (glazed nose): before / after', NOTE_B)
sheet([[(b('ewo_view'), '1.9.0 EWO, centre-section skin hidden'), (a('ewo_view'), '1.9.1 EWO, centre-section skin hidden')],
       [(b('ewo_eye'), '1.9.0 EWO eye'), (a('ewo_eye'), '1.9.1 EWO eye')],
       [(u('ewo_eye'), '1.9.1 UNITY: EWO eye'), (u('ewo_overview'), '1.9.1 UNITY: EWO, skin hidden')]],
      os.path.join(R, 'sheet_ewo.png'), 'MSB-17/80 EWO console bank: before / after', NOTE_B)
sheet([[(b('laser_ring'), '1.9.0 ventral laser'), (a('laser_ring'), '1.9.1 ventral laser + seal ring')],
       [(b('laser_ring_under'), '1.9.0 from below'), (a('laser_ring_under'), '1.9.1 from below')]],
      os.path.join(R, 'sheet_laser_ring.png'), 'MSB-17/80 ventral laser ring: before / after', 'left 1.9.0, right 1.9.1')
sheet([[(b('props_close'), '1.9.0 blades'), (a('props_close'), '1.9.1 blades')],
       [(b('props_edge'), '1.9.0 blades from above'), (a('props_edge'), '1.9.1 blades from above')]],
      os.path.join(R, 'sheet_props.png'), 'MSB-17/80 prop blades: before / after', 'left 1.9.0, right 1.9.1 (NACA sections, one twist law, scimitar sweep in the plane of rotation, rows 0.50 m apart, counter-rotating)')
