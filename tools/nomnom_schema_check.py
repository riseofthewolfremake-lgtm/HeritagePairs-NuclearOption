"""Check a NOMNOM mod manifest against NOMNOM's ValidationSchema.json without PowerShell 7 (the repo's own Validate-JsonSchema.ps1 needs
Test-Json -Schema, which Windows PowerShell 5.1 does not have).

  python tools/nomnom_schema_check.py <manifest.json> <ValidationSchema.json>

Implements the JSON-Schema draft-07 keywords that schema uses: type, required, properties, items, enum, minLength, format uri.
Exit 0 = valid. This is a stand-in, not the project's validator: the pull request's GitHub workflow is the real check.
"""
import sys, json, re


def check(v, s, path, errs):
    t = s.get('type')
    ok = {'object': dict, 'array': list, 'string': str}.get(t)
    if ok and not isinstance(v, ok):
        errs.append(f'{path}: not a {t}'); return
    for r in s.get('required', []):
        if isinstance(v, dict) and r not in v:
            errs.append(f'{path}: missing {r}')
    if 'enum' in s and v not in s['enum']:
        errs.append(f'{path}: {v!r} not in {s["enum"]}')
    if 'minLength' in s and isinstance(v, str) and len(v) < s['minLength']:
        errs.append(f'{path}: shorter than {s["minLength"]}')
    if s.get('format') == 'uri' and isinstance(v, str) and not re.match(r'^[A-Za-z][A-Za-z0-9+.\-]*:\S+$', v):
        errs.append(f'{path}: not a URI')
    if isinstance(v, dict):
        for k, sub in s.get('properties', {}).items():
            if k in v:
                check(v[k], sub, f'{path}.{k}', errs)
    if isinstance(v, list) and 'items' in s:
        for i, x in enumerate(v):
            check(x, s['items'], f'{path}[{i}]', errs)


if __name__ == '__main__':
    m = json.load(open(sys.argv[1], encoding='utf-8-sig')); s = json.load(open(sys.argv[2], encoding='utf-8-sig'))
    errs = []
    check(m, s, '$', errs)
    for e in errs:
        print('INVALID', e)
    print('schema check:', 'VALID' if not errs else f'{len(errs)} errors')
    sys.exit(1 if errs else 0)
