"""1.9.12: build, export and check the FD-32 airbrake add-on from the SHIPPED model (which is only read), and the two naval liveries.

  python blender/fd32/run_airbrake1912_fd32.py [--out <dir>] [--liveries] [--renders [<render dir>]]

Steps
  1. airbrake1912_fd32.py on assets/model_fd32/fd32.blend            -> <out>/fd32_airbrake.blend + fd32_airbrake.json
  2. export_fd32.py (the FD-32's own FBX exporter) on that .blend    -> <out>/fd32_airbrake.fbx + fd32_airbrake_parts.md / .json
  3. check_airbrake1912_fd32.py on the shipped model                 -> <out>/fd32_airbrake_check.json (exit 1 on a failed row)
  4. --liveries: build_textures_fd32.py --liveries-only bdf_navy,pala_navy on the shipped model: writes the two naval livery PNGs,
     merges them into fd32_liveries.json and the atlas manifest (nothing else in assets/textures_fd32 is written)
  5. --renders: every livery, panels shut / open, lit / flat, six views + close-ups (panel, fuselage shoulder, fin / rudder); the four
     1.9.11 liveries also WITHOUT the panels with the same cameras (1.9.11 look), contact sheets, and <dir>/fin_fullres: the rudder
     number of the naval liveries from both sides at 1600 px. Default render dir: nuclearoption-ref/study/v1912/fd32/renders
     (review material, not in git).
Default <out> = assets/model_fd32. fd32.blend / fd32.fbx are not written; their hashes are compared before and after.
"""
import os, sys, subprocess, hashlib, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run_fd32 as RF

ROOT, BLENDER = RF.ROOT, RF.BLENDER
MODEL = os.path.join(ROOT, 'assets', 'model_fd32')
TEX = os.path.join(ROOT, 'assets', 'textures_fd32')
RENDERS = r"C:\Users\User\nuclearoption-ref\study\v1912\fd32\renders"
NAVAL = 'bdf_navy,pala_navy'
OLD = 'bdf_mattegrey,bdf_temperate,pala_desert,pala_matteblack'


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()[:12]


def bl(args, keys=('[fd32-airbrake]', '[export]', '[check]', '[ftex]', '[render]', 'Error', 'Traceback')):
    print('>>', ' '.join(os.path.basename(a) for a in args[:4]), '...', flush=True)
    r = subprocess.run([BLENDER, '--background', '--python-exit-code', '1'] + args, capture_output=True, text=True)
    for line in (r.stdout + r.stderr).splitlines():
        if any(k in line for k in keys):
            print('   ', line[:400])
    if r.returncode:
        print((r.stdout + r.stderr)[-3000:])
        sys.exit(f'step failed: {os.path.basename(args[2]) if len(args) > 2 else args}')


def sheets(rdir):
    from PIL import Image
    tiles = json.load(open(os.path.join(rdir, 'tiles.json')))
    for k, fs in sorted(tiles.items()):
        ims = [Image.open(f).convert('RGB') for f in fs if os.path.exists(f)]
        if not ims:
            continue
        w, h = ims[0].size
        n = 4
        sheet = Image.new('RGB', (w * n, h * ((len(ims) + n - 1) // n)))
        for i, im in enumerate(ims):
            sheet.paste(im, ((i % n) * w, (i // n) * h))
        sheet.save(os.path.join(rdir, f'sheet_{k}.jpg'), quality=88)
    print('[airbrake] contact sheets', len(tiles), 'in', rdir)


def main():
    a = sys.argv[1:]
    out = os.path.abspath(a[a.index('--out') + 1]) if '--out' in a else MODEL
    os.makedirs(out, exist_ok=True)
    blend, fbx = os.path.join(MODEL, 'fd32.blend'), os.path.join(MODEL, 'fd32.fbx')
    before = (sha(blend), sha(fbx))
    bl([blend, '--python', os.path.join(HERE, 'airbrake1912_fd32.py'), '--', '--out', out])
    ab = os.path.join(out, 'fd32_airbrake.blend')
    bl([ab, '--python', os.path.join(HERE, 'export_fd32.py'), '--', '--fbx', os.path.join(out, 'fd32_airbrake.fbx'), '--table', os.path.join(out, 'fd32_airbrake_parts')])
    if '--liveries' in a:
        keep = {f: sha(os.path.join(TEX, f)) for f in os.listdir(TEX) if f.endswith('.png') and not f.endswith('_navy.png')}
        bl([blend, '--python', os.path.join(HERE, 'textures', 'build_textures_fd32.py'), '--', '--out', TEX, '--liveries-only', NAVAL])
        changed = [f for f, h in keep.items() if sha(os.path.join(TEX, f)) != h]
        if changed:
            sys.exit(f'liveries-only changed existing textures: {changed}')
        print(f'[airbrake] liveries-only: {len(keep)} existing PNGs in assets/textures_fd32 unchanged;', ', '.join(f'fd32_livery_{k}.png {sha(os.path.join(TEX, "fd32_livery_" + k + ".png"))}' for k in NAVAL.split(',')))
    bl([blend, '--python', os.path.join(HERE, 'check_airbrake1912_fd32.py'), '--', os.path.join(out, 'fd32_airbrake.json'), os.path.join(out, 'fd32_airbrake.fbx'),
        os.path.join(out, 'fd32_airbrake_check.json')])
    if (sha(blend), sha(fbx)) != before:
        sys.exit('the main model files changed during the run')
    print('[airbrake] main model untouched: fd32.blend', before[0], 'fd32.fbx', before[1])
    for f in ('fd32_airbrake.fbx', 'fd32_airbrake.json', 'fd32_airbrake.blend'):
        print('[airbrake]', f, sha(os.path.join(out, f)), os.path.getsize(os.path.join(out, f)), 'bytes')
    if '--renders' in a:
        i = a.index('--renders')
        rdir = os.path.abspath(a[i + 1]) if len(a) > i + 1 and not a[i + 1].startswith('--') else RENDERS
        tj = os.path.join(rdir, 'tiles.json')
        if os.path.exists(tj):
            os.remove(tj)
        bl([blend, '--python', os.path.join(HERE, 'render_airbrake1912_fd32.py'), '--', TEX, rdir])
        bl([blend, '--python', os.path.join(HERE, 'render_airbrake1912_fd32.py'), '--', TEX, rdir, '--no-panels', '--only', OLD])
        sheets(rdir)
        fdir = os.path.join(rdir, 'fin_fullres')          # round 2: the rudder number of the two naval liveries, both sides, 1600 px (about 5 px per texel)
        tj = os.path.join(fdir, 'tiles.json')
        if os.path.exists(tj):
            os.remove(tj)
        bl([blend, '--python', os.path.join(HERE, 'render_airbrake1912_fd32.py'), '--', TEX, fdir, '--only', NAVAL, '--views', 'finL,finR', '--res', '1600'])
        sheets(fdir)


if __name__ == '__main__':
    main()
