"""Release zip for NOMM / NOMNOM: HeritagePairs_<ver>.zip with the .nobp and B25H.Instruments.dll at its ROOT (no wrapper folder, no meta.json:
NOMM extracts the archive as it is into <id>/ and writes its own meta.json; nomm Installer.kt / LocalMods.kt, checked at 8786356).

  python tools/make_release_zip.py <frozen dir> <out dir> <version>

Deterministic: fixed entry order and timestamps, so the same two files give the same zip bytes. Prints and writes the sha256.
"""
import sys, os, zipfile, hashlib

fz, out, ver = sys.argv[1], sys.argv[2], sys.argv[3]
names = ['B25H.Instruments.dll', f'Heritage Pairs_{ver}.nobp']
os.makedirs(out, exist_ok=True)
zp = os.path.join(out, f'HeritagePairs_{ver}.zip')
with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for n in names:
        zi = zipfile.ZipInfo(n, date_time=(2026, 11, 13, 0, 0, 0))
        zi.compress_type = zipfile.ZIP_DEFLATED
        zi.external_attr = 0o644 << 16
        with open(os.path.join(fz, n), 'rb') as f:
            z.writestr(zi, f.read(), compresslevel=6)
h = hashlib.sha256(open(zp, 'rb').read()).hexdigest()
open(zp + '.sha256', 'w', newline='\n').write(f'{h} *{os.path.basename(zp)}\n')
print(zp, os.path.getsize(zp), 'sha256', h)
