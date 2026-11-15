"""Generate unity/Editor/MSB1780Build.cs (Heritage Pairs 1.9.0; MSB-17, formerly MSB-17/80; key MSB17 since 1.9.9) from the generated B17GBuild.cs + unity/msb1780_sections.

The B-17G build code is reused by COPY (design 6.1: "copy, not refactor"): B17GBuild.cs itself and its sections are untouched; this script
renames the identity (class, jsonKey, folders, repo paths, asset / texture prefixes) and replaces the functions where the MSB differs
(head constants + part table, engines, weapons + turrets, cockpit + crew, root systems, FBW, save, checks). Run after editing a section:

    python unity/gen_msb1780build.py            (then copy unity/Editor/*.cs to the Blueprinter project's Assets/Editor)
"""
import os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
SEC = os.path.join(HERE, 'msb1780_sections')
ED = os.path.join(HERE, 'Editor')
base = open(os.path.join(ED, 'B17GBuild.cs'), encoding='utf-8').read()


def rd(n):
    return open(os.path.join(SEC, n), encoding='utf-8').read()


s = base


def splice(start, end, new):
    global s
    a = s.index(start); b = s.index(end, a + len(start))
    s = s[:a] + new + s[b:]


def rep(a, b, count=1):
    global s
    assert a in s, 'missing: ' + a[:100]
    s = s.replace(a, b, count)


# ---------------------------------------------------------------- 1. the MSB functions (written with MSB names) replace the B-17G ones
a = s.index("        // ------------------------------------------------------------------ state for one build")
s = rd('msb_head.cs') + s[a:]
splice("        static readonly int[] EngineNums = { 1, 2, 3, 4 };", "        // the AB-4 (FastBomber1) failure messages", rd('msb_eng.cs'))
splice("        static WeaponMount ammoCannon, ammo50;", "        static WeaponMount Mount(string n)", rd('msb_weap.cs'))
splice("        static void Cockpit(List<LandingGear> gears)", "        // Hatch per contract:", rd('msb_ck.cs'))
splice("        static Pilot MakeCrewMember(CrewSpec c, int index)", "        // ------------------------------------------------------------------ root systems", rd('msb_crew_tur.cs'))
splice("        static void RootSystems(List<LandingGear> gears)", "        static Vector3 TipPoint(", rd('msb_root.cs'))
splice("        static void FlyByWire(LandingGear noseGear)", "        // =================================================================== damage diagram", rd('msb_fbw.cs'))
splice("        static GameObject SaveEverything()", "        static (float t, float v)[] WingCL", rd('msb_save.cs'))
sys.path.insert(0, SEC)
import compose_check
a = s.index("        static bool RunCheck(GameObject prefab)")
s = s[:a] + compose_check.compose()

# ---------------------------------------------------------------- 2. identity renames in the reused B-17G code (not inside the MSB sections)
REN = [
    # 1.9.9: the key is MSB17 (was MSB1780). In-pack names (assets, materials, sprites, textures, prefab, definition) take MSB17 / msb17;
    # repo file / folder / class names keep msb1780 (model_msb1780, textures_msb1780, msb1780_contract.json, MSB1780Build, MSB1780Source).
    ('public static class B17GBuild', 'public static class MSB1780Build'), ('B17GBuild.', 'MSB1780Build.'),
    ('Debug.Log("[B25H] B17G " + s)', 'Debug.Log("[B25H] MSB17 " + s)'),
    ('"b17g_contract.json"', '"msb1780_contract.json"'),      # before the generic "b17g_ rule: a repo file name in assets/model_msb1780
    ('"B17G', '"MSB17'), ('/B17G.prefab', '/MSB17.prefab'), ('/B17G.asset', '/MSB17.asset'), ('B17GSource', 'MSB1780Source'),
    ('"b17g_', '"msb17_'), ("b17g_v2.fbx", "msb17_v2.fbx"), ('b17g_v2_propdisc.fbx', 'msb17_v2_propdisc.fbx'),
    ('/Textures/b17g_propblur.png', '/Textures/msb17_propblur.png'),
    ('model_b17g', 'model_msb1780'), ('prop blur atlas b17g_propblur.png', 'prop blur atlas msb17_propblur.png'),
    ('texture worker art b17g_map_icon.png', 'texture worker art msb17_map_icon.png'),
    ('textures_b17g', 'textures_msb1780'),
    ('"no b17g_liveries.json"', '"no msb17_liveries.json"'), ('"centre fuselage object B17G missing"', '"centre fuselage object MSB17 missing"'),
    ('"/B17G_statusDisplay.prefab"', '"/MSB17_statusDisplay.prefab"'),
]
for x, y in REN:
    s = s.replace(x, y)
# anything B-17G-specific left in CODE (comments may keep the history) must be deliberate: list the code lines that still say B17G / b17g
left = [ln for ln in s.splitlines() if re.search(r'[Bb]17[Gg]', ln.split('//')[0]) and 'B17GWingDrag' not in ln]
if left:
    print('B17G references left in code:'); print('\n'.join(left[:40])); sys.exit(1)

# ---------------------------------------------------------------- 3. reused-code values that differ (gear sized for 34-43 t, rudder, templates)
rep('foreach (var n in new[] { "COIN", "CAS1", "EW1", "turret_57mm_SideMount", "gun_12.7mm_internal", "turret_12.7mm_door", "FastBomber1" })',
    'foreach (var n in new[] { "COIN", "CAS1", "EW1", "turret_57mm_SideMount", "gun_12.7mm_internal", "turret_12.7mm_door", "FastBomber1", "turret_20mm_rotary", "Laser_EW1", "LaserTrailer1" })')
rep('CS("rudder", "CAS1:rudder_L", 0, 0, -22f, 40f);', 'CS("rudder", "CAS1:rudder_L", 0, 0, -RudderThrow, 40f);')
rep('const float MainK = 1.6e6f, MainC = 1.3e5f, MainMaxComp = 0.45f, TailK = 3.5e5f, TailC = 3.0e4f;',
    'const float MainK = 2.4e6f, MainC = GearDamp193 ? 2.9e5f : 1.95e5f, MainMaxComp = 0.45f, TailK = GearDamp193 ? 6.5e5f : 5.2e5f, TailC = GearDamp193 ? 6.0e4f : 4.5e4f, TailMaxComp = GearDamp193 ? 0.36f : 0.30f;   // 1.9.0 MSB: 1.5 x the B-17G (34-43 t on the same legs); 1.9.3: main damping x1.49 (rebound after the AI touchdown; per-step c dt / m 2.93 on wing_inner, under the B-25H 3.33 that runs smooth), tail 6.5e5 / 6.0e4 / break 0.36 (5 m/s sink 3-point touchdown 0.31 m: tools/flightmodel/msb1780_touchdown.py)')
rep('maxComp = 0.30f, mass = 80f,', 'maxComp = TailMaxComp, mass = 80f,')
rep('const float MainFriction = 0.8f, MainBrakeShare = 0.275f;', 'const float MainFriction = 0.8f, MainBrakeShare = 0.35625f;   // 1.9.2 MSB: 0.34 -> 0.356 = BrakeFriction 0.285, the most the nose-over rule allows (tail-up CoM angle 19.4 deg in msb1780_ground.py - atan 0.285 = 3.5 deg). In game 1.9.0 the 3-point stop measured 0.22 g against the 0.272 tail-up figure: 16 % of the weight sits on the unbraked tail wheel (wlog: mains 267 / tail 51 kN), so 3-point braking = 0.285 x 0.84 = 0.24 g (+ the 1.9.2 airbrake at idle)')
rep('const float BrakeFriction = 0.22f, MainContactArea = 0.09f', 'const float BrakeFriction = 0.285f, MainContactArea = 0.12f')
# 1.9.2: flaps follow the speed schedule from 72 m/s (fully down at 58; were 63 / 52): more lift at the heavy lift-off (~62 m/s) and drag on final
rep('S(h, "speedDeployed", 52f); S(h, "speedRetracted", 63f);', 'S(h, "speedDeployed", FlapSpeedDown); S(h, "speedRetracted", FlapSpeedUp);')
rep('const bool ColumnPlugin189 = true;', 'const bool ColumnPlugin189 = false;   // MSB: no control columns (stock SFB-81 sticks on Cockpit.joysticks)')
rep('const bool ANM2Guns = true;', 'const bool ANM2Guns = false;  // MSB: own twin 20 mm in the model')
rep('maxComp = MainMaxComp, mass = 450f,', 'maxComp = MainMaxComp, mass = 650f,')
rep('var pts = new[] { (0f, 0.008f), (0.025f, 0.0114f), (0.05f, 0.022f)', 'var pts = new[] { (0f, WingCd0), (0.025f, WingCd0 + 0.0034f), (0.05f, 0.022f)')
# MSB escape hatches are jettisoned before the ejection seats fire: the COIN canopy values (GA-25X canopy_jettison), not the B-17G bail-out hatch
rep('cn.ejectionTransform = ej.transform; cn.attachedPart = part; cn.mass = 20f; cn.ejectionCollider = box;', 'cn.ejectionTransform = ej.transform; cn.attachedPart = part; cn.mass = 50f; cn.ejectionCollider = box;')
rep('S(cn, "ejectionForce", new Vector3(0f, 800f, 0f));', 'S(cn, "ejectionForce", new Vector3(0f, 4000f, 0f));')
# reused check rows: the stock EjectionSeat's own collider (the GA-25X / FD-32 ship it unchanged and flew it) is cooked by the game, not
# ours; the mfd_* screens are rebuilt in Unity as stock tac-page quads (MFDScreens), like the props
rep('.Where(c => c.convex && c.sharedMesh != null && c.sharedMesh.vertexCount > 100)',
    '.Where(c => c.convex && c.sharedMesh != null && c.sharedMesh.vertexCount > 100 && c.name != "EjectionSeat")')
rep('if (mf.sharedMesh == null || mf.name.StartsWith("prop_") ||', 'if (mf.sharedMesh == null || mf.name.StartsWith("prop_") || mf.name.StartsWith("mfd_") || mf.sharedMesh.name.EndsWith("_tac") ||')   # 1.9.2: + the WSO / EWO tac screens rebuilt by TacScreenMesh
# ... and they leave the expected count too (the MSB has 56 prop_* objects: 8 rows x blades / hubs / spinners, against the B-17G's ~16)
rep('var want = tab.Where(r => (int)r["tris"] > 0 && !((string)r["name"]).EndsWith("_hullsrc")).ToDictionary(',
    'var want = tab.Where(r => (int)r["tris"] > 0 && !((string)r["name"]).EndsWith("_hullsrc") && !((string)r["name"]).StartsWith("prop_") && !((string)r["name"]).StartsWith("mfd_") && !(TacPanels192 && (((string)r["name"]).StartsWith("cockpit_screen_wso1") || ((string)r["name"]).StartsWith("cockpit_screen_ewo1")))).ToDictionary(')
# 1.9.6 cockpit detail pass: backlit legends and annunciator lamps (simple emissive materials, no textures; blender/msb1780/msb_detail196.py)
rep('            Save(LitMat(lit, "MSB17_screen", Color.black, 0f, 0.5f), "screen");',
    '            Save(LitMat(lit, "MSB17_screen", Color.black, 0f, 0.5f), "screen");\n'
    '            foreach (var (key, col, glow) in new[] { ("ck_legend", new Color(0.90f, 0.90f, 0.86f), 0.55f), ("ck_amber", new Color(0.85f, 0.52f, 0.08f), 0.45f), ("ck_green", new Color(0.22f, 0.78f, 0.32f), 0.40f) })\n'
    '            {   // 1.9.6: backlit legends / annunciator lamps on our deck (URP Lit + emission; no texture)\n'
    '                var em = LitMat(lit, "MSB17_" + key, col, 0f, 0.4f);\n'
    '                em.EnableKeyword("_EMISSION"); em.SetColor("_EmissionColor", col * glow); em.globalIlluminationFlags = MaterialGlobalIlluminationFlags.None;\n'
    '                Save(em, key);\n'
    '            }')
# 1.9.12 formation-light strips: the model's `light_off` material slot = the stock light_green_off (the GA-25X line, GA25XBuild.BuildMaterials).
# Keyed on the MODEL (contract lights.formation, written only with msb_spec.STRIPS1912), not on FormationLights1912: BuildPrefab throws on a
# model material without an entry whatever the Unity flag says, and a model built with the strips off gets the 1.9.11 material list (the
# "materials:" build-log line stays as in 1.9.11).
rep('                Save(em, key);\n            }',
    '                Save(em, key);\n            }\n'
    '            if (JList("lights", "formation").Any()) mats["light_off"] = Asset<Material>("Material/light_green_off_PLACEHOLDER.mat");   // 1.9.12 slimelight_* strips unlit (stock light_green_off; msb_spec.STRIPS1912)')


# 1.9.12: the B-17G got an invisible airbrake (InvisibleAirbrake1912: a call at the end of its RootSystems + two helper methods + a check
# row). The MSB-17 keeps exactly ONE Airbrake, its own Airbrake192 block in msb_root.cs. Today the B-17G additions fall inside the spliced
# RootSystems / RunCheck / head and vanish; if they ever move, strip them here and fail loudly rather than build a second Airbrake.
def _strip_method(sig):
    global s
    a_ = s.find(sig)
    if a_ < 0:
        return False
    i = s.index('{', a_); d = 0
    for j in range(i, len(s)):
        d += s[j] == '{'; d -= s[j] == '}'
        if d == 0:
            break
    a0 = s.rfind('\n', 0, a_) + 1
    while True:        # the comment lines directly above the method go with it
        p0 = s.rfind('\n', 0, a0 - 1) + 1
        if s[p0:a0].strip().startswith('//'):
            a0 = p0
        else:
            break
    b0 = s.index('\n', j) + 1
    while s[b0:b0 + 1] == '\n':      # ... and the blank line(s) after it
        b0 += 1
    s = s[:a0] + s[b0:]
    return True


_stripped = [sig for sig in ('static void AddInvisibleAirbrake(', 'static string InvisibleAirbrakeProblems(') if _strip_method(sig)]
s = re.sub(r'^[ \t]*if \(InvisibleAirbrake1912\) AddInvisibleAirbrake\([^\n]*\n', '', s, flags=re.M)
s = re.sub(r'^[ \t]*(//[^\n]*\n[ \t]*)*const bool InvisibleAirbrake1912 = [^\n]*\n[ \t]*const float InvisibleAirbrakeDrag[^\n]*\n', '', s, flags=re.M)
if _stripped:
    print('note: B-17G invisible-airbrake helpers stripped from the MSB build:', _stripped)
_code = [ln.split('//')[0] for ln in s.splitlines()]
_inv = [ln for ln in _code if 'InvisibleAirbrake' in ln]
_add = [ln for ln in _code if 'AddComponent<global::Airbrake>()' in ln]
if _inv or len(_add) != 1:
    print('MSB-17 must carry exactly ONE Airbrake (its Airbrake192 block in msb_root.cs):', len(_add), 'AddComponent<global::Airbrake>() lines,', len(_inv), 'InvisibleAirbrake references')
    print('\n'.join((_inv + _add)[:20])); sys.exit(1)
for _need in ('var ab = root.AddComponent<global::Airbrake>();', 'S(ab, "part", parts["MSB17"]);', 'const bool Airbrake192 = true;', 'const float AirbrakeDrag = 3.0f, AirbrakeOpenSpeed = 1.0f;'):
    assert _need in s, 'pinned text missing (tools/stub_tests_192 / 193 / 194): ' + _need
s = s.replace('\r\n', '\n')
open(os.path.join(ED, 'MSB1780Build.cs'), 'w', encoding='utf-8', newline='\r\n').write(s)   # CRLF as the other generators
print('wrote', os.path.join(ED, 'MSB1780Build.cs'), len(s.splitlines()), 'lines')
