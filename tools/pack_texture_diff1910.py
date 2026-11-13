r"""1.9.10: list the textures that differ between two built packs (.nobp), from the packs themselves (UnityPy; reads only).

  <venv>/python tools/pack_texture_diff1910.py <old.nobp> <new.nobp> [--json out.json] [--expect name,name,...]

Every Texture2D is decoded and compared by name: size, format and the bytes of the decoded image. Prints the names that changed,
were added or were removed, and for a changed texture of equal size the bounding box and count of the pixels that differ.
With --expect: exit 1 unless the set of changed names is exactly that list and nothing was added or removed.
Use the study venv: C:\Users\User\nuclearoption-ref\study\venv.
"""
import sys, json, hashlib
import UnityPy
import numpy as np


def texes(p):
    out = {}
    for o in UnityPy.load(p).objects:
        if o.type.name == 'Texture2D':
            t = o.read()
            im = t.image
            n = t.m_Name
            assert n not in out or out[n][0] == hashlib.sha256(im.tobytes()).hexdigest(), 'duplicate texture name with different pixels: ' + n
            out[n] = (hashlib.sha256(im.tobytes()).hexdigest(), im.size, str(t.m_TextureFormat), im)
    return out


def main():
    old, new = texes(sys.argv[1]), texes(sys.argv[2])
    changed = sorted(n for n in old if n in new and old[n][:3] != new[n][:3])
    added = sorted(n for n in new if n not in old); removed = sorted(n for n in old if n not in new)
    rep = dict(old=len(old), new=len(new), changed=[], added=added, removed=removed)
    for n in changed:
        d = dict(name=n, size_old=old[n][1], size_new=new[n][1], format=new[n][2])
        if old[n][1] == new[n][1]:
            a, b = np.asarray(old[n][3].convert('RGBA')), np.asarray(new[n][3].convert('RGBA'))
            ch = np.argwhere((a != b).any(-1))
            d.update(pixels=int(len(ch)), bbox=[int(ch[:, 1].min()), int(ch[:, 0].min()), int(ch[:, 1].max()), int(ch[:, 0].max())])
        rep['changed'].append(d)
    print(f'textures: old {len(old)}, new {len(new)}; changed {len(changed)}, added {len(added)}, removed {len(removed)}')
    for d in rep['changed']:
        print('  CHANGED', d)
    for n in added: print('  ADDED', n)
    for n in removed: print('  REMOVED', n)
    if '--json' in sys.argv:
        json.dump(rep, open(sys.argv[sys.argv.index('--json') + 1], 'w'), indent=1)
    if '--expect' in sys.argv:
        want = sorted(x for x in sys.argv[sys.argv.index('--expect') + 1].split(',') if x)
        ok = changed == want and not added and not removed
        print('EXPECT', 'OK' if ok else f'FAIL (wanted {want})')
        sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
