r"""1.9.9 (MSB-17/80 -> MSB-17, key MSB1780 -> MSB17): scan a built pack (.nobp) for name and key strings, from the pack itself
(UnityPy; reads the pack only, writes nothing but the optional JSON summary).

  <venv>/python tools/pack_strings199.py <pack.nobp> [--json out.json]

Every object's raw serialized bytes are searched (UTF-8 and UTF-16) for
  * the old name:  '17/80', 'MSB 17'
  * the old key:   '1780' inside a text token (letters / digits / _ . / - around it, at least 3 more characters), which catches
                   MSB1780, msb1780_*, paths .../msb1780/... and anything else that spells it; bare 4-byte matches in binary data are
                   counted separately (old_key_raw) and not treated as text
and the strings that carry the new name ('MSB-17') and the new key ('MSB17') are listed and counted per object type.
Use the study venv: C:\Users\User\nuclearoption-ref\study\venv.
"""
import sys, json, re, collections
import UnityPy

OLD_NAME = [b'17/80', b'MSB 17', '17/80'.encode('utf-16-le'), 'MSB 17'.encode('utf-16-le')]
TOK = re.compile(rb'[A-Za-z0-9_./\\\- ]*1780[A-Za-z0-9_./\\\-]*')
TOK16 = re.compile(rb'(?:[A-Za-z_]\x00){2,}(?:[A-Za-z0-9_./ -]\x00)*1\x007\x008\x000\x00')     # UTF-16 text only: needs two letters before it (mesh index data also holds the bare byte pattern)
STR = re.compile(rb'[\x20-\x7e]{4,}')


def scan(p):
    env = UnityPy.load(p)
    old_name, old_key, new_name, key = [], collections.Counter(), collections.Counter(), collections.Counter()
    raw_key = 0
    for o in env.objects:
        raw = o.get_raw_data()
        t = o.type.name
        for pat in OLD_NAME:
            for m in re.finditer(re.escape(pat), raw):
                old_name.append((t, o.path_id, raw[max(0, m.start() - 24):m.end() + 24].decode('latin-1')))
        if b'1780' in raw:
            for m in TOK.finditer(raw):
                tok = m.group(0).decode('latin-1').strip()
                if len(tok) >= 7 and re.search(r'[A-Za-z_]', tok):
                    old_key[(t, tok[-80:])] += 1
                else:
                    raw_key += 1
        for m in TOK16.finditer(raw):
            old_key[(t, 'utf16:' + m.group(0).decode('utf-16-le', 'replace')[-60:])] += 1
        if b'MSB-17' in raw:
            for s in STR.findall(raw):
                if b'MSB-17' in s:
                    new_name[(t, s.decode('latin-1')[:90])] += 1
        if b'MSB17' in raw:
            key[t] += 1
    return old_name, old_key, raw_key, new_name, key


if __name__ == '__main__':
    a = sys.argv[1:]
    old_name, old_key, raw_key, new_name, key = scan(a[0])
    for t, pid, ctx in old_name:
        print(f'OLD NAME  {t} {pid}: {ctx!r}')
    for (t, s), n in sorted(old_key.items())[:60]:
        print(f'OLD KEY   {t} x{n}: {s!r}')
    for (t, s), n in sorted(new_name.items()):
        print(f'NAME      {t} x{n}: {s!r}')
    print(f'KEY MSB17 in objects by type: {dict(key)}')
    out = dict(pack=a[0].replace('\\', '/').split('/')[-1], old_name_hits=len(old_name), old_name=[list(x) for x in old_name[:40]],
               old_key_tokens=sum(old_key.values()), old_key_distinct=len(old_key), old_key_sample=[[t, s, n] for (t, s), n in sorted(old_key.items())[:40]],
               old_key_raw=raw_key, new_name_strings=[[t, s, n] for (t, s), n in sorted(new_name.items())], key_hits=dict(key))
    if '--json' in a:
        json.dump(out, open(a[a.index('--json') + 1], 'w'), indent=1)
    print(f'SUMMARY old_name_hits {len(old_name)}, old key text tokens {sum(old_key.values())} ({len(old_key)} distinct), bare 1780 byte matches in binary data {raw_key}, '
          f'distinct strings with MSB-17 {len(new_name)}, objects with the key MSB17 {sum(key.values())}')
    sys.exit(0)
