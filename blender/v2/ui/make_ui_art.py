"""B-25H UI art from the model: map icon (also the aircraft-selection button icon) and the cockpit/HUD damage
status display (background line art + one sprite per UnitPart + a layout file the Unity build wires up).

  blender --background assets/model_v2/b25h_v2.blend --python blender/v2/ui/make_ui_art.py -- [--out assets/ui]
        [--parts unity/Editor/B25HBuild.cs | <parts.json>] [--res 4096]

Stock conventions this follows (evidence in docs/stock_ui_study.md):
  * UnitDefinition.mapIcon: one Sprite used by the map (UnitMapIcon, tinted by IFF colour via Image.color, rotated
    with heading when mapOrient) AND by the hangar aircraft-selection button (AircraftSelectionButton,
    image.sprite = definition.mapIcon). Stock aircraft icons: white top-down silhouette, nose up, transparent
    background, 256x256 (or 128), span touching the edges (1-2 px margin); glazing drawn half-transparent.
  * AircraftParameters.StatusDisplay: a prefab (root RectTransform 300x300, anchored bottom-right, StatusDisplay
    component) whose root Image shows a 1024x1024 white-on-black line drawing of the aircraft from above, and one
    child Image per UnitPart, GameObject name == UnitPart GameObject name, sprite = grey part silhouette on black
    (128x128 / 128x64 / 64x128), drawn with the additive UI material (black = invisible). Left-side parts reuse the
    right-side sprite with a negative X scale. StatusDisplay tints them (yellow -> red) and fades them in by damage.
Parts are read from the build script's Parts() table (UnitPart name -> source mesh object), so the art follows the
current split; every other mesh object belongs to the nearest ancestor that is a part's source object.
"""
import bpy, sys, os, re, json, math
import numpy as np
from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
opt = lambda k, d: argv[argv.index(k) + 1] if k in argv else d
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
OUT = os.path.abspath(opt('--out', os.path.join(ROOT, 'assets', 'ui')))
PARTS_SRC = os.path.abspath(opt('--parts', os.path.join(ROOT, 'unity', 'Editor', 'B25HBuild.cs')))
RES = int(opt('--res', '4096'))
SDIR = os.path.join(OUT, 'status')
PDIR = os.path.join(OUT, 'previews')
for d in (OUT, SDIR, PDIR):
    os.makedirs(d, exist_ok=True)
F32 = np.float32

# stock numbers (CAS1_statusDisplay prefab / CAS1 status sprites, see docs/stock_ui_study.md)
UI_SIZE = 300.0            # root RectTransform size (UI units); the background sprite fills it
BG_RES = 1024              # background line-art texture
SPR = 128                  # part sprite long side (short side 64 when the part is long and thin)
FILL = 214 / 255           # grey level of stock part sprites (max 214-219)
LINE = 205 / 255           # grey level of stock background lines
RED_THRESHOLD = 30         # PartStatusDisplay.redStatusThreshold on every stock CAS1 entry
ICON = 256


# ------------------------------------------------------------------ parts table
def parts_from_build_script(path):
    """[(part, source_object)] from `new PartSpec("name", "parent", "mesh", ...)` lines; '+ s' expands to L / R."""
    src = open(path, encoding='utf-8').read()
    body = src[src.index('static List<PartSpec> Parts()'):]
    body = body[:body.index('return l;')]
    out = []
    for line in body.splitlines():
        m = re.search(r'new PartSpec\((.*)\)\);?|new PartSpec\((.*)\),', line)
        if not m:
            continue
        args = (m.group(1) or m.group(2))
        a = [x.strip() for x in re.split(r',(?=(?:[^"]*"[^"]*")*[^"]*$)', args)][:3]

        def ev(x, s):
            if x == 'null':
                return None
            return eval(x.replace('+ s', f'+ "{s}"'))     # only string literals and '+ s' occur here
        sides = ['L', 'R'] if any('+ s' in x for x in a) else [None]
        for s in sides:
            out.append((ev(a[0], s), ev(a[2], s)))
    return out


if PARTS_SRC.endswith('.json'):
    PARTS = [(p['part'], p.get('object')) for p in json.load(open(PARTS_SRC))['parts']]
else:
    PARTS = parts_from_build_script(PARTS_SRC)
# a part without a source mesh in the table is the propeller (built on prop_hub_<side>)
PARTS = [(p, o if o else ('prop_hub_' + p[5:] if p.startswith('prop_') else None)) for p, o in PARTS]
print('[ui] parts', len(PARTS), PARTS)
src_of = {o: p for p, o in PARTS if o}

SKIP = re.compile(r'^(prop_[LR]_blade|propdisc|cockpit_|gauge_|mfd_|gunsight_|crew_|gun_waist_|muzzle|hp_)')  # blades/discs, interior, side-pointing waist guns


def part_of(ob):
    o = ob
    while o is not None:
        if o.name in src_of:
            return src_of[o.name]
        o = o.parent
    return None


meshes = [o for o in bpy.data.objects if o.type == 'MESH' and not SKIP.match(o.name)]
owner = {o.name: part_of(o) for o in meshes}
missing = [p for p, o in PARTS if o and o not in bpy.data.objects]
print('[ui] part sources missing in the .blend:', missing)
part_names = [p for p, o in PARTS]

# ------------------------------------------------------------------ render setup (Workbench, flat, no AA)
sc = bpy.context.scene
sc.render.engine = 'BLENDER_WORKBENCH'
sc.display.shading.light = 'FLAT'
sc.display.shading.show_object_outline = False
sc.display.shading.show_cavity = False
sc.display.shading.show_specular_highlight = False
sc.display.shading.show_shadows = False
sc.display.shading.show_xray = False
sc.display.render_aa = 'OFF'
sc.view_settings.view_transform = 'Standard'
sc.view_settings.look = 'None'
sc.view_settings.exposure = 0
sc.view_settings.gamma = 1
sc.render.film_transparent = True
sc.render.image_settings.file_format = 'PNG'
sc.render.image_settings.color_mode = 'RGBA'
sc.render.image_settings.color_depth = '8'
sc.render.resolution_x = sc.render.resolution_y = RES
sc.render.resolution_percentage = 100
for o in bpy.data.objects:
    if o.type == 'MESH':
        o.hide_render = o not in meshes
# gear down in the file: the top view hides it anyway (wheels sit under nacelles/fuselage)

mins = np.array([1e9] * 3); maxs = -mins
for o in meshes:
    for c in o.bound_box:
        v = np.array(o.matrix_world @ Vector(c)); mins = np.minimum(mins, v); maxs = np.maximum(maxs, v)
span = float(maxs[0] - mins[0]); length = float(maxs[1] - mins[1])
EXT = max(span, length) * 1.0 / 0.985          # square frame, span fills it with ~0.75 % margin per side
CX, CY = float(mins[0] + maxs[0]) / 2, float(mins[1] + maxs[1]) / 2
print(f'[ui] bbox x {mins[0]:.2f}..{maxs[0]:.2f} y {mins[1]:.2f}..{maxs[1]:.2f}; frame {EXT:.2f} m')
cam = bpy.data.objects.new('ui_cam', bpy.data.cameras.new('ui_cam'))
sc.collection.objects.link(cam)
sc.camera = cam
cam.data.type = 'ORTHO'
cam.data.ortho_scale = EXT
cam.data.clip_start, cam.data.clip_end = 0.1, 200
cam.location = (CX, CY, float(maxs[2]) + 20)
cam.rotation_euler = (0, 0, 0)                # looking down -Z, image up = +Y = nose, image right = +X = right wing


def srgb(c):
    c = np.asarray(c, F32)
    return np.where(c <= 0.0031308, 12.92 * c, 1.055 * np.power(np.maximum(c, 0), 1 / 2.4) - 0.055)


LEV = [0.0, 0.18, 0.4, 0.7, 1.0]
PALETTE = np.array([(a, b, c) for a in LEV for b in LEV for c in LEV][1:], F32)   # 124 distinct ids (0 = black skipped)


def render_ids(label_of, tag):
    """render with an object colour per label; returns int map (H, W), -1 = background; row 0 = top."""
    labels = sorted({label_of(o) for o in meshes if label_of(o) is not None})
    assert len(labels) <= len(PALETTE), len(labels)
    lid = {l: i for i, l in enumerate(labels)}
    sc.display.shading.color_type = 'OBJECT'
    for o in meshes:
        l = label_of(o)
        o.hide_render = l is None
        if l is not None:
            o.color = (*PALETTE[lid[l]], 1.0)
    path = os.path.join(bpy.app.tempdir, f'ui_{tag}.png')
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    im = bpy.data.images.load(path)
    a = np.empty(RES * RES * 4, F32)
    im.pixels.foreach_get(a)
    bpy.data.images.remove(im)
    a = a.reshape(RES, RES, 4)[::-1]          # row 0 = top
    ref = srgb(PALETTE[:len(labels)])
    ids = np.full((RES, RES), -1, np.int32)
    m = a[..., 3] > 0.5
    px = a[..., :3][m]
    best = np.zeros(len(px), np.int32)
    bd = np.full(len(px), 1e9, F32)
    for i, c in enumerate(ref):
        d = ((px - c) ** 2).sum(-1)
        upd = d < bd
        best[upd] = i
        bd[upd] = d[upd]
    ids[m] = best
    print(f'[ui] render {tag}: {len(labels)} labels, max decode error {float(np.sqrt(bd.max())) if len(bd) else 0:.4f}')
    for o in meshes:
        o.hide_render = False
    return ids, labels


part_ids, part_labels = render_ids(lambda o: owner[o.name], 'parts')


def detail_label(o):
    """line-art grouping: one region per object, cowl flaps merged into their engine."""
    if o.name.startswith('cowl_flap_'):
        return 'engine_' + o.name[10]
    return o.name


det_ids, _ = render_ids(detail_label, 'detail')


def glass_label(o):
    return o.name if any(m and 'glass' in m.name for m in o.data.materials) else 'solid'


# glazing mask: per-material is needed (fus_tail / waist blisters mix glass and paint), so colour by material
sc.display.shading.color_type = 'MATERIAL'
saved = {}
for m in bpy.data.materials:
    saved[m.name] = tuple(m.diffuse_color)
    m.diffuse_color = (1, 0, 0, 1) if 'glass' in m.name else (1, 1, 1, 1)
path = os.path.join(bpy.app.tempdir, 'ui_glass.png')
sc.render.filepath = path
bpy.ops.render.render(write_still=True)
im = bpy.data.images.load(path)
g = np.empty(RES * RES * 4, F32)
im.pixels.foreach_get(g)
bpy.data.images.remove(im)
g = g.reshape(RES, RES, 4)[::-1]
for m in bpy.data.materials:
    m.diffuse_color = saved[m.name]
solid = g[..., 3] > 0.5
glass = solid & (g[..., 1] < 0.5)
print('[ui] glazing px', int(glass.sum()), 'solid px', int(solid.sum()))


# ------------------------------------------------------------------ image helpers (numpy, row 0 = top)
def box_down(a, f):
    h, w = a.shape[:2]
    return a[:h // f * f, :w // f * f].reshape(h // f, f, w // f, f, *a.shape[2:]).mean(axis=(1, 3))


def resample(a, ow, oh):
    """area-ish resample of a 2D float array to (oh, ow) by supersampled bilinear."""
    h, w = a.shape
    ys = (np.arange(oh * 4) + 0.5) / (oh * 4) * h - 0.5
    xs = (np.arange(ow * 4) + 0.5) / (ow * 4) * w - 0.5
    y0 = np.clip(np.floor(ys).astype(int), 0, h - 1); y1 = np.clip(y0 + 1, 0, h - 1); fy = np.clip(ys - y0, 0, 1)
    x0 = np.clip(np.floor(xs).astype(int), 0, w - 1); x1 = np.clip(x0 + 1, 0, w - 1); fx = np.clip(xs - x0, 0, 1)
    t = a[y0][:, x0] * (1 - fx) + a[y0][:, x1] * fx
    b = a[y1][:, x0] * (1 - fx) + a[y1][:, x1] * fx
    r = t * (1 - fy[:, None]) + b * fy[:, None]
    return r.reshape(oh, 4, ow, 4).mean(axis=(1, 3))


def dilate(m, r):
    out = m.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx * dx + dy * dy <= r * r:
                out |= np.roll(np.roll(m, dy, 0), dx, 1)
    return out


def save_png(path, rgba):
    rgba = np.clip(np.asarray(rgba, F32), 0, 1)
    h, w = rgba.shape[:2]
    im = bpy.data.images.new(os.path.basename(path), w, h, alpha=True)
    im.colorspace_settings.name = 'Non-Color'
    im.pixels.foreach_set(rgba[::-1].ravel())
    im.filepath_raw = path
    im.file_format = 'PNG'
    im.save()
    bpy.data.images.remove(im)
    print('[ui] wrote', os.path.relpath(path, ROOT), f'{w}x{h}')


px_m = EXT / RES                                 # metres per render pixel
written = []

# ------------------------------------------------------------------ 1. map icon (= selection button icon)
f = RES // ICON
cov = box_down(solid.astype(F32), f)
gl = box_down(glass.astype(F32), f)
alpha = np.clip(cov - 0.5 * gl, 0, 1)              # glazing at half alpha, like the stock CI-22 icon
icon = np.dstack([np.ones_like(alpha)] * 3 + [alpha])
save_png(os.path.join(OUT, 'b25h_map_icon.png'), icon)
written.append('b25h_map_icon.png')

# ------------------------------------------------------------------ 2. status background (line art)
f = RES // BG_RES
lw = max(1, int(round(RES / BG_RES * 0.9)))       # ~1.8 px lines at 1024 after the box filter
edge = np.zeros((RES, RES), bool)
for ids in (det_ids, part_ids):
    for ax in (0, 1):
        d = np.diff(ids, axis=ax) != 0
        if ax == 0:
            edge[1:] |= d; edge[:-1] |= d
        else:
            edge[:, 1:] |= d; edge[:, :-1] |= d
edge &= dilate(solid, 1) | solid
edge = dilate(edge, lw)
lines = box_down(edge.astype(F32), f) * LINE
bg = np.dstack([lines, lines, lines, np.ones_like(lines)])      # opaque black + grey lines, like the stock sprite
save_png(os.path.join(SDIR, 'b25h_status.png'), bg)
written.append('status/b25h_status.png')

# ------------------------------------------------------------------ 3. part sprites + layout
px_ui = UI_SIZE / RES                              # UI units per render pixel
layout = dict(
    generator='blender/v2/ui/make_ui_art.py', model=os.path.basename(bpy.data.filepath), parts_source=os.path.relpath(PARTS_SRC, ROOT),
    root=dict(name='B25H_statusDisplay', size=[UI_SIZE, UI_SIZE], anchorMin=[1, 0], anchorMax=[1, 0], pivot=[1, -0.05],
              anchoredPosition=[0, -30.1], sprite='status/b25h_status.png', color=[1, 1, 1, 1],
              note='as CAS1_statusDisplay: StatusDisplay component on the root, root Image = aircraftBackground'),
    material='additive UI material (stock Text_additive, shader UI additive): black = invisible',
    part_color=[1, 1, 0, 1], redStatusThreshold=RED_THRESHOLD, metres_per_ui_unit=EXT / UI_SIZE,
    parts=[], failure_indicators=[], hidden_parts=[])
part_bbox = {}
for i, p in enumerate(part_labels):
    m = part_ids == i
    if m.sum() < 20:
        continue
    ys, xs = np.nonzero(m)
    part_bbox[p] = (xs.min(), xs.max() + 1, ys.min(), ys.max() + 1, m)


def sprite_for(p):
    x0, x1, y0, y1, m = part_bbox[p]
    pad = int(round((x1 - x0 + y1 - y0) * 0.02)) + 4
    x0, y0 = max(0, x0 - pad), max(0, y0 - pad)
    x1, y1 = min(RES, x1 + pad), min(RES, y1 + pad)
    crop = m[y0:y1, x0:x1].astype(F32)
    w, h = x1 - x0, y1 - y0
    ar = w / h
    tw, th = (SPR, SPR // 2) if ar > 1.6 else ((SPR // 2, SPR) if ar < 1 / 1.6 else (SPR, SPR))
    s = min(tw / w, th / h)                       # texture px per render px (aspect preserved)
    cw, ch = max(1, int(round(w * s))), max(1, int(round(h * s)))
    small = resample(crop, cw, ch)
    tex = np.zeros((th, tw), F32)
    ox, oy = (tw - cw) // 2, (th - ch) // 2
    tex[oy:oy + ch, ox:ox + cw] = small
    # content centre in texture px vs bbox centre in render px -> UI placement
    cx_r = x0 + w / 2 + ((ox + cw / 2) - tw / 2) / s
    cy_r = y0 + h / 2 + ((oy + ch / 2) - th / 2) / s
    scale = 1 / s * px_ui                          # UI units per texture px
    return tex, (tw, th), (cx_r, cy_r), scale, crop


done = {}
for p in part_names:
    if p not in part_bbox:
        layout['hidden_parts'].append(dict(name=p, reason='not visible from above (no pixels in the top view)'))
        continue
    tex, (tw, th), (cxr, cyr), scale, crop = sprite_for(p)
    sprite, sx = None, 1.0
    if p.endswith('_L') and p[:-2] + '_R' in part_bbox:
        # reuse the right-side sprite mirrored (stock style) when the two halves match
        tr, _, _, _, cr = sprite_for(p[:-2] + '_R')
        if cr.shape == crop.shape:
            iou = (np.minimum(cr, crop[:, ::-1]).sum() / max(np.maximum(cr, crop[:, ::-1]).sum(), 1))
        else:
            iou = 0.0
        if iou > 0.97:
            sprite, sx = done[p[:-2] + '_R'] if p[:-2] + '_R' in done else (None, 1.0), -1.0
            sprite = f'status/b25h_status_{p[:-2]}_R.png'
            # placement of the mirrored sprite: its content centre mirrors the right one's
    if sprite is None:
        sprite = f'status/b25h_status_{p}.png'
        rgba = np.dstack([tex * FILL] * 3 + [tex])
        save_png(os.path.join(OUT, sprite), rgba)
        written.append(sprite)
    done[p] = (sprite, sx)
    pos = [round((cxr - RES / 2) * px_ui, 2), round((RES / 2 - cyr) * px_ui, 2)]
    layout['parts'].append(dict(name=p, sprite=sprite, sizeDelta=[tw, th], anchoredPosition=pos,
                                localScale=[round(sx * scale, 5), round(scale, 5), 1.0], pivot=[0.5, 0.5],
                                anchor=[0.5, 0.5], visible_px=int(part_bbox[p][4].sum())))
# The R sprite may be written after its L partner was decided: make sure every referenced sprite exists
for e in layout['parts']:
    if not os.path.exists(os.path.join(OUT, e['sprite'])):
        p = e['sprite'].split('b25h_status_')[1][:-4]
        tex = sprite_for(p)[0]
        save_png(os.path.join(OUT, e['sprite']), np.dstack([tex * FILL] * 3 + [tex]))
        written.append(e['sprite'])

# failure indicators (names = OnReportDamage.failureMessage strings the stock twin-engine display listens for)
for side, word in (('L', 'LEFT'), ('R', 'RIGHT')):
    for tag, part, h in (('ENGINE FAILURE', 'engine_' + side, 33.4), ('PROP STRIKE', 'prop_' + side, 17.67)):
        if part not in part_bbox:
            continue
        x0, x1, y0, y1, _ = part_bbox[part]
        pos = [round(((x0 + x1) / 2 - RES / 2) * px_ui, 2), round((RES / 2 - (y0 + y1) / 2) * px_ui, 2)]
        layout['failure_indicators'].append(dict(name=f'{word} {tag}', anchoredPosition=pos, sizeDelta=[18.5, h],
                                                 localScale=[0.638, 0.853, 1], color=[1, 0, 0, 1], sprite=None,
                                                 note='plain red Image, inactive until StatusDisplay sees this failure message'))
with open(os.path.join(OUT, 'b25h_status_layout.json'), 'w') as fjs:
    json.dump(layout, fjs, indent=1)
written.append('b25h_status_layout.json')

# ------------------------------------------------------------------ 4. previews (composited like the game)
def composite(damage):
    """background + parts tinted by condition (1 = intact, invisible ... 0 = red), additive."""
    acc = np.dstack([box_down(edge.astype(F32), RES // 1024) * LINE] * 3)
    for e in layout['parts']:
        p = e['name']
        cond = damage.get(p, 1.0)
        a = 1 - cond
        if a <= 0:
            continue
        col = np.array([1, min(cond * 2, 1), 0], F32) * a
        m = box_down((part_ids == part_labels.index(p)).astype(F32), RES // 1024) * FILL
        acc += m[..., None] * col
    return np.clip(acc, 0, 1)


demo = {p: (0.0 if i % 5 == 0 else (0.45 if i % 3 == 0 else 1.0)) for i, p in enumerate(part_names)}
save_png(os.path.join(PDIR, 'status_damage_demo.png'), np.dstack([composite(demo), np.ones((1024, 1024), F32)]))
allp = {p: 0.3 for p in part_names}
save_png(os.path.join(PDIR, 'status_all_parts.png'), np.dstack([composite(allp), np.ones((1024, 1024), F32)]))
# part map with labels is in the json; icon preview tinted (friendly blue / hostile red) on a map-like ground
ic = icon[..., 3]
tile = []
for col in ((0.35, 0.65, 1.0), (1.0, 0.3, 0.25), (0.2, 1.0, 0.3)):
    bgc = np.zeros((ICON, ICON, 3), F32) + np.array([0.16, 0.2, 0.17], F32)
    tile.append(bgc * (1 - ic[..., None]) + np.array(col, F32) * ic[..., None])
save_png(os.path.join(PDIR, 'map_icon_tinted.png'), np.dstack([np.concatenate(tile, 1), np.ones((ICON, ICON * 3), F32)]))
print('[ui] DONE', len(written), 'files;', len(layout['parts']), 'part images,', len(layout['hidden_parts']), 'hidden parts')
