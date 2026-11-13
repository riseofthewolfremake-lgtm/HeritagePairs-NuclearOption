"""1.9.6 review sheets (PIL; plain python): the same Unity editor cameras (unity/Editor/MSB1780CockpitShot.cs Shoot195) on the built prefab,
1.9.5 (study/msb1780/r5/unity_195) | 1.9.6 (r6/unity_196), real stock meshes; '_live' = every tacScreenDisplay slot drawn flat green (a screen
that shows the live tac page in game; the editor cannot drive the render texture). Writes into <r6>: sheet_deck_196.png (1.9.5 | 1.9.6,
live-marked), sheet_deck_196_plain.png (as the editor draws it), sheet_closeups_196.png (panel, pedestal, left console; 1.9.6 only).

  python blender/msb1780/compose_review196.py <r6 dir>
"""
import os, sys
from PIL import Image, ImageDraw

R = os.path.abspath(sys.argv[1])
R5 = os.path.join(os.path.dirname(R), 'r5')
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
        ('deck_behind', 'the deck from behind (fixed camera)'), ('overhead', 'the overhead strip (fixed camera)')]
for suf, name, note in (('_live', 'sheet_deck_196.png', 'GREEN = a screen that shows the LIVE tac page in game (the editor cannot drive the render texture). 1.9.6: the standby screen is live too.'),
                        ('', 'sheet_deck_196_plain.png', 'as the editor draws it: the tac page renders black; legends / lamps are emissive materials (placeholder lighting).')):
    rows = [[(os.path.join(R5, 'unity_195', f'u195_{k}{suf}.png'), f'1.9.5: {t}'), (os.path.join(R, 'unity_196', f'u195_{k}{suf}.png'), f'1.9.6 detail pass: {t}')] for k, t in CAMS]
    sheet(rows, os.path.join(R, name), 'MSB-17/80 flight deck: 1.9.5 | 1.9.6 (detail pass on our own deck) - Unity editor, same cameras, real stock meshes', note + ' Crew bodies hidden; stock seats shown.')
sheet([[(os.path.join(R, 'unity_196', 'u195_closeup_panel.png'), '1.9.6 close-up: main panel (stack, gear / flap, wells, annunciators, legends)'),
        (os.path.join(R, 'unity_196', 'u195_closeup_panel_live.png'), '1.9.6 close-up: main panel, live screens green')],
       [(os.path.join(R, 'unity_196', 'u195_closeup_pedestal.png'), '1.9.6 close-up: pedestal (quadrant surround, radio heads, trim, speed brake)'),
        (os.path.join(R, 'unity_196', 'u195_closeup_console_L.png'), '1.9.6 close-up: left console (comm, oxygen, switches, map pocket)')]],
      os.path.join(R, 'sheet_closeups_196.png'), 'MSB-17/80 1.9.6 close-ups (Unity editor, real stock meshes)', 'stock: sfb_joystick, sfb_throttle, EW1_warningLights, ejectionSeat; everything else ours.')
