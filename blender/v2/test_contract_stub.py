"""Offline stub test of the B-25H v2 build contract (plain Python, no Blender, no Unity).

  python blender/v2/test_contract_stub.py [assets/model_v2]

Re-implements the few lines of the stock drivers that matter (decompiled Assembly-CSharp, see the contract notes)
on Unity numbers and checks every sign / axis / range claim in b25h_v2_contract.json against the probe points
measured on the real mesh:
  ControlSurface      rest * AngleAxis(pitch*pitchRange + roll*rollRange + yaw*yawRange, right)
  Cockpit.Throttle    localEulerAngles = (throttle * range, 0, 0)
  Turret              localEulerAngles: az (0, t, 0), el (e, 0, 0); e clamped to [-maxElevation, -minElevation]
  Canopy.CanopyHinge  localEulerAngles = right * hingeAngle * open
plus structural checks (names, parents, hardpoints on pylons, gauge ranges, crew). Includes negative tests that
flip a sign and expect the check to fail, so the harness cannot pass vacuously. Exit code 1 on any failure.
"""
import json, math, os, sys

D = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), '..', '..', 'assets', 'model_v2')
con = json.load(open(os.path.join(D, 'b25h_v2_contract.json')))
parts = {r['name']: r for r in json.load(open(os.path.join(D, 'b25h_v2_parts.json')))}
fails = []
n = [0]


def ok(name, cond, detail=''):
    n[0] += 1
    print(('PASS ' if cond else 'FAIL ') + name + (f' : {detail}' if detail else ''))
    if not cond:
        fails.append(name)


# ---------------------------------------------------------------- Unity math (numbers identical to UnityEngine)
def norm(v):
    l = math.sqrt(sum(c * c for c in v))
    return [c / l for c in v]


def angle_axis(deg, axis, v):
    """Quaternion.AngleAxis(deg, axis) * v  (Rodrigues; Unity uses the same numbers)."""
    k = norm(axis)
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    kv = sum(x * y for x, y in zip(k, v))
    kxv = [k[1] * v[2] - k[2] * v[1], k[2] * v[0] - k[0] * v[2], k[0] * v[1] - k[1] * v[0]]
    return [v[i] * c + kxv[i] * s + k[i] * kv * (1 - c) for i in range(3)]


def rot_about(pivot, axis, deg, p):
    r = angle_axis(deg, axis, [p[i] - pivot[i] for i in range(3)])
    return [pivot[i] + r[i] for i in range(3)]


def sub(a, b):
    return [x - y for x, y in zip(a, b)]


assert all(abs(a - b) < 1e-9 for a, b in zip(angle_axis(90, [1, 0, 0], [0, 1, 0]), [0, 0, 1])), 'AngleAxis(90,X)*Y must be +Z'

# ---------------------------------------------------------------- structure
names = set(parts)
for sec in ('controls', 'gauges', 'mfds', 'turrets', 'crew', 'hatches', 'prop_discs', 'hardpoints', 'breaks'):
    ok(f'contract section {sec} present', sec in con)


def all_objs(x, acc):
    if isinstance(x, dict):
        if 'name' in x and 'pivot' in x and 'local_axes' in x:
            acc.append(x)
        for v in x.values():
            all_objs(v, acc)
    elif isinstance(x, list):
        for v in x:
            all_objs(v, acc)
    return acc


objs = all_objs(con, [])
missing = sorted({o['name'] for o in objs if o['name'] not in names})
ok('every contract object exists in the parts table', not missing, str(missing[:8]))
badp = sorted({o['name'] for o in objs if o['parent'] and o['parent'] not in names})
ok('every contract parent exists in the parts table', not badp, str(badp[:8]))
diff = [o['name'] for o in objs if any(abs(a - b) > 1e-3 for a, b in zip(o['pivot'], parts[o['name']]['pivot_unity']))]
ok('contract pivots equal the parts table pivots', not diff, str(diff[:5]))
for r in con['renames']:
    ok(f"rename {r['old']} -> {r['new']}: old name gone, new present", r['old'] not in names and r['new'] in names)


# ---------------------------------------------------------------- controls (ControlSurface)
def control_checks(sign_flip=1.0, quiet=False):
    res = []
    for c in con['controls']['objects']:
        ax, piv, pr = c['local_axes']['x'], c['pivot'], c['probe']
        val = c['drive']['value'] * sign_flip
        p1 = rot_about(piv, ax, val * 1.0, pr)          # input = +1 (pitch pull / roll right / yaw right)
        d = sub(p1, pr)
        if 'column' in c['name']:
            res.append((f"{c['name']}: pitch +1 (pull) moves the column top AFT", d[2] < -0.01, f'dz {d[2]:+.3f}'))
        elif 'yoke' in c['name']:
            res.append((f"{c['name']}: roll +1 (right) turns the wheel top RIGHT", d[0] > 0.01, f'dx {d[0]:+.3f}'))
        else:
            res.append((f"{c['name']}: yaw +1 (right rudder) moves the right pedal FORWARD", d[2] > 0.005, f'dz {d[2]:+.3f}'))
    return res


for name, cond, det in control_checks():
    ok(name, cond, det)
neg = control_checks(-1.0)
ok('negative test: flipped control signs are caught', all(not c for _, c, _ in neg))
for c in con['controls']['objects']:
    ax = c['local_axes']['x']
    want = {'column': [1, 0, 0], 'yoke': None, 'pedals': [0, 1, 0]}
    k = 'column' if 'column' in c['name'] else ('yoke' if 'yoke' in c['name'] else 'pedals')
    if want[k]:
        ok(f"{c['name']} driver axis is {want[k]}", all(abs(a - b) < 1e-3 for a, b in zip(ax, want[k])), str(ax))
    else:
        ok(f"{c['name']} hub axis points aft toward the pilot", ax[2] < -0.9, str(ax))

# ---------------------------------------------------------------- gauges (Cockpit.Throttle-style X rotation)
for g in con['gauges']['movers']:
    if g.get('kind') == 'gauge_card':
        continue
    piv, tip, ax = g['pivot'], g['probe'], g['local_axes']['x']
    r = sub(tip, piv)
    kx = sum(a * b for a, b in zip(r, ax))
    up = norm([r[i] - ax[i] * kx for i in range(3)])            # in the dial plane (drop the stand-off along local X)
    ok(f"{g['name']}: rests at 12 o'clock (tip along local +Y)", sum(a * b for a, b in zip(up, g['local_axes']['y'])) > 0.995)
    p1 = rot_about(piv, ax, 30.0, tip)
    ok(f"{g['name']}: +30 deg moves the tip clockwise (to the pilot's right)", p1[0] - tip[0] > 0.005, f'dx {p1[0] - tip[0]:+.4f}')
    if 'sweep' in g:
        ok(f"{g['name']}: deg_per_unit * span == sweep <= 360", abs(g['deg_per_unit'] * (g['v1'] - g['v0']) - g['sweep']) < 0.05 and g['sweep'] <= 360)
    if g['stock_driver']:
        ok(f"{g['name']}: throttle driver range inside the dial sweep", 0 < g['stock_driver']['range'] <= g['sweep'])

# ---------------------------------------------------------------- throttle levers (Cockpit.Throttle X rotation)
mfd_c = next(m for m in con['mfds'] if m['name'] == 'mfd_center')
for g in con.get('levers', {}).get('movers', []):
    piv, tip, ax = g['pivot'], g['probe'], g['local_axes']['x']
    ok(f"{g['name']}: driver axis is lateral (+X right)", ax[0] > 0.999, str(ax))
    p1 = rot_about(piv, ax, g['stock_driver']['range'], tip)
    ok(f"{g['name']}: full throttle moves the lever top forward", p1[2] - tip[2] > 0.03, f'dz {p1[2] - tip[2]:+.4f}')
    ok(f"{g['name']}: idle leans aft, full throttle leans forward", tip[2] < piv[2] - 0.02 and p1[2] > piv[2] + 0.02,
       f'idle dz {tip[2] - piv[2]:+.3f}, full dz {p1[2] - piv[2]:+.3f}')
    # 2026-11-01 v3: the quadrant now sits on a tall pedestal right under the panel (photos 44 / 47), so the old rule "lever top
    # below the screen's lower edge" is replaced by what it protected: from the pilot's eye, the sight line to the centre screen's
    # lower edge passes above the lever top at idle and at full throttle
    eye = [s_ for s_ in con['crew']['stations'] if s_['role'] == 'pilot'][0]['eye']['pivot']
    cs = mfd_c['corners']
    lo2 = sorted(cs, key=lambda c: c[1])[:2]
    bot = [(lo2[0][k] + lo2[1][k]) / 2 for k in range(3)]
    def clear(t):
        f = (t[2] - eye[2]) / (bot[2] - eye[2])
        return eye[1] + (bot[1] - eye[1]) * f - t[1]
    cl = min(clear(tip), clear(p1))
    ok(f"{g['name']}: lever top stays under the pilot's sight line to the centre screen's lower edge", cl > 0.01, f'clearance {cl * 1000:.0f} mm')

# ---------------------------------------------------------------- MFDs
for m in con['mfds']:
    w, h = m['size_m']
    c = m['corners']
    ok(f"{m['name']}: 4 corners, size {w} x {h} m", len(c) == 4 and 0.12 <= w <= 0.40 and 0.10 <= h <= 0.30)
    ok(f"{m['name']}: faces the crew (normal toward -Z)", m['normal_unity'][2] < -0.9)

# ---------------------------------------------------------------- turrets (Turret.cs absolute euler)
for t in con['turrets']['turrets']:
    T = t['Turret']
    az, el = t['az'], t['el']
    ok(f"{az['name']}: az axis (local +Y) is up", az['local_axes']['y'][1] > 0.99, str(az['local_axes']['y']))
    ok(f"{az['name']}/{el['name']}: rest frames equal the mount frame (identity under the mount)",
       all(all(abs(a - b) < 1e-3 for a, b in zip(az['local_axes'][k], t['mount']['local_axes'][k])) and
           all(abs(a - b) < 1e-3 for a, b in zip(el['local_axes'][k], t['mount']['local_axes'][k])) for k in 'xyz'))
    mz = t['probe_muzzle']
    up_e = rot_about(el['pivot'], el['local_axes']['x'], -T['maxElevation'], mz)       # Turret clamps at -maxElevation
    dn_e = rot_about(el['pivot'], el['local_axes']['x'], -T['minElevation'], mz)
    ok(f"{el['name']}: localEuler.x = -maxElevation raises the muzzle, -minElevation lowers it", up_e[1] > mz[1] and dn_e[1] < mz[1],
       f"up {up_e[1] - mz[1]:+.2f} down {dn_e[1] - mz[1]:+.2f}")
    fwd = norm(sub(mz, el['pivot']))
    ok(f"{t['mount']['name']}: muzzle lies along the mount forward (+Z)", sum(a * b for a, b in zip(fwd, t['mount']['local_axes']['z'])) > 0.9)
    ok(f"{az['name']}: limits sane", 0 < T['traverseRange'] <= 360 and -90 <= T['minElevation'] < 0 < T['maxElevation'] <= 90)
    for g in t['guns']:
        loc = sub(g['muzzle']['pivot'], g['gun']['pivot'])
        # muzzle at (0, 0.046, 1.2) in the gun frame
        gz = g['gun']['local_axes']['z']
        gy = g['gun']['local_axes']['y']
        along = sum(a * b for a, b in zip(loc, gz))
        up = sum(a * b for a, b in zip(loc, gy))
        ok(f"{g['muzzle']['name']}: at the stock M2 muzzle offset", abs(along - 1.2) < 2e-3 and abs(up - 0.046) < 2e-3, f'{along:.3f}, {up:.3f}')

# ---------------------------------------------------------------- hatches (CanopyHinge, conversion rule)
for h in con['hatches']['hatches']:
    piv = h['hinge']['pivot']
    ax = h['axis_parent_space']
    ok(f"{h['hatch']['name']}: hinge axis == hinge empty local +X", all(abs(a - b) < 1e-3 for a, b in zip(ax, h['hinge']['local_axes']['x'])))
    p_open = rot_about(piv, ax, h['hingeAngle'], h['probe_closed'])
    err = math.sqrt(sum(c * c for c in sub(p_open, h['probe_open'])))
    ok(f"{h['hatch']['name']}: Unity hingeAngle reproduces the Blender open pose (rule check)", err < 2e-3, f'{err * 1000:.2f} mm')
    p_wrong = rot_about(piv, ax, -h['hingeAngle'], h['probe_closed'])
    ok(f"{h['hatch']['name']}: negative test, the opposite sign does not", math.dist(p_wrong, h['probe_open']) > 0.05)
    d = sub(h['probe_open'], h['probe_closed'])
    exp = {'hatch_cockpit_top': d[1] > 0.1, 'hatch_entry_fwd': d[1] < -0.1, 'hatch_entry_rear': d[1] < -0.1,
           'hatch_waist_L': d[0] < -0.1, 'hatch_waist_R': d[0] > 0.1}[h['hatch']['name']]
    ok(f"{h['hatch']['name']}: opens up / down / outward as intended", exp, str([round(c, 2) for c in d]))

# ---------------------------------------------------------------- hardpoints, crew, prop discs
for hp in con['hardpoints']['hardpoints']:
    if hp['pylon']:
        ok(f"{hp['hardpoint']['name']}: at the pylon origin (bottom face)", math.dist(hp['hardpoint']['pivot'], hp['pylon']['pivot']) < 1e-3)
        ok(f"{hp['hardpoint']['name']}: pylon is {hp['pylon']['depth_below_skin']} m deep", 0.05 <= hp['pylon']['depth_below_skin'] <= 0.2)
roles = [c['role'] for c in con['crew']['stations']]
ok('crew of five', sorted(roles) == sorted(['pilot', 'navigator', 'engineer', 'radio', 'tail']), str(roles))
for c in con['crew']['stations']:
    ok(f"crew {c['role']}: eye and seat objects exist", c['eye']['name'] in names and c['seat'] in names)
ok('tail gunner looks aft', [c for c in con['crew']['stations'] if c['role'] == 'tail'][0]['eye']['local_axes']['z'][2] < -0.99)
for s in con['prop_discs']['slots']:
    ok(f"{s['name']}: spin axis +Z forward", s['local_axes']['z'][2] > 0.999)
ok('propDiscMeshes = [null, blur, full]', con['prop_discs']['ConstantSpeedProp']['propDiscMeshes'] == [None, 'propdisc_blur', 'propdisc_full'])
pm = con['breaks']['parent_map']
ok('break parent map: every part chains to fus_center', all(_ for _ in [(lambda n: (lambda f: f(f, n))(lambda f, x: x == 'fus_center' or (pm.get(x) is not None and f(f, pm[x]) if x in pm else x in ('fus_center',))))(k) for k in pm]))

# ---------------------------------------------------------------- 1.8.14 (offline M): roof skin round the dorsal opening, torn seams
# (numbers from the FBX re-import, check_b25h_v2.py -> b25h_v2_check.json; this stub re-judges them from the raw figures)
_ck = json.load(open(os.path.join(D, 'b25h_v2_check.json'))) if os.path.exists(os.path.join(D, 'b25h_v2_check.json')) else {}
_rb = _ck.get('roof_dorsal_boundary_1814')
_sm = _ck.get('seams_1814')


def roof_ok(rb):
    return rb is not None and rb['opening_edges'] > 0 and len(rb['other_edges']) == 0 and rb['odd_vertices'] == 0


def seams_ok(sm, tears=('4.55', '2.62', '1.3', '-1.8', '-6.1')):
    return (sm is not None and all(sm['per_seam'].get(t, {}).get('seam_edges', 0) > 0 for t in tears) and not sm['structure_near_skin']
            and not sm['no_lap'] and sm['lap_vertices'] > 0 and not sm['lap_not_under_skin'])


ok('1.8.14 roof skin round the dorsal opening: no open edge except the opening (closed outline, every vertex even degree)', roof_ok(_rb), str(_rb))
ok('1.8.14 roof check negative test: one open edge outside the trim ring fails it', _rb is not None and not roof_ok(dict(_rb, other_edges=[(0.3, 2.6, 1.36, 0.8)])))
ok('1.8.14 torn seams 4.55 / 2.62 / 1.30 / -1.80 / -6.10: lap strip under every two-sided seam edge, no structure within 2.5 mm of the skin, lap under the skin',
   seams_ok(_sm), '' if _sm is None else f"{_sm['samples']} samples, {_sm['lap_vertices']} lap vertices")
ok('1.8.14 seam check negative test: a wall touching the skin fails it', _sm is not None and not seams_ok(dict(_sm, structure_near_skin=[(2.62, (0, 2.62, 1.36), 0.01)])))

print(f'SUMMARY {n[0] - len(fails)}/{n[0]} passed')
sys.exit(1 if fails else 0)
