"""1.9.5 review sheets (PIL; plain python): the SAME Unity editor cameras (unity/Editor/MSB1780CockpitShot.cs Shoot195) on the built prefab
before (the 1.9.4 build = the 1.9.1 stock EW-25 deck) and after (1.9.5: our deck with single stock parts). Real stock meshes in both; the
tac page renders black in the editor, so the '_live' captures draw every tacScreenDisplay slot flat green = a screen that shows the live tac
page in game. Writes into <r5>: sheet_deck_195.png (1.9.1 | 1.9.5, live-marked), sheet_deck_195_plain.png (as the editor draws it),
sheet_stations_195.png (WSO / EWO).

  python blender/msb1780/compose_review195.py <r5 dir>
"""
import os, sys
from PIL import Image, ImageDraw

R = os.path.abspath(sys.argv[1])
W = 800


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


CAMS = [('pilot_eye', 'pilot eye'), ('copilot_eye', 'co-pilot eye'), ('down_controls', 'looking down: sticks, pedestal, throttle'),
        ('deck_behind', 'the deck from behind (fixed camera at the 1.9.1 eye mid point, over the EWO seat)'), ('overhead', 'the overhead strip (fixed camera)')]
for suf, name, note in (('_live', 'sheet_deck_195.png', 'GREEN = a screen that shows the LIVE tac page in game (the editor cannot drive the render texture; every tacScreenDisplay slot is drawn flat green). Dark screens = stock dark glass.'),
                        ('', 'sheet_deck_195_plain.png', 'as the editor draws it: the tac page renders black (render texture not driven outside the game); placeholder materials.')):
    rows = [[(os.path.join(R, 'unity_191', f'u195_{k}{suf}.png'), f'1.9.1-1.9.4 stock EW-25 deck: {t}'), (os.path.join(R, 'unity_195', f'u195_{k}{suf}.png'), f'1.9.5 our deck + single stock parts: {t}')]
            for k, t in CAMS]
    sheet(rows, os.path.join(R, name), 'MSB-17/80 flight deck: 1.9.1 (whole stock EW-25 cockpit) | 1.9.5 (our own deck, single stock parts) - Unity editor, same cameras, real stock meshes',
          note + ' Crew bodies hidden; the stock ejection seats shown. 1.9.5 pilots sit 0.11 m further forward and 0.04 m lower than 1.9.1 (seat clearance), so the eye cameras moved with them.')
rows = [[(os.path.join(R, 'unity_191', f'u195_{k}_live.png'), f'1.9.1-1.9.4: {t}'), (os.path.join(R, 'unity_195', f'u195_{k}_live.png'), f'1.9.5: {t}')]
        for k, t in (('wso_eye', 'WSO eye'), ('ewo_eye', 'EWO eye'))]
sheet(rows, os.path.join(R, 'sheet_stations_195.png'), 'MSB-17/80 WSO / EWO stations (kept from 1.9.1): 1.9.1 | 1.9.5',
      'green = live tac page. 1.9.5 changes only what clashed: WSO eye 0.035 m up + thin seat plate (the stock seat base sat in the floor), EWO desk edge 0.12 m outboard (the seat armrests).')
