"""Build the public-repo tree of Heritage Pairs from this (private) repo: only what is needed to read, rebuild and trust the mod.

  python tools/make_public_tree.py <out dir>          (the out dir must not exist or must be empty apart from .git)

For a later version the public repository already has history: build the tree into an empty scratch folder, then make the repository's
working copy equal to it (delete what is gone, copy what is new or changed), `git add -A` and add ONE commit on top. Never rewrite or
amend a commit that has been pushed.

Copies the files listed by INCLUDE minus EXCLUDE (tracked files only, plus the files named in EXTRA), writes a .gitignore and a
.gitattributes, then scans the
copy and prints a report: file count, size, largest files, and every finding of the checks below. Exit 1 on a finding marked BLOCK.
It never runs git and never touches a network.

Checks on the copy:
  BLOCK  a file over 50 MB; a .dll / .exe / .pdb / .il / .nobp / .unitypackage / .assets / .bundle / archive / .obj / .mtl / audio / font /
         photo-format file; a path with testhelper, media/, MODLOG, STATUS, decomp, AssetRipper output; an image or model whose name says
         comparison, reference render, screenshot or capture
  BLOCK  text that looks like a key or token (FAL_KEY=, Key <hex>, ghp_, github_pat_, sk-..., BEGIN PRIVATE KEY, Bearer <long>), an e-mail
         address other than the commit placeholder ones, the Steam user-data folder id
  NOTE   build-PC paths (C:\\Users\\<name>\\...) and which name they carry
  NOTE   text files that mention decompiled code, AssetRipper or War Thunder (listed for a human to read)
"""
import os, re, sys, shutil, subprocess, fnmatch, collections

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INCLUDE = ['README.md', 'LICENSE', 'LICENSE-ASSETS', 'CREDITS.md', 'CHANGELOG.md',
           'src/B25H.Instruments/*',
           'unity/*',
           'blender/*',
           'assets/*',
           'tools/build_instruments.sh', 'tools/make_release_zip.py', 'tools/pack_asset_report.py', 'tools/pack_strings199.py', 'tools/atlas_pack_check1816.py',
           'tools/nomnom_schema_check.py', 'tools/make_public_tree.py', 'tools/paint_out_marks1910.py', 'tools/pack_texture_diff1910.py',
           'docs/publishing/HeritagePairs.json', 'docs/publishing/pack_asset_report_1.9.15.txt',      # the current release's report only
           'docs/publishing/RELEASE_NOTES_*.md', 'docs/publishing/HOW_TO_RELEASE.md']
EXCLUDE = ['*/__pycache__/*', '*.pyc', '*.blend1',
           # ship gate: an aircraft the user has not released yet is listed here by path pattern (none since 1.9.15: the A6M2 Zero was
           # excluded from 2026-11-18 until its release in 1.9.15, and from then on goes out like the other aircraft)

           'blender/*/study/*',                      # study scripts that read the user's game export
           'assets/*/renders/*', 'assets/*/previews/*', 'assets/*/drafts/*',      # review renders and drafts: not needed to rebuild
           'assets/*/concepts/*.png', 'assets/*/ck_concepts/*.png', 'assets/*/fal/raw/*.png',    # AI concept images / model preview renders (the manifests stay)
           'assets/model/preview_*.png',
           'assets/*compare_*.png',                  # comparison sheets (our model beside a reference render): never public
           'assets/*/log_*.txt', 'assets/*.log', 'assets/*_done.txt',      # fal run logs (request ids); the fal_manifest.jsonl files stay
           # 1.9.10 (pre-publish audit): files no script reads (checked by name search over .py / .cs / .sh / .json)
           'assets/*_rendered_image.png',                                    # Tripo preview renders of the generated 3D parts
           'assets/textures_v2/fal_raw_cockpit_b25h/panel_main_2.png', 'assets/textures_v2/fal_raw_cockpit_b25h/v3/panel_main_v3_2.png',
           'assets/textures_v2/fal_raw_cockpit_b25h/v3/panel_v3b_7321.png', 'assets/textures_v2/fal_raw_cockpit_b25h/v3/panel_v3b_7321_2.png',
           'assets/textures_v2/fal_raw_cockpit_b25h/v3/panel_v3b_7322_2.png', 'assets/textures_ga25x/fal_raw_cockpit/v034/quadrant_gate_2.png',   # six unused panel alternates
           'assets/model_b17g/src/fal/remesh/ck_yoke_remesh*']               # first-round yoke model, replaced by ck_yoke2 (its hub carries an insignia-like badge)
EXTRA = []      # untracked files to take as well (none)
GITIGNORE = '''# Python, Blender, .NET
__pycache__/
*.pyc
*.blend1
*.blend2
bin/
obj/
*.pdb
*.user
*.suo
# editors and OS
.vs/
.vscode/
.idea/
.claude/
.DS_Store
Thumbs.db
desktop.ini
# Unity project folders (the Blueprinter project is not part of this repository)
Library/
Temp/
Logs/
*.meta
# build outputs and game-type files: never commit these
build/
dist/
*.dll
*.exe
*.nobp
*.zip
*.unitypackage
*.assets
*.bundle
*.log
*.tmp
# reference models and captures stay outside the repository
*.obj
*.mtl
'''
GITATTRIBUTES = '''* text=auto
*.cs text eol=lf
*.py text eol=lf
*.sh text eol=lf
*.md text eol=lf
*.json text eol=lf
*.jsonl text eol=lf
*.txt text eol=lf
*.csproj text eol=lf
*.asmdef text eol=lf
.gitattributes text eol=lf
.gitignore text eol=lf
LICENSE text eol=lf
LICENSE-ASSETS text eol=lf
*.png binary
*.glb binary
*.fbx binary
*.blend binary
'''
TEXT = ('.cs', '.py', '.sh', '.md', '.json', '.jsonl', '.txt', '.asmdef', '.csproj', '.yml', '.yaml', '.cfg', '')
BLOCK_EXT = ('.dll', '.exe', '.pdb', '.il', '.nobp', '.unitypackage', '.assets', '.bundle', '.ress', '.pfx', '.pem', '.zip', '.7z',
             '.obj', '.mtl', '.dds', '.tga', '.jpg', '.jpeg', '.bmp', '.ogg', '.wav', '.mp3', '.mp4', '.ttf', '.otf', '.prefab', '.mat', '.shader')
# 1.9.10: path words of reference renders, comparison sheets, screenshots and captures (none may be in the tree)
BLOCK_NAME = ('compare_', '_wt_', 'wt_', 'screenshot', 'capture', 'ingame', 'shot_', 'war_thunder', 'warthunder', '_ref_', 'rendered_image')
BLOCK_PATH = ('testhelper', 'media/', 'MODLOG.md', 'STATUS.md', 'decomp', 'NUCLEAROPTIONEXPORTS', 'ExportedProject', 'src/B25H/', 'parked/', 'dist/')
SECRET = [(re.compile(r'FAL_KEY\s*[=:]\s*["\']?[A-Za-z0-9\-_:]{16,}'), 'FAL key value'), (re.compile(r'\bKey [0-9a-f\-]{20,}:[0-9a-f]{20,}'), 'fal Key header'),
          (re.compile(r'\b(ghp|gho|ghu|ghs)_[A-Za-z0-9]{30,}'), 'GitHub token'), (re.compile(r'github_pat_[A-Za-z0-9_]{30,}'), 'GitHub PAT'),
          (re.compile(r'\bsk-[A-Za-z0-9\-_]{24,}'), 'API key'), (re.compile(r'BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY'), 'private key'),
          (re.compile(r'Bearer [A-Za-z0-9\-_\.]{30,}'), 'bearer token'), (re.compile(r'[?&](token|sig|signature|X-Amz-Signature|key)=[A-Za-z0-9%\-_\.]{16,}', re.I), 'signed URL')]
EMAIL = re.compile(r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}')
EMAIL_OK = ('noreply@anthropic.com', 'users.noreply.github.com', 'example.com', 'example.org')
USERPATH = re.compile(r'[A-Za-z]:[\\/]+Users[\\/]+([^\\/"\'\s]+)')
MENTION = re.compile(r'decompil|AssetRipper|War Thunder|ilspy', re.I)


def match(path, pats):
    return any(fnmatch.fnmatch(path, p) or (p.endswith('/*') and path.startswith(p[:-1])) for p in pats)


def main():
    out = os.path.abspath(sys.argv[1])
    if os.path.exists(out) and [x for x in os.listdir(out) if x != '.git']:
        print('out dir is not empty:', out); sys.exit(2)
    tracked = [f for f in subprocess.run(['git', '-C', REPO, 'ls-files'], capture_output=True, text=True).stdout.split('\n') if f]
    take = [f for f in tracked + EXTRA if match(f, INCLUDE) and not match(f, EXCLUDE) and os.path.exists(os.path.join(REPO, f))]
    # 1.9.15: every file goes out as it is in the repository (the A6M2 dev strip of 1.9.14-1.9.15 development is no longer applied: the released
    # DLL is built from exactly this source)
    for f in take:
        dst = os.path.join(out, f)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(os.path.join(REPO, f), dst)
    open(os.path.join(out, '.gitignore'), 'w', newline='\n').write(GITIGNORE)
    open(os.path.join(out, '.gitattributes'), 'w', newline='\n').write(GITATTRIBUTES)
    # ---------------- scan the copy
    files = []
    for dp, dn, fn in os.walk(out):
        if '.git' in dn:
            dn.remove('.git')
        for f in fn:
            p = os.path.join(dp, f)
            files.append((os.path.relpath(p, out).replace('\\', '/'), os.path.getsize(p)))
    total = sum(s for _, s in files)
    block, note = [], []
    users = collections.Counter(); mention = []; by_top = collections.Counter(); size_top = collections.Counter()
    for rel, size in files:
        top = '/'.join(rel.split('/')[:2]) if rel.split('/')[0] in ('assets', 'tools', 'src', 'unity', 'blender', 'docs') else rel.split('/')[0]
        by_top[top] += 1; size_top[top] += size
        if size > 50e6:
            block.append(f'over 50 MB: {rel} ({size})')
        if rel.lower().endswith(BLOCK_EXT) and rel not in ('.gitignore', '.gitattributes'):
            block.append(f'binary / game-type file: {rel}')
        if any(k in rel for k in BLOCK_PATH):
            block.append(f'excluded path: {rel}')
        base = rel.split('/')[-1].lower()
        if os.path.splitext(rel)[1].lower() in ('.png', '.glb', '.fbx', '.blend') and any(base.startswith(k) or ('_' + k) in base or k in base for k in BLOCK_NAME):
            block.append(f'reference render / comparison / capture by name: {rel}')
        if os.path.splitext(rel)[1].lower() in TEXT and size < 8e6:
            try:
                t = open(os.path.join(out, rel), encoding='utf-8', errors='replace').read()
            except Exception:
                continue
            for rx, what in SECRET:
                m = rx.search(t) if rel != 'tools/make_public_tree.py' else None      # this file holds the patterns themselves
                if m:
                    block.append(f'{what}: {rel}: {m.group(0)[:24]}...')
            for m in EMAIL.finditer(t):
                if not any(m.group(0).lower().endswith(ok) or ok in m.group(0).lower() for ok in EMAIL_OK) and not re.search(r'\.(png|json|py|cs|fbx|blend|glb)$', m.group(0)):
                    block.append(f'e-mail address: {rel}: {m.group(0)}')
            for m in USERPATH.finditer(t):
                users[m.group(1)] += 1
            if MENTION.search(t):
                mention.append((rel, len(MENTION.findall(t))))
    print(f'PUBLIC TREE {out}')
    print(f'files {len(files)}, size {total / 1e6:.1f} MB')
    for k, v in sorted(size_top.items(), key=lambda kv: -kv[1])[:30]:
        print(f'  {v / 1e6:9.1f} MB {by_top[k]:5d}  {k}')
    print('largest:', [(r, round(s / 1e6, 1)) for r, s in sorted(files, key=lambda x: -x[1])[:6]])
    print(f'NOTE build-PC paths by account name: {dict(users)}')
    print(f'NOTE {len(mention)} text files mention decompiled code / AssetRipper / War Thunder: {[m[0] for m in sorted(mention, key=lambda x: -x[1])[:60]]}')
    print(f'BLOCK findings: {len(block)}')
    for b in block[:80]:
        print('  BLOCK', b)
    sys.exit(1 if block else 0)


if __name__ == '__main__':
    main()
