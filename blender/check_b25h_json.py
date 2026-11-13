"""Validate assets/model/b25h_model.json without Blender or Unity.

  python -I blender/check_b25h_json.py assets/model/b25h_model.json

Checks: required names, unique names, parents exist and precede children, index ranges, normal/uv
counts, unit normals, unit quaternions, scale == 1, overall bounding box (span/length/height),
wheel contact vs groundOffset, blade1 pointing up, every movable part has a hinge axis.
Exit code 0 on success.
"""
import json, math, sys

REQUIRED = ['B25H_root', 'fuselage', 'nose_guns', 'cannon', 'canopy_glass', 'turret_dorsal', 'turret_dorsal_guns',
            'tail_guns', 'waist_blister_L', 'waist_blister_R', 'wing_L', 'wing_R', 'aileron_L', 'aileron_R', 'flap_L',
            'flap_R', 'nacelle_L', 'nacelle_R', 'cowling_L', 'cowling_R', 'prop_hub_L', 'prop_hub_R',
            'prop_L_blade1', 'prop_L_blade2', 'prop_L_blade3', 'prop_R_blade1', 'prop_R_blade2', 'prop_R_blade3',
            'stab_h', 'elevator_L', 'elevator_R', 'fin_L', 'fin_R', 'rudder_L', 'rudder_R', 'gear_nose_strut',
            'gear_nose_wheel', 'gear_main_L_strut', 'gear_main_L_wheel', 'gear_main_R_strut', 'gear_main_R_wheel',
            'bomb_door_L', 'bomb_door_R']
MOVABLE = ['turret_dorsal', 'turret_dorsal_guns', 'aileron_L', 'aileron_R', 'flap_L', 'flap_R', 'prop_hub_L',
           'prop_hub_R', 'elevator_L', 'elevator_R', 'rudder_L', 'rudder_R', 'gear_nose_strut', 'gear_nose_wheel',
           'gear_main_L_strut', 'gear_main_L_wheel', 'gear_main_R_strut', 'gear_main_R_wheel', 'bomb_door_L',
           'bomb_door_R'] + [f'prop_{s}_blade{k}' for s in 'LR' for k in (1, 2, 3)]
MATERIALS = {'paint_olive', 'paint_grey', 'metal_dark', 'rubber', 'glass', 'prop_black', 'prop_tip_yellow', 'insignia'}


def qmul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
            aw * bw - ax * bx - ay * by - az * bz)


def qrot(q, v):
    x, y, z, w = q
    vx, vy, vz = v
    # v' = q v q*
    tx = 2 * (y * vz - z * vy)
    ty = 2 * (z * vx - x * vz)
    tz = 2 * (x * vy - y * vx)
    return (vx + w * tx + (y * tz - z * ty), vy + w * ty + (z * tx - x * tz), vz + w * tz + (x * ty - y * tx))


def main(path):
    errors, notes = [], []
    d = json.load(open(path))
    assert d.get('version') == 1 and d.get('unit') == 'm', 'bad header'
    objs = d['objects']
    by = {}
    for i, o in enumerate(objs):
        if o['name'] in by:
            errors.append(f'duplicate name {o["name"]}')
        by[o['name']] = (i, o)
    for n in REQUIRED:
        if n not in by:
            errors.append(f'missing required object {n}')
    # world transforms
    world = {}
    for i, o in enumerate(objs):
        p = o['parent']
        if p is not None:
            if p not in by:
                errors.append(f'{o["name"]}: parent {p} missing')
                continue
            if by[p][0] > i:
                errors.append(f'{o["name"]}: parent listed after child')
        if p is None and o['name'] != 'B25H_root':
            errors.append(f'{o["name"]} is not under B25H_root')
        q = o['rotation']
        if abs(math.sqrt(sum(c * c for c in q)) - 1) > 1e-3:
            errors.append(f'{o["name"]}: rotation not unit {q}')
        if any(abs(s - 1) > 1e-6 for s in o['scale']):
            errors.append(f'{o["name"]}: scale {o["scale"]}')
        if p is None:
            world[o['name']] = (tuple(o['position']), tuple(q))
        else:
            pp, pq = world[p]
            lp = qrot(pq, o['position'])
            world[o['name']] = ((pp[0] + lp[0], pp[1] + lp[1], pp[2] + lp[2]), qmul(pq, tuple(q)))
    lo = [1e9] * 3
    hi = [-1e9] * 3
    total = 0
    wheel_min_y = {}
    for o in objs:
        m = o['mesh']
        if m is None:
            continue
        v, n, uv = m['vertices'], m['normals'], m['uvs']
        nv = len(v) // 3
        if len(v) % 3 or len(n) != len(v):
            errors.append(f'{o["name"]}: normals count {len(n)} != vertices {len(v)}')
        if len(uv) != 2 * nv:
            errors.append(f'{o["name"]}: uv count {len(uv)} != 2*{nv}')
        for k in range(0, len(n), 3 * 97):
            L = math.sqrt(n[k] ** 2 + n[k + 1] ** 2 + n[k + 2] ** 2)
            if abs(L - 1) > 2e-3:
                errors.append(f'{o["name"]}: non-unit normal {L}')
                break
        for s in m['submeshes']:
            t = s['triangles']
            if s['material'] not in MATERIALS:
                errors.append(f'{o["name"]}: unknown material {s["material"]}')
            if len(t) % 3:
                errors.append(f'{o["name"]}: triangle list not multiple of 3')
            if t and (min(t) < 0 or max(t) >= nv):
                errors.append(f'{o["name"]}: index out of range')
            for a in range(0, len(t), 3):
                if len({t[a], t[a + 1], t[a + 2]}) < 3:
                    errors.append(f'{o["name"]}: degenerate triangle index')
                    break
            total += len(t) // 3
        wp, wq = world[o['name']]
        ymin = 1e9
        for k in range(0, len(v), 3):
            p = qrot(wq, (v[k], v[k + 1], v[k + 2]))
            p = (p[0] + wp[0], p[1] + wp[1], p[2] + wp[2])
            for a in range(3):
                lo[a] = min(lo[a], p[a])
                hi[a] = max(hi[a], p[a])
            ymin = min(ymin, p[1])
        if o['name'].endswith('_wheel'):
            wheel_min_y[o['name']] = ymin
    size = [hi[a] - lo[a] for a in range(3)]
    for a, name, want, tol in ((0, 'span x', 20.60, 0.25), (2, 'length z', 15.54, 0.35), (1, 'height y', 4.98, 0.25)):
        if abs(size[a] - want) > tol:
            errors.append(f'{name} = {size[a]:.3f} m, expected {want} +- {tol}')
    g = d['groundOffset']
    for w, y in wheel_min_y.items():
        if abs(y + g) > 0.02:
            errors.append(f'{w}: bottom at {y:.3f}, groundOffset says {-g:.3f}')
    if abs(lo[1] + g) > 0.02:
        errors.append(f'lowest point {lo[1]:.3f} is not the wheel contact {-g:.3f}')
    # blade1 must point straight up (+Y) in the rest pose
    for s in 'LR':
        o = by[f'prop_{s}_blade1'][1]
        v = o['mesh']['vertices']
        far = max(range(0, len(v), 3), key=lambda k: v[k] ** 2 + v[k + 1] ** 2 + v[k + 2] ** 2)
        tip = qrot(world[o['name']][1], (v[far], v[far + 1], v[far + 2]))
        if tip[1] < 1.8 or abs(tip[0]) > 0.15:
            errors.append(f'prop_{s}_blade1 tip not straight up: {tip}')
        if abs(math.sqrt(sum(c * c for c in tip)) - 1.93) > 0.03:
            errors.append(f'prop_{s} radius {math.sqrt(sum(c * c for c in tip)):.3f} != 1.93')
    for nme in MOVABLE:
        if nme in by and 'hingeAxis' not in by[nme][1]:
            errors.append(f'{nme}: no hingeAxis')
    print(f'objects {len(objs)}  triangles {total}')
    print(f'bbox min ({lo[0]:.3f}, {lo[1]:.3f}, {lo[2]:.3f})  max ({hi[0]:.3f}, {hi[1]:.3f}, {hi[2]:.3f})')
    print(f'size  span(x) {size[0]:.3f}  height(y) {size[1]:.3f}  length(z) {size[2]:.3f}   groundOffset {g}')
    if errors:
        print('FAIL')
        for e in errors[:50]:
            print('  -', e)
        return 1
    print('PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else 'assets/model/b25h_model.json'))
