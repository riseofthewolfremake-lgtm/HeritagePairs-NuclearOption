"""MSB-17/80 CHECK ALL: the B-17G check rows reused by copy where the MSB keeps the B-17G systems (gear, ground handling, crew-in-hull,
internals look, stray references, meshes-arrive-whole: blocks of unity/b17g_sections/b17g_check.cs by line, asserted by content), the
MSB rows written here (msb_check_rows.cs). Called by unity/gen_msb1780build.py; returns the RunCheck text."""
import os, re
HERE = os.path.dirname(os.path.abspath(__file__))


def compose():
    src = open(os.path.join(HERE, '..', 'b17g_sections', 'b17g_check.cs'), encoding='utf-8').read().splitlines()

    def block(a, b, first, last):
        t = src[a - 1:b]
        assert first in t[0], (a, t[0][:80])
        assert last in t[-1], (b, t[-1][:80])
        return '\n'.join(t) + '\n'
    gear = block(56, 139, '// gear', '}')
    crew_hull = block(162, 219, '{   // (4) every crew vertex inside the hull', 'R("crew inside the hull')
    crew_hull += '                }\n'
    look = block(404, 408, '{   // 1.8.5 offline E', '}')
    stray_mesh = block(454, 499, '// references', '}')
    assert src[496].strip() == 'public static string lastCheck = "";'
    gear = gear.replace('R("gear: 2 braked mains + 1 steerable tailwheel, k / damping sized for 25 t (k of braked + grip)", mains.Count == 2 && tailg != null && mains.All(g => (bool)G(g, "braked") && (float)G(g, "springRate") >= 1.2e6f * (SplitMainGear ? MainBrakeShare : 1f))',
                        'R("gear: 2 braked mains + 1 steerable tailwheel, k / damping sized for 34-43 t (1.5 x the B-17G; k of braked + grip)", mains.Count == 2 && tailg != null && mains.All(g => (bool)G(g, "braked") && (float)G(g, "springRate") >= 1.8e6f * (SplitMainGear ? MainBrakeShare : 1f))')
    gear = gear.replace('R($"1.8.0 split mains:', 'R($"split mains (B-17G 1.8.0; braked share sized for the MSB):')
    gear = gear.replace('R($"nose-over: tail-up CoM angle >= brake friction angle + 3 deg (coordinator 1.6.1 target; noseover.py; friction {BrakeFriction})"',
                        'R($"nose-over: tail-up CoM angle >= brake friction angle + 3 deg (msb1780_ground.py 1.9.2: tail-up braking 0.285 g, 3-point 0.24 g; friction {BrakeFriction})"')
    gear = gear.replace('R("ground handling: braking >= 1.8 m/s2 (1.7.3), nose-over margin >= 3 deg, grass drag at 33 m/s <= 15 % of the wheel load, taxi radius <= 30 m, tailwheel not castering"',
                        'R("ground handling (MSB): braking >= 2.0 m/s2, nose-over margin >= 3 deg, grass drag at 33 m/s <= 15 % of the wheel load, taxi radius <= 30 m, tailwheel not castering"')
    gear = gear.replace('bool ok = decel >= 1.8f &&', 'bool ok = decel >= 2.0f &&')
    gear = gear.replace('1.6.0 Player.log: partial hulls on 8 B17G parts', 'the B-17G 1.6.0 lesson')
    # 1.9.5 (MSB only; the B-17G check text is unchanged): the any-hit Physics.Raycast(origin, dir, dist, mask) drops back-face hits near triangle
    # edges that the closest-hit overload reports (the 1.8.17 CrewRayDebug finding; unity/Editor/CrewRayDebug195.cs on the 1.9.5 WSO vertex: 19 of
    # 1,200 jittered rays missed with the bool query while the RaycastHit query and the mesh triangles hit the nose skin 0.92 m away). The crew
    # rays use the closest-hit overload: a vertex counts as outside only when no airframe triangle is on that side.
    old_r = 'bool r1 = Physics.Raycast(p, right, 4f, mask), r2 = Physics.Raycast(p, -right, 4f, mask);'
    old_u = 'bool u1 = Physics.Raycast(p, upv, 4f, mask), hd = Physics.Raycast(p, -upv, 4f, mask);'
    assert old_r in crew_hull and old_u in crew_hull
    crew_hull = crew_hull.replace(old_r, 'bool r1 = Physics.Raycast(p, right, out _, 4f, mask), r2 = Physics.Raycast(p, -right, out _, 4f, mask);   // 1.9.5: closest-hit overload (compose_check.py)')
    crew_hull = crew_hull.replace(old_u, 'bool u1 = Physics.Raycast(p, upv, out _, 4f, mask), hd = Physics.Raycast(p, -upv, out _, 4f, mask);')
    stray_mesh = stray_mesh.replace('"b17g_parts.json"', '"msb1780_parts.json"').replace('(string)r["name"] == "B17G" ? "fus_center"', '(string)r["name"] == "MSB17" ? "fus_center"')
    rows = open(os.path.join(HERE, 'msb_check_rows.cs'), encoding='utf-8').read()
    head, rest = rows.split('                // @@GEAR@@\n')
    mid, rest = rest.split('                // @@CREW_HULL@@\n')
    mid2, rest = rest.split('                // @@LOOK@@\n')
    mid3, _ = rest.split('                // @@STRAY_MESH@@\n')
    out = head + gear + mid + crew_hull + mid2 + look + mid3 + stray_mesh
    left = [ln for ln in out.splitlines() if re.search(r'[Bb]17[Gg]', ln.split('//')[0])]
    assert not left, left[:5]
    return out


if __name__ == '__main__':
    print(len(compose().splitlines()), 'lines')
