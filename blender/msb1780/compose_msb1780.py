"""Contact sheets for the MSB-17/80 review renders (PIL; plain python, not Blender). Reads the PNGs render_msb1780.py wrote and writes
sheets next to them (outside the repo):

  python blender/msb1780/compose_msb1780.py <r1 dir>      (expects <r1>/msb/msb1780_*.png and <r1>/b17g/b17g_*.png)

  overview_sheet.png   B-17G | MSB-17/80 side by side: side, top, front, three-quarter front, three-quarter rear, under
  liveries_sheet.png   every MSB livery, three-quarter front and rear
  stations_sheet.png   cockpit overview / pilot eye / panel, EWO and WSO stations
  turrets_sheet.png    chin, tail, dorsal laser, ventral laser, props, and the twin 20 mm close-ups
  bay_sheet.png        the bay empty and with stock store envelopes (boxes)
"""
import os, sys, glob
from PIL import Image, ImageDraw

R = os.path.abspath(sys.argv[1])
MSB, B17 = os.path.join(R, 'msb'), os.path.join(R, 'b17g')
W = 760


def tile(path, label, w=W):
    if not os.path.exists(path):
        im = Image.new('RGB', (w, int(w * 0.62)), (60, 20, 20))
        ImageDraw.Draw(im).text((10, 10), 'missing: ' + os.path.basename(path), fill=(255, 200, 200))
    else:
        im = Image.open(path).convert('RGB')
        im = im.resize((w, int(im.height * w / im.width)))
    out = Image.new('RGB', (im.width, im.height + 26), (22, 22, 24))
    out.paste(im, (0, 26))
    ImageDraw.Draw(out).text((8, 6), label, fill=(235, 235, 235))
    return out


def sheet(tiles, cols, out, title):
    rows = [tiles[i:i + cols] for i in range(0, len(tiles), cols)]
    cw = max(t.width for t in tiles)
    rh = [max(t.height for t in r) for r in rows]
    S = Image.new('RGB', (cw * cols, sum(rh) + 34), (14, 14, 16))
    ImageDraw.Draw(S).text((10, 10), title, fill=(255, 255, 255))
    y = 34
    for r, h in zip(rows, rh):
        for i, t in enumerate(r):
            S.paste(t, (i * cw, y))
        y += h
    S.save(out)
    print('[sheet]', out, S.size)


views = [('side', 'side (ortho)'), ('top', 'top (ortho)'), ('front', 'front (ortho)'), ('q34f', 'three-quarter front'), ('q34r', 'three-quarter rear'), ('under', 'under (ortho)')]
t = []
for k, lab in views:
    t.append(tile(os.path.join(B17, f'b17g_{k}.png'), f'B-17G (1.8.18) - {lab}'))
    t.append(tile(os.path.join(MSB, f'msb1780_{k}.png'), f'MSB-17/80 (1.9.0) - {lab}'))
sheet(t, 2, os.path.join(R, 'overview_sheet.png'), 'B-17G vs MSB-17/80, same cameras (Blender EEVEE review renders, not the game shaders)')

liv = sorted(glob.glob(os.path.join(MSB, 'msb1780_livery_*_q34f.png')))
t = []
for f in liv:
    key = os.path.basename(f)[len('msb1780_livery_'):-len('_q34f.png')]
    t.append(tile(f, f'{key} - front')); t.append(tile(f.replace('_q34f', '_q34r'), f'{key} - rear'))
sheet(t, 2, os.path.join(R, 'liveries_sheet.png'), f'MSB-17/80 liveries ({len(liv)}: BDF and PALA)')

st = [('cockpit_overview', 'cockpit from above (canopy hidden)'), ('cockpit_pilot_eye', 'pilot eye'), ('cockpit_panel', 'panel: 5 screens, glare shield, HUD frame'),
      ('station_ewo', 'EWO station (behind the co-pilot)'), ('station_wso', 'WSO station in the nose'), ('station_wso_side', 'WSO station, side (skin hidden)')]
sheet([tile(os.path.join(MSB, f'msb1780_{k}.png'), lab) for k, lab in st], 2, os.path.join(R, 'stations_sheet.png'), 'MSB-17/80 crew stations (4 crew, stock ejection seats)')

tu = [('turret_chin', 'chin twin 20 mm'), ('turret_chin_side', 'chin, side'), ('turret_tail', 'tail twin 20 mm'), ('turret_tail_side', 'tail, side'),
      ('turret_dorsal', 'dorsal 120 kW laser'), ('turret_ventral', 'ventral 120 kW laser'), ('nacelle_props', 'turboshaft nacelle, contra-rotating 6-blade rows'),
      ('gun20_q34', 'own twin 20 mm (gun only)'), ('gun20_side', 'twin 20 mm side'), ('gun20_top', 'twin 20 mm top'), ('gun20_muzzle', 'muzzle brakes')]
sheet([tile(os.path.join(MSB, f'msb1780_{k}.png'), lab) for k, lab in tu], 2, os.path.join(R, 'turrets_sheet.png'), 'MSB-17/80 turrets, props and the twin 20 mm')

ba = [('bay_empty', 'bay 5.7 m, doors hidden'), ('bay_gpo500x8', 'GPO-500 x8 (stock envelope box)'), ('bay_agm68_x8', 'AGM-68 x8'), ('bay_alm_x2', 'ALM-C450 x2'),
      ('bay_pab250_16', 'PAB-250 x16 (tandem)'), ('bay_pab80_12', 'glide bombs x12 (side racks)')]
sheet([tile(os.path.join(MSB, f'msb1780_{k}.png'), lab) for k, lab in ba], 2, os.path.join(R, 'bay_sheet.png'), 'MSB-17/80 bay loadouts (stock mount envelopes drawn as boxes)')
