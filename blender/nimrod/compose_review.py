"""Compose the user-review-1 comparison sheets (PIL).

  python blender/nimrod/compose_review.py

media/nimrod_v3/before_after_<defect>.jpg       our 1.2.3 renders (before) next to the 1.3.0 renders (after); our own art -> in git
media/nimrod_v3/side_by_side_<defect>.jpg       + the user's screenshot (refs/nimrod_user_review_1): NEVER in git (.gitignore side_by_side*)
media/nimrod_v3/side_by_side_wt_<view>.jpg      War Thunder reference render (refs/nimrod_wt/renders) next to ours: NEVER in git
"""
import os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
M = os.path.join(ROOT, 'media', 'nimrod_v3')
USER = r'C:\Users\User\nuclearoption-ref\refs\nimrod_user_review_1'
WT = r'C:\Users\User\nuclearoption-ref\refs\nimrod_wt\renders'
try:
    FONT = ImageFont.truetype(os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts', 'arialbd.ttf'), 26)
except Exception:
    FONT = ImageFont.load_default()

DEFECTS = {   # name: (user shot, [render names])
    'd1_cockpit_struts': ('shot1.jpg', ['tex_d1_cockpit_struts', 'solid_d1_cabane_feet']),
    'd2_wings_guns': ('shot2.jpg', ['tex_d2_front34_wings', 'solid_d2_lower_root', 'tex_d2_gun_close', 'tex_d2_guns_above']),
    'd3_exhausts': ('shot4.jpg', ['tex_d3_cowling_side', 'solid_d3_cowling_side']),
    'd4_interplane': ('shot5.jpg', ['tex_d4_interplane', 'solid_d4_interplane_ext']),
    'd5_upper_wing_tip': ('shot6.jpg', ['tex_d5_side_upperwing', 'solid_d5_tip_R', 'solid_d5_tip_L']),
    'd6_tail': ('shot7.jpg', ['tex_d6_tail_below', 'solid_d6_stab_root', 'solid_d6_tail_34']),
    'd7_breakup': ('shot8.jpg', ['broken_fus_rear_c', 'broken_fus_rear_a', 'broken_fus_center_c', 'broken_fus_engine_d', 'broken_wing_upper_L_d',
                                 'broken_wing_upper_C_c', 'broken_wing_lower_L_b', 'broken_stab_L_d', 'broken_fin_b', 'broken_aileron_L_c']),
    'd8_hook': ('shot7.jpg', ['solid_d8_hook_deployed_side_deployed', 'solid_d8_hook_below_deployed']),
    'd9_pedals': (None, ['cockpit/cockpit_floor', 'cockpit/cockpit_pilot_eye']),
}


def load(path, w):
    if not os.path.exists(path):
        return None
    im = Image.open(path).convert('RGB')
    return im.resize((w, int(im.height * w / im.width)))


def label(im, text):
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, im.width, 34), fill=(20, 20, 20))
    d.text((8, 3), text, fill=(240, 240, 240), font=FONT)
    return im


def column(images, w):
    ims = [i for i in images if i is not None]
    if not ims:
        return None
    h = sum(i.height for i in ims)
    out = Image.new('RGB', (w, h), 'white')
    y = 0
    for i in ims:
        out.paste(i, (0, y)); y += i.height
    return out


def sheet(cols, path):
    cols = [c for c in cols if c is not None]
    W = sum(c.width for c in cols); H = max(c.height for c in cols)
    out = Image.new('RGB', (W, H), 'white')
    x = 0
    for c in cols:
        out.paste(c, (x, 0)); x += c.width
    out.save(path, quality=86)
    print('[compose]', path)


W = 820
for name, (shot, renders) in DEFECTS.items():
    bcol = column([label(im, 'BEFORE 1.2.3  ' + r) for r in renders if (im := load(os.path.join(M, 'before', r + '.png'), W)) is not None], W)
    acol = column([label(im, 'AFTER 1.3.0  ' + r) for r in renders if (im := load(os.path.join(M, 'after', r + '.png'), W)) is not None], W)
    sheet([bcol, acol], os.path.join(M, f'before_after_{name}.jpg'))
    if shot:
        u = load(os.path.join(USER, shot), W)
        if u is not None:
            sheet([column([label(u, 'USER 1.2.3 ' + shot)], W), bcol, acol], os.path.join(M, f'side_by_side_{name}.jpg'))
for v in ('d2_front34_wings', 'd2_gun_close', 'd3_cowling_side', 'd4_interplane_ext', 'd6_tail_34', 'd8_hook_below', 'gear_front', 'full_34front'):
    w_ = load(os.path.join(WT, f'wt_{v}.png'), W)
    o = load(os.path.join(M, 'after', f'solid_{v}.png'), W)
    t = load(os.path.join(M, 'after', f'tex_{v}.png'), W)
    if w_ is not None and o is not None:
        sheet([column([label(w_, 'WT reference (reference only) ' + v)], W), column([label(o, 'OURS 1.3.0 solid')], W),
               column([label(t, 'OURS 1.3.0 textured')], W) if t is not None else None], os.path.join(M, f'side_by_side_wt_{v}.jpg'))
lv = [label(load(os.path.join(M, 'after', 'tex_full_34front.png'), W), 'faa_silver')]
for L in ('bdf_mattegrey', 'bdf_temperate', 'pala_matteblack', 'pala_desert'):
    im = load(os.path.join(M, 'after', f'liv_{L}', 'tex_full_34front.png'), W)
    if im is not None:
        lv.append(label(im, L))
sheet([column(lv[:3], W), column(lv[3:], W)], os.path.join(M, 'liveries_130.jpg'))
