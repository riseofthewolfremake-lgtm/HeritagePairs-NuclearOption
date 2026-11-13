        static bool RunCheck(GameObject prefab)
        {
            var rows = new List<(string name, bool ok, string detail)>();
            void R(string n, bool ok, string d) => rows.Add((n, ok, d));
            var inst = (GameObject)Object.Instantiate(prefab);
            try
            {
                {   // 1.8.16 livery-atlas guard (AtlasGuard1816.cs = blender/atlas_guard.py): the skin / livery / damage textures were painted on THIS UV0 atlas
                    var ag = AtlasGuard1816.Check(inst, mats["paint"], Path.Combine(RepoTextures, "msb17_atlas_manifest.json"), new Dictionary<string, string> { { "fus_center", "MSB17" } });
                    R("1.8.16 livery atlas: UV0 of the paint meshes == the texture manifest (textures painted on this atlas, files unchanged)", ag.Item1, ag.Item2);
                }
                var ac = inst.GetComponent<Aircraft>();
                var allParts = inst.GetComponentsInChildren<AeroPart>(true);
                Transform T(string n) => inst.GetComponentsInChildren<Transform>(true).FirstOrDefault(x => x.name == n);
                var def = ac.definition;
                R("definition: MSB17 'MSB-17' (1.9.9 rename: unitName / code / aircraftName / WorkshopTag exactly 'MSB-17', no '17/80' in the description), rank 4, $110m, 31.62 m span, RCS 1.2, crew 4, damage tolerance 1.5, 3-point rest rotation",
                    def != null && def.jsonKey == JsonKey && JsonKey == "MSB17" && def.unitName == "MSB-17" && def.code == "MSB-17" && def.WorkshopTag == "MSB-17" && ((AircraftDefinition)def).aircraftParameters.aircraftName == "MSB-17" && !def.description.Contains("17/80") && def.description.StartsWith("MSB-17,") && ((AircraftDefinition)def).aircraftParameters.rankRequired == 4 && Mathf.Abs(def.value - 110f) < 0.01f && Mathf.Abs(def.width - 31.62f) < 0.01f
                    && Mathf.Abs(def.radarSize - 1.2f) < 1e-4f && def.manpower == 4 && Mathf.Abs(def.damageTolerance - 1.5f) < 1e-4f && (!SpawnThreePoint || ((AircraftDefinition)def).restRotation.x < -5f),
                    $"spawn y {def?.spawnOffset.y:F3}, rest {((AircraftDefinition)def)?.restRotation}, value {def?.value}, RCS {def?.radarSize}");
                float m = allParts.Sum(p => p.mass);
                R("mass: parts 24-27 t (24.5 t empty + crew + 20 mm ammo), encyclopedia empty 24,500 / max 43,000 kg", m > 24000f && m < 27000f && Mathf.Abs(((AircraftDefinition)def).aircraftInfo.emptyWeight - 24500f) < 1f && Mathf.Abs(((AircraftDefinition)def).aircraftInfo.maxWeight - 43000f) < 1f, $"{m:F0} kg");
                var props = inst.GetComponentsInChildren<ConstantSpeedProp>(true);
                var trs = props.Select(p => (Transmission)G(p, "transmission")).ToList();
                var engs = inst.GetComponentsInChildren<TurbineEngine>(true);
                R("4 TurbineEngines 4.03 MW, each with its own Transmission driving TWO ConstantSpeedProps (front + aft row), messages ENGINE 1-4 FIRE",
                    engs.Length == 4 && engs.All(e => Mathf.Abs(e.maxPower - EnginePower) < 1f) && (!ContraProps190 || (props.Length == 8 && trs.Distinct().Count() == 4 && trs.GroupBy(t => t).All(g => g.Count() == 2)))
                    && trs.All(t => t != null && t.GetComponent<TurbineEngine>() != null) && engs.Select(e => (string)G(e, "failureMessage")).OrderBy(x => x).SequenceEqual(new[] { "ENGINE 1 FIRE", "ENGINE 2 FIRE", "ENGINE 3 FIRE", "ENGINE 4 FIRE" }),
                    string.Join(", ", props.Select(p => $"{p.name}->{((Transmission)G(p, "transmission")).name}")));
                {
                    var bad = new List<string>();
                    foreach (var g in props.GroupBy(p => (Transmission)G(p, "transmission")))
                    {
                        var rows2 = g.ToList();
                        int turnSum = rows2.Sum(p => Convert.ToInt32(G(p, "turnDirection")));
                        float nom = rows2.Sum(p => (float)G(p, "nominalPower"));
                        var nParts = rows2.Select(p => ((UnitPart)G(p, "unitPart")).transform).Distinct().Count();
                        if (ContraProps190 && (turnSum != 0 || Mathf.Abs(nom - EnginePower) > 1f || nParts != 1)) bad.Add($"{g.Key.name}: turn sum {turnSum}, nominal {nom / 1e6f:F2} MW, parts {nParts}");
                        foreach (var p in rows2)
                        {
                            int dir = Convert.ToInt32(G(p, "turnDirection"));
                            foreach (var b in (IList)G(p, "blades"))
                            {
                                var bt = (Transform)G(b, "transform"); var lt = (Transform)G(b, "liftTransform");
                                var motion = Vector3.Cross(-p.transform.forward, bt.forward).normalized * dir;
                                if (Vector3.Dot(lt.forward, motion) < 0.98f) { bad.Add($"{p.name} blade lift transform off its motion"); break; }
                            }
                            if (((IList)G(p, "blades")).Count != 6) bad.Add($"{p.name} {((IList)G(p, "blades")).Count} blades");
                            if (!(G(p, "propStrikeDetector") is PropStrikeDetector psd && psd.gameObject.layer == 15 && Mathf.Abs((float)G(p, "bladeLength") - 1.70f) < 0.05f)) bad.Add($"{p.name} strike / R");
                        }
                    }
                    R("contra-rotation: per engine the two rows turn opposite ways (torques cancel), share the engine (2 x 2.015 MW), ride one part; 6 blades each, R 1.70, own strike trigger, blade lift transforms along their motion",
                        bad.Count == 0, bad.Count == 0 ? $"{props.Length} rows" : string.Join("; ", bad.Take(6)));
                }
                var fusCols = allParts.Where(p => p.name == "MSB17" || p.name.StartsWith("fus_")).Select(p => p.GetComponent<MeshCollider>()).Where(c => c != null).ToList();
                float worst = 9f;
                foreach (var p in props)
                {
                    var c = p.transform.position; float Rr = (float)G(p, "bladeLength");
                    for (int k = 0; k < 72; k++)
                    {
                        float a = k * Mathf.PI * 2 / 72; var q = c + (p.transform.right * Mathf.Cos(a) + p.transform.up * Mathf.Sin(a)) * Rr;
                        foreach (var col in fusCols) { var cp = col.ClosestPoint(q); worst = Mathf.Min(worst, (cp - q).magnitude); }
                    }
                }
                R("prop tips >= 0.15 m from the fuselage colliders (both rows)", worst >= 0.15f, $"min {worst:F3} m");
                {
                    var dmgPath = Path.Combine(RepoTextures, "msb17_skin_dmg_b.png");
                    var hc = DamageHoles189.Check(dmgPath, tex.ContainsKey("msb17_skin_dmg_b") ? tex["msb17_skin_dmg_b"] : null);
                    var pm = mats["paint"];
                    R("skin damage HOLES: dmg_b alpha opens 5-13 / 10-27 / 15-30 % of the skin at HP 80 / 50 / 0 (stock bands), paint material uses dmg_b / dmg_n, alpha kept on import",
                        hc.Item1 && File.Exists(Path.Combine(RepoTextures, "msb17_skin_dmg_n.png")) && pm.GetTexture("_BasecolorDmg") == tex["msb17_skin_dmg_b"] && pm.GetTexture("_NormalDmg") == tex["msb17_skin_dmg_n"], hc.Item2);
                }
                // @@GEAR@@
                {   // the accepted taildragger stack: castoring mains (GripGear.Castor) under B25H.Instruments GroundGrip189 + TaxiTurn1811 (keyed MSB17 in 1.9.0)
                    bool cok = GripGear.VerifyCastor(inst, MainCastorRange, MainCastorAlign, out string cd);
                    R($"castoring mains (B-17G 1.8.8 stack): braked mains steering, speed 0, aligning {MainCastorAlign}, range +-{MainCastorRange} deg; tail wheel locked (not castering), lock {TailSteeringLock}", MainCastor188 && cok, cd);
                }
                Physics.SyncTransforms();
                // @@CREW_HULL@@
                var wm = ac.weaponManager;
                var setNames = wm.hardpointSets.Select(x => x.name).ToList();
                R("hardpoint sets in loadout order: Bomb Bay, Bay Tandem, Bay Racks, Defensive Bays, Inner Pylons, Outer Pylons, Chin 20mm, Tail 20mm, Dorsal Laser, Ventral Laser",
                    setNames.SequenceEqual(new[] { "Bomb Bay", "Bay Tandem", "Bay Racks", "Defensive Bays", "Inner Pylons", "Outer Pylons", "Chin 20mm", "Tail 20mm", "Dorsal Laser", "Ventral Laser" }), string.Join(", ", setNames));
                var bayS = wm.hardpointSets[0];
                R("bay arrangements exclude each other (precludingHardpointSets 0 <-> 1 <-> 2), all on the two bay doors",
                    wm.hardpointSets[0].precludingHardpointSets.SequenceEqual(new byte[] { 1, 2 }) && wm.hardpointSets[1].precludingHardpointSets.SequenceEqual(new byte[] { 0, 2 }) && wm.hardpointSets[2].precludingHardpointSets.SequenceEqual(new byte[] { 0, 1 })
                    && wm.hardpointSets.Take(3).All(x => x.hardpoints.All(h => h.bayDoors.Length == 2)), "");
                var opts = wm.hardpointSets.Take(6).SelectMany(x => x.weaponOptions.Skip(1)).ToList();
                R("bay / side-bay / pylon options: every stock mount found, every non-nuclear one allowed (WeaponMount.IsAllowed), ALM-C450 internal only, MMR-S3 in the side bays",
                    opts.All(o => o != null) && opts.Where(o => o.info == null || !o.info.nuclear).All(o => o.IsAllowed(false)) && wm.hardpointSets[3].weaponOptions.Skip(1).Any(o => o.name.StartsWith("AAM1_double_internal"))
                    && !wm.hardpointSets.Skip(4).Take(2).SelectMany(x => x.weaponOptions.Skip(1)).Any(o => o.name.StartsWith("CruiseMissile")) && wm.hardpointSets[0].weaponOptions.Count >= 11,
                    string.Join(" | ", wm.hardpointSets.Take(6).Select(x => $"{x.name}: {x.weaponOptions.Count - 1}")));
                bool doorsOk = true; var dd = new List<string>();
                foreach (var bd in bayS.hardpoints[0].bayDoors.Concat(wm.hardpointSets[3].hardpoints.SelectMany(h => h.bayDoors)))
                {
                    var tr = bd.transform; var mf = tr.GetComponentInChildren<MeshFilter>(); var c0 = mf.transform.TransformPoint(mf.sharedMesh.bounds.center);
                    var r0 = tr.localRotation; tr.localEulerAngles = new Vector3(0, 0, (float)G(bd, "hingeAngle")); var c1 = mf.transform.TransformPoint(mf.sharedMesh.bounds.center); tr.localRotation = r0;
                    bool side = mf.name.Contains("side_bay");
                    bool ok = side ? (c1.y > c0.y + 0.15f && Mathf.Abs(c1.x) > Mathf.Abs(c0.x) + 0.2f) : (c1.y < c0.y - 0.15f && Mathf.Abs(c1.x) > Mathf.Abs(c0.x) + 0.3f); doorsOk &= ok;
                    dd.Add($"{mf.name}: centre moves ({c1.x - c0.x:F2}, {c1.y - c0.y:F2})");
                }
                R("bay doors open down and out, side-bay doors up and out", doorsOk && dd.Count == 4, string.Join("; ", dd));
                {   // side-bay hardpoints rolled: the mount's down (-up) points outboard, so the missiles leave sideways
                    var hl = T("hp_def_L"); var hr = T("hp_def_R");
                    bool ok = hl != null && hr != null && inst.transform.InverseTransformDirection(-hl.up).x < -0.9f && inst.transform.InverseTransformDirection(-hr.up).x > 0.9f && Vector3.Dot(hl.forward, inst.transform.forward) > 0.99f;
                    R("defensive side bays: hardpoints rolled (mount down = outboard), forward along the aircraft", ok, hl != null && hr != null ? $"L down {inst.transform.InverseTransformDirection(-hl.up).ToString("F2")}, R down {inst.transform.InverseTransformDirection(-hr.up).ToString("F2")}" : "missing");
                }
                {   // pylons outboard of the outer prop discs (FD-32 lesson)
                    var outerX = props.Where(p => Mathf.Abs(inst.transform.InverseTransformPoint(p.transform.position).x) > 5f).Select(p => Mathf.Abs(inst.transform.InverseTransformPoint(p.transform.position).x) + (float)G(p, "bladeLength")).DefaultIfEmpty(8.3f).Max();
                    var pyl = new[] { "hp_inner_L", "hp_inner_R", "hp_outer_L", "hp_outer_R" }.Select(T).ToList();
                    bool ok = pyl.All(t => t != null && Mathf.Abs(inst.transform.InverseTransformPoint(t.position).x) - 0.80f > outerX);
                    R("4 pylons outboard of the outer prop discs (widest store half width 0.76 m clear of the disc)", ok, $"disc edge |x| {outerX:F2}; pylons {string.Join(", ", pyl.Select(t => t != null ? $"{t.name} {inst.transform.InverseTransformPoint(t.position).x:F2}" : "missing"))}");
                }
                var tur = inst.GetComponentsInChildren<Turret>(true);
                var guns20 = tur.Select(t => G(t, "aimSafetyWeapon") as Gun).Where(g => g != null).ToList();
                R($"chin + tail: own twin 20 mm 'DTC-20' (one Gun, 2 muzzles, {Gun20Cycles} cycles = {Gun20Cycles * 2} rds, {Gun20CyclesPerMin} cycles/min, v0 {Gun20Velocity}, pierce {Gun20Pierce}, air + missile only), one WeaponInfo per station",
                    guns20.Count == 2 && guns20.All(g => ((Transform[])G(g, "muzzles")).Length == 2 && (int)G(g, "magazineCapacity") == Gun20Cycles && Mathf.Abs((float)G(g, "fireRate") - Gun20CyclesPerMin) < 0.1f
                        && Mathf.Abs(g.info.muzzleVelocity - Gun20Velocity) < 0.1f && Mathf.Abs(g.info.pierceDamage - Gun20Pierce) < 0.1f && g.info.effectiveness.antiSurface == 0f && g.info.weaponName.StartsWith("DTC-20"))
                        && guns20.Select(g => g.info).Distinct().Count() == 2,
                    string.Join(", ", guns20.Select(g => $"{g.name}: {g.info.weaponName} {G(g, "fireRate")}/min x {((Transform[])G(g, "muzzles")).Length}, mag {G(g, "magazineCapacity")}")));
                {
                    var lt = tur.Where(t => G(t, "aimSafetyWeapon") == null).ToList();
                    var lp = stationSets.Where(x => x.station == "Dorsal" || x.station == "Ventral").Select(x => x.ammo.prefab).ToList();
                    var lasers = lp.Where(p => p != null).Select(p => p.GetComponentInChildren<Laser>(true)).ToList();
                    bool ok = lt.Count == 2 && lt.All(t => (bool)G(t, "onlyDefensive") && ((IList)G(t, "targetDetectors")).Count == 1) && lasers.Count == 2 && lasers.All(l => l != null && l.info != null)
                        && lasers.Select(l => l.info).Distinct().Count() == 2;
                    R("two 120 kW lasers on their own stations (own info each), mount prefabs on the apertures, HLT turrets onlyDefensive with their own 15 km detector", ok,
                        string.Join(", ", lasers.Where(l => l != null).Select(l => $"{l.info.weaponName} {G(l, "power")} kW")));
                }
                {   // turret kinematics: mount > az > el; 20 mm muzzles along el +Z at the barrel tips; laser aperture under el; envelope inside the cones
                    var det = new List<string>(); bool ok = true;
                    foreach (var t in tur)
                    {
                        var az = t.transform; var el = (Transform)G(t, "elevationTransform"); var mount = az.parent;
                        var gun = G(t, "aimSafetyWeapon") as Gun;
                        var mz = gun != null ? (Transform[])G(gun, "muzzles") : mount.GetComponentsInChildren<Transform>(true).Where(x => x.name.EndsWith("_aperture")).ToArray();
                        bool par = el.parent == az && mount != null && mount.name.EndsWith("_mount") && mz.Length > 0 && mz.All(x => x.IsChildOf(el));
                        bool rest = Quaternion.Angle(az.localRotation, Quaternion.identity) < 0.5f && Quaternion.Angle(el.localRotation, Quaternion.identity) < 0.5f;
                        float dirErr = mz.Length > 0 ? mz.Max(x => Vector3.Angle(x.forward, el.forward)) : 99f;
                        var cones = (FiringCone[])G(t, "firingCones"); int tot = 0, inside = 0;
                        float tr = Mathf.Min((float)G(t, "traverseRange"), 180f), e0 = (float)G(t, "minElevation"), e1 = (float)G(t, "maxElevation");
                        for (float a = -tr; a <= tr + 0.01f; a += 5f)
                            for (float e = e0; e <= e1 + 0.01f; e += 5f)
                            {
                                var dir = mount.rotation * (Quaternion.Euler(0f, a, 0f) * (Quaternion.Euler(-e, 0f, 0f) * Vector3.forward)); tot++;
                                if (FiringConeChecker.VectorWithinFiringCones(cones, dir, out var _)) inside++;
                            }
                        float share = tot > 0 ? (float)inside / tot : 0f;
                        bool tOk = par && rest && dirErr < 1f && share >= 0.4f; ok &= tOk;
                        det.Add($"{mount?.name}: {(par ? "" : "PARENT ")}{(rest ? "" : "REST ")}bore axis {dirErr:F1} deg, envelope in cones {share * 100f:F0} %, {cones.Length} cones");
                    }
                    R("turret kinematics: mount > az > el, rest at identity, muzzles / apertures along el +Z, >= 40 % of each envelope inside its cones", ok && tur.Length == 4, string.Join("; ", det));
                }
                if (FireClear1814On && DefensiveTurrets)
                {
                    FireClear1814.MuzzleOverride = tr => { var ap = tr.transform.parent != null ? tr.transform.parent.GetComponentsInChildren<Transform>(true).FirstOrDefault(x => x.name.EndsWith("_aperture")) : null; return ap != null ? new[] { ap } : null; };
                    try
                    {
                        var fc14 = FireClear1814.CheckInstance(inst);
                        R("fire clearance (1.8.14 method): no aim direction where a turret may fire into our own airframe (20 mm both muzzles, lasers from the aperture; game FiringConeChecker + 1 deg onTarget; colliders, meshes, prop discs)", fc14.bad == 0, fc14.detail);
                    }
                    finally { FireClear1814.MuzzleOverride = null; }
                }
                {   // the AN/M2 sweep (1.8.13) on our twin 20 mm: cannon surface samples (10 mm) vs everything not on the elevation object, over the envelope
                    var keep = ANM2Gun.GunTag; ANM2Gun.GunTag = "_gun0";
                    try
                    {
                        var cl = ANM2Gun.Clearance(inst);
                        bool ok = cl.Count == 2 && cl.All(r => r.minSweep >= ANM2Gun.ClipDist);
                        R("20 mm clearance sweep (AN/M2 method 1.8.13): cannon surface vs the airframe and the turret bodies over traverse x elevation: 0 clipping poses", ok,
                            string.Join("; ", cl.Select(r => $"{r.turret}: min {r.minSweep * 1000f:F0} mm over {r.poses} poses, worst {r.worstPose} vs {r.worstAgainst}")));
                    }
                    finally { ANM2Gun.GunTag = keep; }
                }
                R("crew of 4 (pilot, co-pilot, WSO, EWO) in stock ejection seats (Pilot.ejectionSeat, the stock EjectionSeat on each figure)",
                    ac.pilots.Length == 4 && ac.pilots.All(p => p != null && (bool)G(p, "ejectionSeat") && p.transform.Find("EjectionSeat") != null), string.Join(", ", ac.pilots.Select(p => p.name)));
                var cans = (Canopy[])G(ac, "canopies");
                R("4 escape hatches jettisoned before the seats (stock Canopy, 4,000 N on 50 kg)", cans != null && cans.Length == 4 && cans.All(c => Mathf.Abs(c.mass - 50f) < 0.1f), cans != null ? string.Join(", ", cans.Select(c => c.name)) : "none");
                R("cockpit view point = the left-seat pilot eye", ac.cockpitViewPoint != null && ac.cockpitViewPoint.position.x < -0.2f, ac.cockpitViewPoint ? ac.cockpitViewPoint.position.ToString("F2") : "none");
                {
                    var ck = inst.GetComponentInChildren<global::Cockpit>(true);
                    var js = ck != null ? (IList)G(ck, "joysticks") : null; var thr = ck != null ? (IList)G(ck, "throttles") : null;
                    bool sticks = js != null && js.Count == 2;
                    float pushZ = 0f, rollX = 0f;
                    if (sticks)
                    {   // the stock driver: localEulerAngles = (pitch x range, 0, -roll x range); pitch > 0 = PUSH (stock CI-22 / SFB-81 sign, the 1.8.12 lesson)
                        var sd = (Transform)G(js[0], "transform"); var mf = sd.GetComponentInChildren<MeshFilter>();
                        var top0 = mf.transform.TransformPoint(mf.sharedMesh.bounds.center + Vector3.up * mf.sharedMesh.bounds.extents.y);
                        var r0 = sd.localRotation; float rg = (float)G(js[0], "range");
                        sd.localEulerAngles = new Vector3(1f * rg, 0f, 0f); var top1 = mf.transform.TransformPoint(mf.sharedMesh.bounds.center + Vector3.up * mf.sharedMesh.bounds.extents.y);
                        sd.localEulerAngles = new Vector3(0f, 0f, -1f * rg); var top2 = mf.transform.TransformPoint(mf.sharedMesh.bounds.center + Vector3.up * mf.sharedMesh.bounds.extents.y);
                        sd.localRotation = r0;
                        pushZ = inst.transform.InverseTransformDirection(top1 - top0).z; rollX = inst.transform.InverseTransformDirection(top2 - top0).x;
                    }
                    R("stock sticks on Cockpit.joysticks: push (pitch > 0) = stick top FORWARD, roll right = top right; the stock throttle on Cockpit.throttles moves forward at full (1.9.1 EW-25 / 1.9.5 SFB-81 parts; ControlCheck195 measures the 1.9.5 parts in detail)",
                        sticks && pushZ > 0.01f && rollX > 0.01f && thr != null && thr.Count == 1 && throttleForward.Count == 1 && throttleForward.Values.All(v => v > 0.005f), $"push top dz {pushZ:F3}, roll right top dx {rollX:F3}, throttles {thr?.Count}, grip forward {string.Join("/", throttleForward.Values.Select(v => v.ToString("F3")))}");
                    // 1.9.1: the stock EW-25 flight deck (tub with its MFD glass, wide tac screen, sticks, throttle) on the contract anchors; live tac
                    // page on the EW-25 tac screen (Cockpit.tacScreenRender) and on screen 1 of the WSO and EWO stations; the others stock dark glass
                    bool Tac(string n) { var t = T(n); return t != null && t.GetComponent<MeshRenderer>() != null && t.GetComponent<MeshRenderer>().sharedMaterials.Any(mt => mt != null && mt.name.Contains("tacScreenDisplay")); }
                    var kit = new[] { ("cockpit_ew1_tub", "EW1_cockpit_int"), ("cockpit_ew1_tacscreen", "EW1_targetScreen"), ("stick_L", "EW1_joystick"), ("stick_R", "EW1_joystick"), ("cockpit_throttle", "EW1_throttle") };
                    var kitBad = kit.Where(k => { var t = T(k.Item1); var mf = t != null ? t.GetComponent<MeshFilter>() : null; return mf == null || mf.sharedMesh == null || !AssetDatabase.GetAssetPath(mf.sharedMesh).Contains(k.Item2 + "_PLACEHOLDER")
                        || t.GetComponent<MeshRenderer>() == null || t.GetComponent<MeshRenderer>().sharedMaterials.Length != mf.sharedMesh.subMeshCount; })
                        .Select(k => k.Item1).Where(n => !(EwScreens193 && n == "cockpit_ew1_tacscreen" && T(n) != null && T(n).GetComponent<MeshFilter>().sharedMesh.name == "cockpit_ew1_tacscreen_tac" && T(n).GetComponent<MeshRenderer>().sharedMaterials.Length == 2)).ToList();   // 1.9.3: our quads on the stock screen rectangles
                    var tacR_ = ck != null ? (Renderer)G(ck, "tacScreenRender") : null;
                    var others = inst.GetComponentsInChildren<MeshRenderer>(true).Where(r => r.name.StartsWith("cockpit_screen_") && !r.name.StartsWith("cockpit_screen_wso1") && !r.name.StartsWith("cockpit_screen_ewo1")
                        && !(StationScreens193 && (r.name.StartsWith("cockpit_screen_wso2") || r.name.StartsWith("cockpit_screen_ewo2")))).ToList();   // 1.9.3: screen 2 live too
                    bool scr = kitBad.Count == 0 && tacR_ != null && tacR_.name.StartsWith("cockpit_ew1_tacscreen") && Tac("cockpit_ew1_tacscreen") && Tac("cockpit_screen_wso1") && Tac("cockpit_screen_ewo1")
                        && (StationScreens193 ? others.Count == 0 && Tac("cockpit_screen_wso2") && Tac("cockpit_screen_ewo2") : others.Count >= 2) && others.All(r => r.sharedMaterials.All(mt => mt != null && mt.name.Contains("Touchscreen_off")))
                        && T("cockpit_ew1_tub_int") != null && T("cockpit_ew1_tub_int").gameObject.layer == 3;
                    var eyes0 = JList("crew", "stations").Select(st => T((string)st["eye"]["name"])).Where(e => e != null).ToList();
                    bool deck195 = T("cockpit_panel") != null;
                    if (!deck195)
                        R("glass cockpit (1.9.1): stock EW-25 flight deck (tub, wide tac screen, sticks, throttle) on the anchors with their own materials, live stock tac page on the EW-25 tac screen + WSO / EWO screen 1, other screens stock dark glass, cockpit-layer copy, no rudder pedals, HUD kept",
                            scr && inst.GetComponentsInChildren<Transform>(true).All(t => !t.name.Contains("pedal")) && ((AircraftDefinition)def).aircraftParameters.HUDExtras != null,
                            $"kit missing / wrong {string.Join(", ", kitBad)}; tacScreenRender {(tacR_ != null ? tacR_.name : "none")}; dark {others.Count}");
                    else
                    {   // 1.9.5: OUR deck (panel, glare shield, pedestal, consoles, floor) + single stock parts; no stock cockpit / screen-set mesh anywhere
                        var stockMeshes = inst.GetComponentsInChildren<MeshFilter>(true).Where(f => f.sharedMesh != null && AssetDatabase.GetAssetPath(f.sharedMesh).Contains("_PLACEHOLDER"))
                            .Select(f => (f.name, mesh: Path.GetFileNameWithoutExtension(AssetDatabase.GetAssetPath(f.sharedMesh)).Replace("_PLACEHOLDER", ""))).ToList();
                        var tubs = stockMeshes.Where(x => x.mesh.Contains("cockpit") || x.mesh.ToLowerInvariant().Contains("tacscreen") || x.mesh.Contains("targetScreen")).ToList();
                        var orig = stockMeshes.Where(x => !x.name.EndsWith("_int")).ToList();     // the exterior originals (each has a cockpit-view _int copy, the lamps excepted)
                        int nStick = orig.Count(x => x.mesh == "sfb_joystick" && x.name.StartsWith("stick_")), nThr = orig.Count(x => x.mesh == "sfb_throttle" && x.name.StartsWith("cockpit_throttle"));
                        int nLamp = orig.Count(x => x.mesh == "EW1_warningLights"), nSeat = orig.Count(x => x.mesh == "ejectionSeat");
                        bool ours = new[] { "cockpit_panel", "cockpit_glareshield", "cockpit_pedestal", "cockpit_console_L", "cockpit_console_R", "cockpit_interior", "cockpit_overhead" }
                            .All(n => T(n) != null && T(n).GetComponent<MeshRenderer>() != null && !AssetDatabase.GetAssetPath(T(n).GetComponent<MeshFilter>().sharedMesh).Contains("_PLACEHOLDER") && T(n + "_int") != null && T(n + "_int").gameObject.layer == 3);
                        bool mats = new[] { "stick_L", "stick_R" }.All(n => T(n).GetComponent<MeshRenderer>().sharedMaterials.Select(m => m.name.Replace("_PLACEHOLDER", "")).SequenceEqual(new[] { "hotas", "SFB_cockpit" }))
                            && T("cockpit_throttle").GetComponent<MeshRenderer>().sharedMaterials.Single().name.Replace("_PLACEHOLDER", "") == "SFB_cockpit";
                        R("1.9.5 own flight deck: our panel / glare shield / pedestal / consoles / floor / overhead (cockpit-layer copies) with single stock parts - sfb_joystick x2, sfb_throttle x1 (stock materials), EW1_warningLights x2, ejectionSeat x4 on the figures; NO stock cockpit tub or stock screen-set mesh; no rudder pedals, HUD kept",
                            ours && mats && tubs.Count == 0 && nStick == 2 && nThr == 1 && nLamp == 2 && nSeat >= 4 && inst.GetComponentsInChildren<Transform>(true).All(t => !t.name.Contains("pedal")) && ((AircraftDefinition)def).aircraftParameters.HUDExtras != null,
                            $"ours {ours}, stock mats {mats}; tubs / screen sets {string.Join(", ", tubs.Select(x => x.name + "=" + x.mesh))}; sticks {nStick}, throttle {nThr}, lamps {nLamp}, seats {nSeat}");
                        var cwl = inst.GetComponentsInChildren<global::CockpitWarningLights>(true).ToList();
                        var lamps = cwl.Count == 1 ? ((Renderer[])G(cwl[0], "lightRenderers")).ToList() : new List<Renderer>();
                        var ckL = ((Renderer[])G(ac, "cockpitRenderers")).ToList(); var exL = ((Renderer[])G(ac, "exteriorRenderers")).ToList();
                        R("1.9.5 missile-warning lamps: the stock CockpitWarningLights (aircraft set) drives the two EW1_warningLights renderers, layer 14 (CockpitAndExternal, the stock lamps' layer), in neither cockpitRenderers nor exteriorRenderers (nothing else switches them), each on its glare-shield lip in front of a pilot",
                            !WarnLamps195 || (cwl.Count == 1 && G(cwl[0], "aircraft") as Aircraft == ac && lamps.Count == 2 && lamps.All(r => r.gameObject.layer == 14 && !ckL.Contains(r) && !exL.Contains(r)
                                && r.bounds.center.y > eyes0.Max(e => e.position.y) - 0.40f && Mathf.Abs(Mathf.Abs(r.bounds.center.x) - 0.38f) < 0.02f)),
                            $"{cwl.Count} blinker(s), lamps {string.Join(", ", lamps.Select(r => r.name + " " + r.bounds.center.ToString("F3") + " layer " + r.gameObject.layer))}");
                        var gs = T("cockpit_glareshield").GetComponent<MeshRenderer>().bounds; var pn = T("cockpit_panel").GetComponent<MeshRenderer>().bounds;
                        {   // 1.9.6 detail pass: legends / lamps are emissive, untextured, and only on our deck parts; the deck carries modelled controls
                            var emis = new[] { "ck_legend", "ck_amber", "ck_green" }.Select(k6 => MSB1780Build.mats.TryGetValue(k6, out var mm6) ? mm6 : null).ToList();
                            var users = inst.GetComponentsInChildren<MeshRenderer>(true).Where(r6 => r6.sharedMaterials.Any(m6 => emis.Contains(m6))).Select(r6 => r6.name).Distinct().ToList();
                            int legendTris = inst.GetComponentsInChildren<MeshFilter>(true).Where(f6 => !f6.name.EndsWith("_int") && f6.sharedMesh != null && f6.GetComponent<MeshRenderer>() != null)
                                .Sum(f6 => { var r6 = f6.GetComponent<MeshRenderer>(); int t6 = 0; for (int i6 = 0; i6 < r6.sharedMaterials.Length && i6 < f6.sharedMesh.subMeshCount; i6++) if (emis.Contains(r6.sharedMaterials[i6])) t6 += (int)f6.sharedMesh.GetIndexCount(i6) / 3; return t6; });
                            R("1.9.6 cockpit detail: backlit legends / annunciator lamps on emissive untextured materials (ck_legend / ck_amber / ck_green), only on our deck parts (panel, glare shield, pedestal, consoles, overhead + their cockpit copies)",
                                emis.All(m6 => m6 != null && m6.IsKeywordEnabled("_EMISSION") && m6.GetTexture("_BaseMap") == null) && users.Count > 0 && users.All(n6 => n6.StartsWith("cockpit_")) && legendTris >= 400,
                                $"{legendTris} legend / lamp triangles on {string.Join(", ", users.Where(n6 => !n6.EndsWith("_int")))}");
                        }
                        R("1.9.5 glare shield stops at the panel ends (its half width <= the panel's), the overhead strip keeps the 1.9.2 rule (row below)",
                            gs.extents.x <= pn.extents.x + 0.001f && Mathf.Abs(gs.center.x) < 0.002f, $"shield half width {gs.extents.x:F3}, panel {pn.extents.x:F3}");
                    }
                }
                {   // 1.9.2 rows (fixes from the first in-game test of 1.9.0)
                    var eyes = JList("crew", "stations").Select(st => T((string)st["eye"]["name"])).Where(e => e != null).ToList();
                    var ckList = ((Renderer[])G(ac, "cockpitRenderers")).ToList(); var exList = ((Renderer[])G(ac, "exteriorRenderers")).ToList();
                    var bad = new List<string>(); int nTac = 0;
                    foreach (var r in inst.GetComponentsInChildren<MeshRenderer>(true).Where(r => r.sharedMaterials.Any(mt => mt != null && mt.name.Contains("tacScreenDisplay"))))
                    {   // each live tac screen: content triangles (submesh 0) face a crew eye within 1.6 m, UVs inside the texture; the _int copy is a
                        // cockpit-view renderer (layer 3, in cockpitRenderers), the original an exterior one (hidden in cockpit view)
                        nTac++;
                        var mf = r.GetComponent<MeshFilter>(); var mesh = mf.sharedMesh; var tri = mesh.GetTriangles(0); var vs = mesh.vertices; var uv = mesh.uv;
                        var c = r.transform.TransformPoint(vs[tri[0]]); var nrm = r.transform.TransformDirection(Vector3.Cross(vs[tri[1]] - vs[tri[0]], vs[tri[2]] - vs[tri[0]])).normalized;
                        bool faces = eyes.Any(e => (e.position - c).magnitude < 1.6f && Vector3.Dot(nrm, (e.position - c).normalized) > 0.3f);
                        bool uvOk = tri.All(i => uv[i].x >= -0.001f && uv[i].x <= 1.001f && uv[i].y >= -0.001f && uv[i].y <= 1.001f);
                        bool isInt = r.name.EndsWith("_int");
                        bool view = isInt ? (r.gameObject.layer == 3 && ckList.Contains(r)) : exList.Contains(r);
                        if (!faces || !uvOk || !view) bad.Add($"{r.name}(faces {faces}, uv {uvOk}, view {view})");
                    }
                    var tacPrefab = G(inst.GetComponentInChildren<global::Cockpit>(true), "tacScreenUIPrefab") as GameObject;
                    R("1.9.2 MFDs: every live tac screen (EW-25 wide screen, WSO / EWO screen 1, their cockpit-view copies) faces a crew eye, UVs inside the render texture, copies on the cockpit layer in cockpitRenderers, originals in exteriorRenderers; the tac page is the CI-22 prop page (tacScreen_cricket, as the B-25H / GA-25X)",
                        nTac >= 6 && bad.Count == 0 && tacPrefab != null && tacPrefab.name.Contains("cricket"), $"{nTac} tac renderers, prefab {(tacPrefab != null ? tacPrefab.name : "none")}; bad {string.Join(", ", bad)}");
                    var csps192 = inst.GetComponentsInChildren<ConstantSpeedProp>(true).ToList();
                    R("1.9.2 props: propTorqueLimit per row >= the torque of the row's nominal power at 0.85 x rpmLimit (1.9.0: 15 kN m capped each row at ~1.6 MW, 79 % of the engine; tools/flightmodel/msb1780_fm.py)",
                        csps192.Count == 8 && csps192.All(p => (float)G(p, "propTorqueLimit") >= (float)G(p, "nominalPower") * 9.5488f / (0.85f * (float)G(p, "rpmLimit")) - 1f),
                        string.Join(", ", csps192.Select(p => $"{(float)G(p, "propTorqueLimit"):F0}")));
                    var wing = allParts.First(p => p.name == "wing_inner_L"); var stab = allParts.First(p => p.name == "stab_L");
                    float incS = Mathf.Asin(((Transform)G(stab, "liftNormal")).forward.y) * Mathf.Rad2Deg;
                    R($"1.9.2 cruise trim: wing lift frames at {WingIncidence} deg incidence (plus dihedral), stabilisers at {StabIncidence}; alpha limiter + incidence = CLmax angle {WingCLmaxDeg}",
                        Mathf.Abs(Mathf.Asin(((Transform)G(wing, "liftNormal")).forward.y) * Mathf.Rad2Deg - WingIncidence) < 0.3f && Mathf.Abs(incS - StabIncidence) < 0.1f && Mathf.Abs(AlphaLimiter + WingIncidence - WingCLmaxDeg) < 0.01f,
                        $"wing {Mathf.Asin(((Transform)G(wing, "liftNormal")).forward.y) * Mathf.Rad2Deg:F2}, stab {incS:F2}");
                    var abk = inst.GetComponentsInChildren<global::Airbrake>(true).ToList();
                    R($"1.9.2 airbrake: one stock Airbrake on the root part, dragAmount {AirbrakeDrag} (opens at throttle 0), no transforms (drag only)",
                        !Airbrake192 || (abk.Count == 1 && abk[0].gameObject == inst && Mathf.Approximately((float)G(abk[0], "dragAmount"), AirbrakeDrag) && G(abk[0], "part") as UnitPart == allParts.First(p => p.gameObject == inst)),
                        $"{abk.Count} airbrakes");
                    var hlds = inst.GetComponentsInChildren<HighLiftDevice>(true).ToList();
                    var prm2 = ((AircraftDefinition)def).aircraftParameters;
                    R($"1.9.2 AI landing: landingSpeed {AiLandingSpeed} (1.9.3 touchdown value; 1.9.2 had 74), approach {AiApproachSpeed} (not read by the game); flaps down below {FlapSpeedDown}, up from {FlapSpeedUp} m/s (unchanged)",
                        prm2.landingSpeed == AiLandingSpeed && prm2.approachSpeed == AiApproachSpeed && hlds.Count == 4 && hlds.All(h => (float)G(h, "speedDeployed") == FlapSpeedDown && (float)G(h, "speedRetracted") == FlapSpeedUp),
                        $"landing {prm2.landingSpeed}, approach {prm2.approachSpeed}, {hlds.Count} flaps");
                    if (LaserBeam197 && LaserTurrets190)
                    {   // 1.9.7: BEAM-line sweep (LaserSweep197.cs) + the saved Laser.maxAngle in both mount prefabs
                        var zMa = stationSets.Where(x => x.station == "Dorsal" || x.station == "Ventral").Select(x => x.ammo.prefab).Where(zp => zp != null).Select(zp => zp.GetComponentInChildren<Laser>(true)).Where(zl => zl != null).Select(zl => (float)G(zl, "maxAngle")).ToList();
                        var zAfter = LaserSweep197.CheckInstance(inst, LaserBeamAngle197); var zBefore = LaserSweep197.CheckInstance(inst, LaserSweep197.StockAngle);
                        foreach (var zr in zBefore) L("  1.9.7 beam sweep BEFORE " + zr);
                        foreach (var zr in zAfter) L("  1.9.7 beam sweep AFTER  " + zr);
                        R($"1.9.7 laser beam = bore line: Laser.maxAngle {LaserBeamAngle197} on both lasers (stock Laser_EW1 30); beam sweep over every target direction: 0 damage lines (solid own colliders) on the turret's own fire path; the pilot / AI trigger path keeps only the elevation-clamp residual (<= 12 lines, the plugin guard's job) against hundreds at 30",
                            zMa.Count == 2 && zMa.All(m => Mathf.Approximately(m, LaserBeamAngle197)) && zAfter.Count == 2 && zAfter.All(LaserSweep197.Clean) && zBefore.Sum(zr => zr.pilotCol) > 50 * Mathf.Max(1, zAfter.Sum(zr => zr.pilotCol)),
                            $"maxAngle [{string.Join(", ", zMa)}]; after: {string.Join("; ", zAfter)} | at the 1.9.6 angle 30: turret path {zBefore.Sum(zr => zr.turretCol)} damage / {zBefore.Sum(zr => zr.turretDisc)} prop-disc / {zBefore.Sum(zr => zr.turretMesh)} mesh-only lines, pilot path {zBefore.Sum(zr => zr.pilotCol)} / {zBefore.Sum(zr => zr.pilotDisc)} / {zBefore.Sum(zr => zr.pilotMesh)} [{string.Join(" | ", zBefore.Select(zr => zr.Top))}]");
                    }
                    var tl = inst.GetComponentsInChildren<Turret>(true).Where(t => t.name.StartsWith("top_") || t.name.StartsWith("ball_")).ToList();
                    R("1.9.2 lasers: traverse 150 deg/s (stock HLT; Turret.AimTurret elevates only while |traverse error| < 45 deg), elevation 60 deg/s, dorsal el 0..90 / ventral -90..0 in an upright frame (el forward level, up = mount up)",
                        tl.Count == 2 && tl.All(t => Mathf.Approximately((float)G(t, "traverseRate"), LaserTraverseRate)) && tl.All(t => { var el = (Transform)G(t, "elevationTransform"); return Vector3.Dot(el.up, t.transform.up) > 0.999f && Mathf.Abs(el.forward.y) < 0.01f; }),
                        string.Join(", ", tl.Select(t => $"{t.name} {(float)G(t, "traverseRate")} el {(float)G(t, "minElevation")}..{(float)G(t, "maxElevation")}")));
                    var oh = T("cockpit_overhead"); var ohB = oh != null ? oh.GetComponent<MeshRenderer>().bounds : new Bounds();
                    float eyeZ = eyes.Take(2).Min(e => e.position.z), eyeY = eyes.Take(2).Min(e => e.position.y);
                    R("1.9.2 overhead console: entirely aft of both pilot eyes (out of the forward view) and >= 0.15 m above eye level, no wider than 0.26 m",
                        oh != null && ohB.max.z < eyeZ - 0.05f && ohB.min.y > eyeY + 0.15f && ohB.size.x <= 0.26f, $"console z {ohB.min.z:F2}..{ohB.max.z:F2} y {ohB.min.y:F2}..{ohB.max.y:F2} x {ohB.size.x:F2}; pilot eye z {eyeZ:F2} y {eyeY:F2}");
                }
                {   // 1.9.3 rows (fixes from the in-game test of 1.9.2)
                    var prm3 = ((AircraftDefinition)def).aircraftParameters;
                    var lg3 = inst.GetComponentsInChildren<LandingGear>(true).ToList();
                    var tail3 = lg3.FirstOrDefault(g => (bool)G(g, "steering"));
                    var mainsL = lg3.Where(g => g.name.StartsWith("gear_main_L")).ToList();
                    float mainC = mainsL.Sum(g => (float)G(g, "dampingRate")), mainK = mainsL.Sum(g => (float)G(g, "springRate"));
                    R($"1.9.3 AI touchdown: landingSpeed {AiLandingSpeed} (adjusted + 1..+5 m/s lands near the 3-point attitude at 29-42 t, tools/flightmodel/msb1780_touchdown.py), main damping {MainC:F0} per wheel (braked + grip), spring {MainK:F0} unchanged, tail k {TailK:F0} / c {TailC:F0} / break {TailMaxComp}",
                        !AiTouchdown193 || (prm3.landingSpeed == AiLandingSpeed && prm3.shortLandingSpeed == AiLandingSpeed && Mathf.Abs(AiLandingSpeed - 56.5f) < 1e-4f
                        && (!GearDamp193 || (mainsL.Count == 2 && Mathf.Abs(mainC - 2.9e5f) < 1f && Mathf.Abs(mainK - 2.4e6f) < 1f && tail3 != null && Mathf.Abs((float)G(tail3, "springRate") - 6.5e5f) < 1f
                        && Mathf.Abs((float)G(tail3, "dampingRate") - 6.0e4f) < 1f && Mathf.Abs((float)G(tail3, "maxCompression") - 0.36f) < 1e-4f))),
                        $"landing {prm3.landingSpeed}, main L c {mainC:F0} k {mainK:F0} ({mainsL.Count} legs), tail k {(tail3 != null ? G(tail3, "springRate") : "-")} c {(tail3 != null ? G(tail3, "dampingRate") : "-")} break {(tail3 != null ? G(tail3, "maxCompression") : "-")}");
                    var ewT = T("cockpit_ew1_tacscreen"); var ewI = T("cockpit_ew1_tacscreen_int");
                    var ewM = ewT != null ? ewT.GetComponent<MeshFilter>().sharedMesh : null;
                    bool ewOk = !EwScreens193 || (ewM != null && ewM.name == "cockpit_ew1_tacscreen_tac" && ewI != null && ewI.GetComponent<MeshFilter>().sharedMesh == ewM
                        && ewScreensFound == 11 && ewScreensLive == 6 && ewScreensDark == 5 && ewLayoutOk && ewM.subMeshCount == 2 && ewM.GetTriangles(1).Length == 11 * 6
                        && ewM.GetTriangles(0).Length == (2 * 1 + 2 * 2 + 2 * 1) * 6 && ewScreenLog.Count(x => x.StartsWith("outer") && x.EndsWith("map")) == 2
                        && ewScreenLog.Count(x => x.StartsWith("inner") && x.EndsWith("panels12")) == 2 && ewScreenLog.Count(x => x.StartsWith("lower centre") && x.EndsWith("panel3")) == 2
                        && ewT.GetComponent<MeshRenderer>().sharedMaterials.Length == 2 && ewT.GetComponent<MeshRenderer>().sharedMaterials[1].name.Contains("Touchscreen_off"));
                    if (T("cockpit_panel") == null)
                        R("1.9.3 EW-25 screens: 11 stock screen rectangles (2 outer, 2 inner, 2 lower centre, 2 lower outer, 2 side, 1 top) with our own quads; live: outer = CI-22 tac map, inner = power + engine-dial panels, lower centre = attitude panel; the other 5 dark glass; every content quad inside its screen at the page's aspect",
                            ewOk, string.Join("; ", ewScreenLog));
                    else
                    {   // 1.9.5: per pilot a map (outboard) and power + engine dials (inboard), the attitude in the centre, the standby glass dark; the
                        // content quads built by StationScreenMesh (throws when a quad leaves its screen); cockpit-view copies the same mesh
                        var tq = new Dictionary<string, int> { { "map", 6 }, { "panels12", 12 }, { "panel3", 6 }, { "dark", 0 } };
                        string stby = (string)contract["deck195"]["screens"]["cockpit_screen_deck_stbyC"];      // 1.9.6: the standby shows the live attitude page (1.9.5: dark)
                        var want = new Dictionary<string, (string c, int t0)> { { "mapL", ("map", 6) }, { "mapR", ("map", 6) }, { "sysL", ("panels12", 12) }, { "sysR", ("panels12", 12) }, { "attC", ("panel3", 6) }, { "stbyC", (stby, tq[stby]) } };
                        var bad5 = new List<string>();
                        foreach (var kv in want)
                        {
                            var t = T("cockpit_screen_deck_" + kv.Key); var ti = T("cockpit_screen_deck_" + kv.Key + "_int");
                            if (t == null || ti == null) { bad5.Add(kv.Key + " missing"); continue; }
                            var mr = t.GetComponent<MeshRenderer>(); var sm5 = t.GetComponent<MeshFilter>().sharedMesh;
                            bool ok = ti.GetComponent<MeshFilter>().sharedMesh == sm5 && deckScreenLog.TryGetValue(t.name, out var c5) && c5 == kv.Value.c;
                            if (kv.Value.c == "dark") ok &= mr.sharedMaterials.Length == 1 && mr.sharedMaterials[0].name.Contains("Touchscreen_off");
                            else ok &= sm5.subMeshCount == 2 && sm5.GetTriangles(0).Length == kv.Value.t0 && sm5.GetTriangles(1).Length == 6 && mr.sharedMaterials[0].name.Contains("tacScreenDisplay") && mr.sharedMaterials[1].name.Contains("Touchscreen_off");
                            if (!ok) bad5.Add(kv.Key);
                        }
                        var ckT = inst.GetComponentInChildren<global::Cockpit>(true); var tacR5 = ckT != null ? (Renderer)G(ckT, "tacScreenRender") : null;
                        R("1.9.5 deck screens: 6 MFD units - map L / R (whole tac map), power + engine dials L / R, attitude centre (live CI-22 page), standby centre (1.9.6: live attitude; 1.9.5: dark glass); content quads inside each screen at the page's aspect; cockpit-view copies share the mesh; Cockpit.tacScreenRender = the pilot's map",
                            !Deck195Screens || (bad5.Count == 0 && deckScreenLog.Count == 6 && tacR5 != null && tacR5.name == "cockpit_screen_deck_mapL"),
                            $"bad {string.Join(", ", bad5)}; {string.Join("; ", deckScreenLog.Select(kv => kv.Key.Replace("cockpit_screen_deck_", "") + " " + kv.Value))}; tacScreenRender {(tacR5 != null ? tacR5.name : "none")}");
                    }
                    var stOk = !StationScreens193 || (stationScreenLog.Count == 8 && new[] { "wso", "ewo" }.All(k =>
                    {
                        var a = T("cockpit_screen_" + k + "1"); var b = T("cockpit_screen_" + k + "2");
                        if (a == null || b == null) return false;
                        var ma = a.GetComponent<MeshFilter>().sharedMesh; var mb = b.GetComponent<MeshFilter>().sharedMesh;
                        return ma.GetTriangles(0).Length == 6 && mb.GetTriangles(0).Length == 18 && ma.GetTriangles(1).Length == 6 && mb.GetTriangles(1).Length == 6
                            && T("cockpit_screen_" + k + "1_int") != null && T("cockpit_screen_" + k + "1_int").GetComponent<MeshFilter>().sharedMesh.GetTriangles(0).Length == 6
                            && T("cockpit_screen_" + k + "2_int") != null && T("cockpit_screen_" + k + "2_int").GetComponent<MeshFilter>().sharedMesh.GetTriangles(0).Length == 18;
                    }));
                    R("1.9.3 station screens: WSO / EWO screen 1 = the tac map alone, screen 2 = the three tac panels (power, engine dials, attitude); cockpit-view copies the same",
                        stOk, string.Join(", ", stationScreenLog.Select(kv => kv.Key + " " + kv.Value)));
                }
                var ckR = (Renderer[])G(ac, "cockpitRenderers");
                R("cockpit layer copies, glass copies use the faint glass (no canopy_int)", ckR != null && ckR.Length > 6 && ckR.All(r => r.gameObject.layer == 3) && ckR.SelectMany(r => r.sharedMaterials).All(mt => mt == null || mt.shader == null || !mt.shader.name.Contains("canopy_int")), $"{ckR?.Length} renderers");
                {
                    var radar = inst.GetComponentInChildren<Radar>(true); var jam = inst.GetComponentInChildren<RadarJammer>(true); var fe = inst.GetComponentInChildren<FlareEjector>(true);
                    var ps = inst.GetComponentInChildren<PowerSupply>(true);
                    float rr = radar != null ? new SerializedObject(radar).FindProperty("RadarParameters.maxRange").floatValue : 0f;
                    bool ok = (!Radar190 || Mathf.Abs(rr - RadarRange) < 1f) && (!RadarJammer190 || (jam != null && Mathf.Approximately((float)G(jam, "powerUsage"), JammerPowerKW)))
                        && fe != null && fe.ammo == FlareCount && ((IList)G(fe, "ejectionPoints")).Count == 4 && ps != null && ((GameObject[])G(ps, "powerSources")).Length == 4;
                    R("radar 60 km (EW-25 values), EW-25 jammer 50 kW, 120 flares from 4 dispensers (no player auto-release), power from all four engines", ok,
                        $"radar {rr / 1000f:F0} km, jammer {(jam != null ? G(jam, "powerUsage") : "none")} kW, flares {fe?.ammo} x {(fe != null ? ((IList)G(fe, "ejectionPoints")).Count : 0)}, power sources {(ps != null ? ((GameObject[])G(ps, "powerSources")).Length : 0)}");
                }
                var prm = ((AircraftDefinition)def).aircraftParameters;
                R("airfoils: wing / tail / aileron / flap (+ rudder, 1.9.4); ailerons use the aileron curve, flaps the flap curve", prm.airfoils.Length == (RudderAirfoil194 ? 5 : 4) && allParts.Where(p => p.name.StartsWith("aileron")).All(p => (int)G(p, "airfoil") == 2) && allParts.Where(p => p.name.StartsWith("flap_")).All(p => (int)G(p, "airfoil") == 3), string.Join(", ", prm.airfoils.Select(a => a.name)));
                var fbw = new SerializedObject(inst.GetComponentInChildren<ControlsFilter>(true));
                float lim = fbw.FindProperty("flyByWire.alphaLimiter").floatValue;
                R("FBW: g 4.5, alpha limiter + wing incidence = wing CLmax angle (16 deg), roll trim off (contra-rotating rows), AB-4 yaw law (weathervaning 0.05, tightness 3)",
                    Mathf.Abs(lim + WingIncidence - WingCLmaxDeg) < 0.05f && Mathf.Abs(fbw.FindProperty("flyByWire.gLimitPositive").floatValue - 4.5f) < 1e-4f && fbw.FindProperty("flyByWire.rollTrimLimit").floatValue == 0f
                    && Mathf.Abs(fbw.FindProperty("flyByWire.yawWeathervaning").floatValue - FbwYawWeathervaning) < 1e-5f, $"{lim} + {WingIncidence}");
                {
                    var fin = allParts.FirstOrDefault(p => p.name == "fin"); var rud = allParts.FirstOrDefault(p => p.name == "rudder");
                    var rcs = rud != null ? rud.GetComponent<ControlSurface>() : null;
                    R("engine-out tail: fin 9.0 + rudder 6.0 m2, rudder throw 30 deg, fin on the tail curve", fin != null && rud != null && Mathf.Abs((float)G(fin, "wingArea") - FinArea) < 0.01f && Mathf.Abs((float)G(rud, "wingArea") - RudderArea) < 0.01f && rcs != null && Mathf.Abs(Mathf.Abs((float)G(rcs, "yawRange")) - RudderThrow) < 0.01f
                        && (int)G(fin, "airfoil") == 1, rcs != null ? $"rudder yawRange {G(rcs, "yawRange")}" : "no rudder surface");
                    // 1.9.4: the rudder's own curve == the tail curve over the shared samples (|t| <= 0.2945 rad: every rudder use below 16.9 deg unchanged), odd, 1.85 at 30 deg
                    bool rOk194 = rud != null && (int)G(rud, "airfoil") == RudderAirfoil;
                    string rDet194 = rud != null ? $"rudder airfoil {(int)G(rud, "airfoil")} {prm.airfoils[(int)G(rud, "airfoil")].name}" : "no rudder";
                    if (RudderAirfoil194 && rOk194)
                    {
                        var rc194 = prm.airfoils[4].liftCoef; var tc194 = prm.airfoils[1].liftCoef;
                        float maxShared194 = 0f, maxOdd194 = 0f;
                        for (int i194 = 0; i194 < 128; i194++)
                        {
                            float t194 = (i194 - 64) * 0.04908734f;
                            if (Mathf.Abs(t194) <= 0.2946f) maxShared194 = Mathf.Max(maxShared194, Mathf.Abs(rc194.Evaluate(t194) - tc194.Evaluate(t194)));
                            maxOdd194 = Mathf.Max(maxOdd194, Mathf.Abs(rc194.Evaluate(t194) + rc194.Evaluate(-t194)));
                        }
                        float at30194 = rc194.Evaluate(0.5236f), tail30194 = tc194.Evaluate(0.5236f);
                        rOk194 = prm.airfoils[4].name == "MSB17_rudder" && maxShared194 < 1e-4f && maxOdd194 < 1e-4f && Mathf.Abs(at30194 - 1.848f) < 0.01f && Mathf.Abs(tail30194 - 0.822f) < 0.01f
                            && Mathf.Abs(prm.airfoils[4].dragCoef.Evaluate(0.3f) - prm.airfoils[1].dragCoef.Evaluate(0.3f)) < 1e-6f;
                        rDet194 += $", shared-sample diff {maxShared194:F6}, odd {maxOdd194:F6}, CL at 30 deg {at30194:F3} (tail {tail30194:F3})";
                    }
                    R("1.9.4 rudder curve: own airfoil 4 'MSB17_rudder' == the tail curve to 16.9 deg, then the control-surface curve (1.85 at 30 deg, tail 0.82); tail drag (msb1780_engineout.py: VMC 71 -> 56 m/s)", rOk194, rDet194);
                }
                R("every part (props excepted) has its own ImpactDamage", allParts.Where(p => !p.name.StartsWith("prop_")).All(p => { var x = G(p, "impactDamage"); return x != null && (float)G(x, "threshold") > 0f; }), "");
                var noJ = allParts.Where(p => p.transform != inst.transform && (p.Joints == null || p.Joints.Length == 0)).Select(p => p.name).ToList();
                var wr = allParts.Where(p => p.name.StartsWith("wing_inner")).Select(p => p.Joints == null || p.Joints.Length == 0 ? 0f : p.Joints.Max(j => j.breakForce)).ToList();
                R("joints: wing roots >= 1 MN class (2.2 x the B-17G), every part jointed", wr.Count == 2 && wr.All(f => f >= 1000000f) && noJ.Count == 0, $"wing roots {string.Join("/", wr)}; without joints: {string.Join(",", noJ)}");
                var fuel = inst.GetComponentsInChildren<FuelTank>(true);
                {
                    var bad = new List<string>();
                    foreach (var f in fuel)
                    {
                        var up = f.GetComponent<AeroPart>();
                        if (up == null || (UnitPart)G(f, "part") != up) bad.Add(f.name + " not on its part");
                    }
                    string[] must = { "wing_inner_L", "wing_mid_L", "wing_outer_L", "wing_inner_R", "wing_mid_R", "wing_outer_R", "nacelle_1", "nacelle_2", "nacelle_3", "nacelle_4", "MSB17", "fus_waist" };
                    foreach (var mn in must) if (!fuel.Any(f => f.name.Replace("(Clone)", "") == mn)) bad.Add("no tank on " + mn);
                    var wi = fuel.FirstOrDefault(f => f.name == "wing_inner_L");
                    bool sealed_ = !SelfSealing190 || (wi != null && (float)G(wi, "leakPerHP") <= tplWingLeakPerHP190 * 0.51f + 1e-6f);
                    R("fuel 10,000 kg in 12 linked AB-4-style tanks on their parts; self-sealing (half the leak per hit point / leak rate, 1.5 x the ignition thresholds)",
                      Mathf.Abs(fuel.Sum(f => (float)G(f, "fuelCapacity")) - FuelKg) < 1f && bad.Count == 0 && sealed_, $"{fuel.Length} tanks {fuel.Sum(f => (float)G(f, "fuelCapacity")):F0} kg; {string.Join("; ", bad.Take(8))}");
                }
                // @@LOOK@@
                {
                    var rs_ = inst.GetComponentsInChildren<MeshRenderer>(true);
                    var ourStruct = rs_.Where(r_ => r_.gameObject.layer != 3 && r_.sharedMaterials.Any(m_ => m_ != null && (m_.name == "MSB17_structure" || m_.name == "MSB17_engine"))).Select(r_ => r_.name).ToList();
                    var stockStruct = rs_.Where(r_ => r_.sharedMaterials.Any(m_ => StockStructure.IsStructMat(m_))).ToList();
                    bool vcolS = stockStruct.All(r_ => { var mm = r_.GetComponent<MeshFilter>().sharedMesh; return mm.colors32.Length == mm.vertexCount; });
                    R("internals (B-17G 1.8.3 method): spars, ribs, frames, stringers, carry-through, turboshaft cores / mounts drawn with the stock aircraft_structure (vertex colour); none left on our structure / engine materials",
                      !StockStructure.Enabled || (ourStruct.Count == 0 && stockStruct.Count >= 20 && vcolS), $"{stockStruct.Count} stock-structure renderers; ours left on: {string.Join(", ", ourStruct.Take(6))}");
                }
                R("AI parameters set (comment-swallow guard): PIDReferenceAirspeed 140, maxSpeed 215, takeoffSpeed 52, takeoffDistance 1000, minimumRadarAlt 3000, groundTurningRadius 30", prm.PIDReferenceAirspeed == 140f && prm.maxSpeed == 215f && prm.takeoffSpeed == 52f && prm.takeoffDistance == 1000f && prm.minimumRadarAlt == AiMinRadarAlt && prm.groundTurningRadius == 30f && prm.landingSpeed == AiLandingSpeed, "");
                var liv = prm.liveries;
                R("liveries: 2 per faction (BDF Matte Gray / Temperate, PALA Desert / Matte Black), none shared", liv.Count == 4 && liv.Where(l => l.name.StartsWith("BDF")).All(l => l.faction == liv[0].faction) && liv.Where(l => l.name.StartsWith("PALA")).All(l => l.faction != liv[0].faction) && liv.Count(l => l.name.StartsWith("BDF")) == 2,
                    string.Join(", ", liv.Select(l => l.name + "/" + (l.faction == liv[0].faction ? "BDF" : "PALA"))));
                R("standard loadouts: 8 (strike, precision, SEAD, anti-ship, nuclear, stand-off, bunker, air defence), each one entry per hardpoint set", prm.StandardLoadouts.Length == 8 && prm.StandardLoadouts.All(s => s.loadout.weapons.Count == wm.hardpointSets.Length), string.Join(" | ", prm.StandardLoadouts.Select(s => s.Name)));
                // @@STRAY_MESH@@
