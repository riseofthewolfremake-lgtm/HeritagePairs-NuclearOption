"""Build the B-25H cockpit art (cockpit rebuild 2026-11-01) from the fal-generated art (our own; assets/fal_manifest.jsonl).

  python blender/v2/textures/make_cockpit_art_b25h.py [--out assets/textures_v2] [--preview <png>]

Writes:
  b25h_ckart_b / _n   4096^2 atlas of the panel, boxes, pedestal face, placards, retrofit bezel (layout b25h_cockpit_layout.py)
  b25h_quilt_b / _n   tiling quilted sound-proofing (fal-ai/z-image/turbo/tiling)
  b25h_od_b / _n      tiling olive-drab painted metal (same)
  b25h_pr_<name>_b/_n each fal 3D prop's own baked base colour + normal map (from its remeshed GLB)
Re-measures the art landmarks the cockpit UVs follow (pedestal slots, bezel opening) and fails if they moved.
"""
import os, sys, io, json, struct, glob
import numpy as np
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
import b25h_cockpit_layout as LY

ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
SRC = os.path.join(ROOT, 'assets', 'textures_v2', 'fal_raw_cockpit_b25h')
PROPS = os.path.join(ROOT, 'assets', 'model_v2', 'src', 'props_gen')


PROP_TEX = 1024


def normal_from(img, k=6.0, blur=2.2):
    b = np.asarray(img.convert('RGB')).astype(np.float32) / 255.0
    lum = 0.299 * b[..., 0] + 0.587 * b[..., 1] + 0.114 * b[..., 2]
    h = np.asarray(Image.fromarray((lum * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(blur))).astype(np.float32) / 255.0
    gx = np.zeros_like(h); gy = np.zeros_like(h)
    gx[:, 1:-1] = (h[:, 2:] - h[:, :-2]) * 0.5
    gy[1:-1, :] = (h[2:, :] - h[:-2, :]) * 0.5
    nx, ny, nz = -gx * k, gy * k, np.ones_like(h)
    ln = np.sqrt(nx * nx + ny * ny + nz * nz)
    n = np.stack([nx / ln, ny / ln, nz / ln], -1) * 0.5 + 0.5
    return Image.fromarray((n * 255 + 0.5).astype(np.uint8))


def measure():
    im = np.asarray(Image.open(os.path.join(SRC, 'pedestal_face.png')).convert('L')).astype(int)
    H, W = im.shape
    assert (W, H) == LY.PED_SIZE
    row = im[H // 2] < 30
    runs, s = [], None
    for x in range(W):
        if row[x] and s is None:
            s = x
        if not row[x] and s is not None:
            if x - s > 8:
                runs.append((s + x) / 2 / W)
            s = None
    runs = runs[:6]
    ok = len(runs) == 6 and all(abs(a - b) * W <= 4 for a, b in zip(runs, LY.PED_SLOT_U))
    im = np.asarray(Image.open(os.path.join(SRC, 'retrofit_bezel.png')).convert('L')).astype(int)
    H, W = im.shape
    cy, cx = H // 2, W // 2

    def run(a, c, th=18):
        s_, e_ = c, c
        while s_ > 0 and a[s_ - 1] < th:
            s_ -= 1
        while e_ < len(a) - 1 and a[e_ + 1] < th:
            e_ += 1
        return s_, e_
    bx, by = run(im[cy], cx), run(im[:, cx], cy)
    exp = LY.BEZEL_OPEN
    ok2 = abs(bx[0] / W - exp[0]) * W <= 4 and abs(bx[1] / W - exp[2]) * W <= 4 and abs((1 - by[1] / H) - exp[1]) * H <= 4
    print('[b25h art] pedestal slots', [round(r, 4) for r in runs], 'bezel opening', bx, by, 'OK' if ok and ok2 else 'MISMATCH')
    if not (ok and ok2):
        raise SystemExit('art landmarks moved: update b25h_cockpit_layout PED_* / BEZEL_OPEN')


def measure_panel():
    """refit the v3 panel art (dark dial holes under the 16 real dials) and compare with LY.PF_*: fail on > 4 px drift."""
    im = np.asarray(Image.open(os.path.join(SRC, LY.PANELS['panel'][1])).convert('L')).astype(int)
    H, W = im.shape
    assert (W, H) == LY.PANEL_SRC_SIZE, (W, H)
    A, B = [], []
    for g, x, z, r in LY.REAL:
        u, v = LY.PF_A * x + LY.PF_B, LY.PF_C * z + LY.PF_D
        rp = r * LY.PF_A
        for _ in range(4):
            R = int(rp * 1.3)
            ys, xs = np.mgrid[int(v - R):int(v + R), int(u - R):int(u + R)]
            ys = np.clip(ys, 0, H - 1); xs = np.clip(xs, 0, W - 1)
            m = im[ys, xs] < 24
            u, v = xs[m].mean(), ys[m].mean()
        A.append((x, z)); B.append((u, v))
    A, B = np.array(A), np.array(B)
    px, pz = np.polyfit(A[:, 0], B[:, 0], 1), np.polyfit(A[:, 1], B[:, 1], 1)
    res = np.hypot(np.polyval(px, A[:, 0]) - B[:, 0], np.polyval(pz, A[:, 1]) - B[:, 1])
    drift = max(abs(np.polyval(px, x) - (LY.PF_A * x + LY.PF_B)) for x in (LY.PANEL_RECT[0], LY.PANEL_RECT[1]))
    drift = max(drift, max(abs(np.polyval(pz, z) - (LY.PF_C * z + LY.PF_D)) for z in (LY.PANEL_RECT[2], LY.PANEL_RECT[3])))
    print(f'[b25h art] panel fit u={px[0]:.2f}x+{px[1]:.2f} v={pz[0]:.2f}z+{pz[1]:.2f}, residual max {res.max():.1f} px, drift {drift:.1f} px')
    if drift > 4 or res.max() > 14:
        raise SystemExit('panel art landmarks moved: update b25h_cockpit_layout PF_*')


def glb_images(path):
    d = open(path, 'rb').read()
    L = struct.unpack('<III', d[:12])[2]
    off, ch = 12, []
    while off < L:
        cl, ct = struct.unpack('<II', d[off:off + 8]); ch.append(d[off + 8:off + 8 + cl]); off += 8 + cl
    js, bn = json.loads(ch[0]), ch[1]
    mat = js['materials'][0]

    def img(ti):
        im = js['images'][js['textures'][ti]['source']]
        bv = js['bufferViews'][im['bufferView']]
        o = bv.get('byteOffset', 0)
        return Image.open(io.BytesIO(bn[o:o + bv['byteLength']])).convert('RGB')
    return img(mat['pbrMetallicRoughness']['baseColorTexture']['index']), img(mat['normalTexture']['index'])


def build(out, preview=None):
    measure()
    measure_panel()
    A = LY.ATLAS
    base = Image.new('RGB', (A, A), (22, 22, 24))
    for name, (rect, src, crop) in LY.PANELS.items():
        im = Image.open(os.path.join(SRC, src)).convert('RGB')
        if crop:
            w_, h_ = im.size
            im = im.crop((int(crop[0] * w_), int(crop[1] * h_), int(crop[2] * w_), int(crop[3] * h_)))
        x0, y0, x1, y1 = rect
        base.paste(im.resize((x1 - x0, y1 - y0), Image.LANCZOS), (x0, y0))
    base.save(os.path.join(out, 'b25h_ckart_b.png'), optimize=True)
    normal_from(base).save(os.path.join(out, 'b25h_ckart_n.png'), optimize=True)
    for src, dst in (('v3/quilt_od_v3.png', 'b25h_quilt'), ('od_metal.png', 'b25h_od')):
        im = Image.open(os.path.join(SRC, src)).convert('RGB')
        # v3 tone: darker olive / khaki as the photos (multiply, slight green shift); pass 1 read too pale next to the photos
        a_ = np.asarray(im).astype(np.float32)
        a_ = a_ * (np.array([0.62, 0.66, 0.55], np.float32) if 'quilt' in src else np.array([0.66, 0.70, 0.52], np.float32))
        im = Image.fromarray(np.clip(a_, 0, 255).astype(np.uint8))
        im.save(os.path.join(out, dst + '_b.png'))
        normal_from(im, k=8.0 if 'quilt' in src else 2.0, blur=3.0).save(os.path.join(out, dst + '_n.png'))
    for g in sorted(glob.glob(os.path.join(PROPS, '*_remesh.glb')) + glob.glob(os.path.join(PROPS, '*_dec.glb'))):
        n = os.path.basename(g).rsplit('_', 1)[0]
        b, nm = glb_images(g)
        # performance pass: prop textures at 1K (props are 0.1-1 m; 2K was ~5 texels / mm at arm's length)
        b = b.resize((PROP_TEX, PROP_TEX), Image.LANCZOS) if b.size[0] > PROP_TEX else b
        nm = nm.resize((PROP_TEX, PROP_TEX), Image.LANCZOS) if nm.size[0] > PROP_TEX else nm
        b.save(os.path.join(out, f'b25h_pr_{n}_b.png')); nm.save(os.path.join(out, f'b25h_pr_{n}_n.png'))
        print('[b25h art] prop textures', n)
    if preview:
        base.resize((1024, 1024)).save(preview)
    print('[b25h art] wrote atlas + tiles into', out)


if __name__ == '__main__':
    a = sys.argv
    out = os.path.abspath(a[a.index('--out') + 1]) if '--out' in a else os.path.join(ROOT, 'assets', 'textures_v2')
    build(out, a[a.index('--preview') + 1] if '--preview' in a else None)
