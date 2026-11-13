"""Build the GA-25X cockpit panel-art atlas (0.3.2) from the fal-generated panel art (our own art, see assets/fal_manifest.jsonl).

  python blender/ga25x/textures/make_cockpit_art_ga25x.py [--out assets/textures_ga25x] [--preview <png>]

Writes ga25x_ckart_b.png (sRGB base colour) and ga25x_ckart_n.png (tangent-space normal map derived from a blurred luminance
height: raised switch bodies / knobs / bezels read as relief; strength kept low so labels stay flat). Layout: ga25x_ckart_layout.py.
Deterministic: same inputs -> same atlas.
"""
import os, sys
import numpy as np
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
import ga25x_ckart_layout as LY

ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
SRC = os.path.join(ROOT, 'assets', 'textures_ga25x', 'fal_raw_cockpit')


GLB = os.path.join(ROOT, 'assets', 'model_ga25x', 'src', 'throttle_gen', 'throttle_tripo_remesh.glb')


def extract_throttle_textures(out):
    """0.3.4: the split throttle handle is a fal-generated model (concept -> tripo3d/h3.1 image-to-3d -> tripo remesh, see
    assets/fal_manifest.jsonl). Write its baked base colour and normal map (from the GLB's own images) as ga25x_throttle_b/_n."""
    import json, struct, io
    d = open(GLB, 'rb').read()
    _, _, L = struct.unpack('<III', d[:12])
    off, chunks = 12, []
    while off < L:
        cl, ct = struct.unpack('<II', d[off:off + 8]); chunks.append(d[off + 8:off + 8 + cl]); off += 8 + cl
    js, bin_ = json.loads(chunks[0]), chunks[1]
    mat = js['materials'][0]
    def img(tex_index):
        im = js['images'][js['textures'][tex_index]['source']]
        bv = js['bufferViews'][im['bufferView']]
        o = bv.get('byteOffset', 0)
        return Image.open(io.BytesIO(bin_[o:o + bv['byteLength']]))
    img(mat['pbrMetallicRoughness']['baseColorTexture']['index']).convert('RGB').save(os.path.join(out, 'ga25x_throttle_b.png'))
    img(mat['normalTexture']['index']).convert('RGB').save(os.path.join(out, 'ga25x_throttle_n.png'))
    print('[ckart] throttle textures from', os.path.basename(GLB))


def measure_quadrant():
    """re-measure the quadrant gate art's slot opening and long scale ticks; fail if they moved from ga25x_ckart_layout.QG_*."""
    im = np.asarray(Image.open(os.path.join(SRC, 'v034', 'quadrant_gate.png')).convert('L')).astype(int)
    H, W = im.shape
    assert (W, H) == LY.QG_SIZE, (W, H)
    cy, cx = H // 2, W // 2

    def run(a, c, th=20):
        s_, e_ = c, c
        while s_ > 0 and a[s_ - 1] < th:
            s_ -= 1
        while e_ < len(a) - 1 and a[e_ + 1] < th:
            e_ += 1
        return s_, e_ + 1
    x0, x1 = run(im[cy], cx)
    r0, r1 = run(im[:, cx], cy)
    col = im[:, x0 - 100]
    rows = [r for r in range(H) if col[r] > 170]
    ticks, grp = [], []
    for r in rows:
        if grp and r - grp[-1] > 2:
            if len(grp) >= 3:
                ticks.append((grp[0] + grp[-1]) // 2)
            grp = []
        grp.append(r)
    if len(grp) >= 3:
        ticks.append((grp[0] + grp[-1]) // 2)
    meas = dict(slot=(x0, x1, r0, r1), ticks=ticks)
    exp_t = sorted(LY.QG_TICK_ROWS.values())
    ok = all(abs(a - b) <= 4 for a, b in zip((x0, x1, r0, r1), LY.QG_SLOT_PX)) and len(ticks) == 3 and all(abs(a - b) <= 4 for a, b in zip(ticks, exp_t))
    print('[ckart] quadrant art measured', meas, 'OK' if ok else 'MISMATCH vs layout', LY.QG_SLOT_PX, exp_t)
    if not ok:
        raise SystemExit('quadrant art landmarks moved: update ga25x_ckart_layout.QG_* (the cockpit UVs follow them)')
    return meas


def build(out, preview=None):
    measure_quadrant()
    extract_throttle_textures(out)
    A = LY.ATLAS
    base = Image.new('RGB', (A, A), (43, 45, 48))      # panel grey bleed
    for name, (rect, src, crop) in LY.PANELS.items():
        im = Image.open(os.path.join(SRC, src)).convert('RGB')
        if crop:
            im = im.crop(crop)
        x0, y0, x1, y1 = rect
        im = im.resize((x1 - x0, y1 - y0), Image.LANCZOS)
        if name == 'blank':
            # tile the plain riveted strip, then soften to a uniform plate
            im = im.filter(ImageFilter.GaussianBlur(1.0))
        base.paste(im, (x0, y0))
    # in-game look: the fal art is lit evenly and a bit bright; darken slightly toward the stock cockpit greys
    b = np.asarray(base).astype(np.float32) / 255.0
    b = np.clip(b * 0.92, 0, 1)
    Image.fromarray((b * 255 + 0.5).astype(np.uint8)).save(os.path.join(out, 'ga25x_ckart_b.png'), optimize=True)
    # normal map from luminance height (blurred), Sobel gradients
    lum = 0.299 * b[..., 0] + 0.587 * b[..., 1] + 0.114 * b[..., 2]
    h = np.asarray(Image.fromarray((lum * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2.2))).astype(np.float32) / 255.0
    gx = np.zeros_like(h); gy = np.zeros_like(h)
    gx[:, 1:-1] = (h[:, 2:] - h[:, :-2]) * 0.5
    gy[1:-1, :] = (h[2:, :] - h[:-2, :]) * 0.5
    k = 6.0
    nx, ny, nz = -gx * k, gy * k, np.ones_like(h)          # image row 0 = top -> +v is up: flip y gradient
    ln = np.sqrt(nx * nx + ny * ny + nz * nz)
    n = np.stack([nx / ln, ny / ln, nz / ln], -1) * 0.5 + 0.5
    Image.fromarray((n * 255 + 0.5).astype(np.uint8)).save(os.path.join(out, 'ga25x_ckart_n.png'), optimize=True)
    if preview:
        base.resize((1024, 1024)).save(preview)
    print('[ckart] wrote', os.path.join(out, 'ga25x_ckart_b.png'), 'and _n', A, 'px')


if __name__ == '__main__':
    a = sys.argv
    out = os.path.abspath(a[a.index('--out') + 1]) if '--out' in a else os.path.join(ROOT, 'assets', 'textures_ga25x')
    build(out, a[a.index('--preview') + 1] if '--preview' in a else None)
