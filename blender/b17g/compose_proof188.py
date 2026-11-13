"""Compose the 1.8.8 B-17G proof sheets: for each view, REFERENCE on top and OURS below (same camera, same scale), labelled.

  python blender/b17g/compose_proof188.py <raw dir> <out dir> <tag> [suffix]      e.g.  ... raw_after sheets after _grey

Reads <view>_ref<suffix>.png and <view>_<tag><suffix>.png, writes <out>/<view>_<tag><suffix>.png. A 'before | after' sheet
(<view>_before_after<suffix>.png: ref / before / after) is written too when <raw>/../raw_before has the before image.
"""
import os, sys, glob
from PIL import Image, ImageDraw, ImageFont


def font(sz):
    for f in ('arialbd.ttf', 'arial.ttf', 'DejaVuSans-Bold.ttf'):
        try:
            return ImageFont.truetype(f, sz)
        except Exception:
            pass
    return ImageFont.load_default()


def label(im, text):
    d = ImageDraw.Draw(im)
    f = font(30)
    d.rectangle((0, 0, 14 + 17 * len(text), 44), fill=(0, 0, 0))
    d.text((8, 6), text, fill=(255, 230, 60), font=f)
    return im


def stack(imgs, labels, width=1600):
    ims = []
    for p, t in zip(imgs, labels):
        im = Image.open(p).convert('RGB')
        if im.width != width:
            im = im.resize((width, int(im.height * width / im.width)))
        ims.append(label(im, t))
    out = Image.new('RGB', (width, sum(i.height for i in ims) + 6 * (len(ims) - 1)), (255, 255, 255))
    y = 0
    for i in ims:
        out.paste(i, (0, y)); y += i.height + 6
    return out


def main():
    raw, out, tag = sys.argv[1], sys.argv[2], sys.argv[3]
    suf = sys.argv[4] if len(sys.argv) > 4 else ''
    os.makedirs(out, exist_ok=True)
    before_dir = os.path.join(os.path.dirname(os.path.abspath(raw)), 'raw_before')
    for rp in sorted(glob.glob(os.path.join(raw, f'*_ref{suf}.png'))):
        view = os.path.basename(rp)[:-len(f'_ref{suf}.png')]
        op = os.path.join(raw, f'{view}_{tag}{suf}.png')
        if not os.path.exists(op):
            continue
        kind = 'grey' if suf else 'textured'
        stack([rp, op], [f'REFERENCE (WT, visual ref only) - {view} - {kind}', f'OURS {tag} - {view} - {kind}']).save(os.path.join(out, f'{view}_{tag}{suf}.png'))
        bp = os.path.join(before_dir, f'{view}_before{suf}.png')
        if tag != 'before' and os.path.exists(bp):
            stack([rp, bp, op], [f'REFERENCE - {view} - {kind}', f'OURS 1.8.7 (before) - {view}', f'OURS {tag} - {view}']).save(
                os.path.join(out, f'{view}_before_after{suf}.png'))
        print('sheet', view)


if __name__ == '__main__':
    main()
