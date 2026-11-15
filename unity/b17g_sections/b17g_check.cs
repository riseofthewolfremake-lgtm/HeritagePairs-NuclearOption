        static bool RunCheck(GameObject prefab)
        {
            var rows = new List<(string name, bool ok, string detail)>();
            void R(string n, bool ok, string d) => rows.Add((n, ok, d));
            var inst = (GameObject)Object.Instantiate(prefab);
            try
            {
                {   // 1.8.16 livery-atlas guard (AtlasGuard1816.cs = blender/atlas_guard.py): the skin / livery / damage textures were painted on THIS UV0 atlas
                    var ag = AtlasGuard1816.Check(inst, mats["paint"], Path.Combine(RepoTextures, "b17g_atlas_manifest.json"), new Dictionary<string, string> { { "fus_center", "B17G" } });
                    R("1.8.16 livery atlas: UV0 of the paint meshes == the texture manifest (textures painted on this atlas, files unchanged)", ag.Item1, ag.Item2);
                }
                var ac = inst.GetComponent<Aircraft>();
                var allParts = inst.GetComponentsInChildren<AeroPart>(true);
                Transform T(string n) => inst.GetComponentsInChildren<Transform>(true).FirstOrDefault(x => x.name == n);
                // identity
                var def = ac.definition;
                R("definition: B17G, rank 3, $45m, 31.62 x 22.66 m, hangar_med only, 3-point rest rotation",
                    def != null && def.jsonKey == JsonKey && ((AircraftDefinition)def).aircraftParameters.rankRequired == 3 && Mathf.Abs(def.value - 45f) < 0.01f && Mathf.Abs(def.width - 31.62f) < 0.01f
                    && (!SpawnThreePoint || ((AircraftDefinition)def).restRotation.x < -5f), $"spawn y {def?.spawnOffset.y:F3}, rest {((AircraftDefinition)def)?.restRotation}");
                float m = allParts.Sum(p => p.mass);
                R("mass: parts 22-26 t (16.4 t empty + crew, ammo, 50 % fuel), encyclopedia empty 16,390 kg", m > 22000f && m < 26000f && Mathf.Abs(((AircraftDefinition)def).aircraftInfo.emptyWeight - 16390f) < 1f, $"{m:F0} kg");
                // engines / props
                var props = inst.GetComponentsInChildren<ConstantSpeedProp>(true);
                var trs = props.Select(p => (Transmission)G(p, "transmission")).ToList();
                R("4 props, 4 own Transmissions + TurbineEngines (an engine kill stops only its prop)", props.Length == 4 && trs.Distinct().Count() == 4 && trs.All(t => t != null && t.GetComponent<TurbineEngine>() != null), string.Join(", ", trs.Select(t => t?.name)));
                R("each prop: 3 blades, own trigger PropStrikeDetector (layer 15), R 1.70-1.80 m", props.All(p => ((IList)G(p, "blades")).Count == 3 && G(p, "propStrikeDetector") is PropStrikeDetector d && d.gameObject.layer == 15 && Mathf.Abs((float)G(p, "bladeLength") - 1.765f) < 0.06f),
                    string.Join(", ", props.Select(p => $"{p.name}: {((IList)G(p, "blades")).Count} blades R {(float)G(p, "bladeLength"):F2}")));
                var engs = inst.GetComponentsInChildren<TurbineEngine>(true);
                R($"engines at game power {EnginePower / 1e6f:F2} MW each (1.6.3 performance tuning), messages ENGINE 1-4 FIRE", engs.Length == 4 && engs.All(e => Mathf.Abs(e.maxPower - EnginePower) < 1f) && engs.Select(e => (string)G(e, "failureMessage")).OrderBy(x => x).SequenceEqual(new[] { "ENGINE 1 FIRE", "ENGINE 2 FIRE", "ENGINE 3 FIRE", "ENGINE 4 FIRE" }),
                    string.Join(", ", engs.Select(e => $"{e.name}:{G(e, "failureMessage")}{(G(e, "failureMessageAudio") != null ? "+voice" : "")}")));
                // prop disc vs fuselage colliders (0.15 m rule, checked on the Unity colliders)
                var fusCols = allParts.Where(p => p.name == "B17G" || p.name.StartsWith("fus_")).Select(p => p.GetComponent<MeshCollider>()).Where(c => c != null).ToList();
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
                {   // 1.8.9 (offline J; docs/damage_model_study.md): the damage map's ALPHA is the shader's hole map (discard below 0.52 - 0.02 / D).
                    // The 1.8.0 row only tested darkening; the 1.8.0 map had a flat alpha 0.6 (no hole ever opened). Now: skin coverage at HP 80 / 50 / 0
                    // inside the stock bands, the paint material uses the maps, the imported texture keeps its alpha.
                    var dmgPath = Path.Combine(RepoTextures, "b17g_skin_dmg_b.png");
                    var hc = DamageHoles189.Check(dmgPath, tex.ContainsKey("b17g_skin_dmg_b") ? tex["b17g_skin_dmg_b"] : null);
                    var pm = mats["paint"];
                    R("1.8.9 skin damage HOLES: dmg_b alpha opens 5-13 / 10-27 / 15-30 % of the skin at HP 80 / 50 / 0 (stock bands), paint material uses dmg_b / dmg_n, alpha kept on import",
                        hc.Item1 && File.Exists(Path.Combine(RepoTextures, "b17g_skin_dmg_n.png")) && pm.GetTexture("_BasecolorDmg") == tex["b17g_skin_dmg_b"] && pm.GetTexture("_NormalDmg") == tex["b17g_skin_dmg_n"], hc.Item2);
                }
                R(ANM2Guns ? "1.8.13 AN/M2 guns: the stock barrel no longer used (kept as the fallback; its bore read from its vertex data)" : "1.8.0 gun barrels on their slots: the stock barrel's bore read from its vertex data (not the bounds centre: 8 cm right, 2 cm high in 1.7.x); bore within 1 cm of the mesh centreline",
                    ANM2Guns || (!barrelTipSource.StartsWith("bounds") && Mathf.Abs(barrelTip.x) < 0.01f && barrelTip.y > 0f && barrelTip.y < 0.08f && barrelTip.z > 1.0f),
                    $"bore ({barrelTip.x:F3}, {barrelTip.y:F3}, {barrelTip.z:F3}) from {barrelTipSource}");
                R("prop tips >= 0.15 m from the fuselage colliders", worst >= 0.15f, $"min {worst:F3} m");
                // gear
                var gears = inst.GetComponentsInChildren<LandingGear>(true).Where(g => !g.name.EndsWith(GripGear.Suffix)).ToArray();   // 1.8.0: grip partners in their own row
                var mains = gears.Where(g => g.name.StartsWith("gear_main")).ToList(); var tailg = gears.FirstOrDefault(g => g.name.StartsWith("gear_tail"));
                {
                    bool gok = GripGear.Verify(inst, MainBrakeShare, MainFriction, MainK, out string gd);
                    R($"1.8.0 split mains: braked + unbraked grip LandingGear per wheel on one contact, frictionCoef {MainFriction} both, braked share {MainBrakeShare} -> braking {MainFriction * MainBrakeShare:F3} x load = BrakeFriction {BrakeFriction}, side grip {MainFriction} x load (1.7.13 0.22)",
                        !SplitMainGear || (gok && Mathf.Abs(MainFriction * MainBrakeShare - BrakeFriction) < 1e-4f), gd);
                }
                R("gear: 2 braked mains + 1 steerable tailwheel, k / damping sized for 25 t (k of braked + grip)", mains.Count == 2 && tailg != null && mains.All(g => (bool)G(g, "braked") && (float)G(g, "springRate") >= 1.2e6f * (SplitMainGear ? MainBrakeShare : 1f)) && (bool)G(tailg, "steering"),
                    string.Join(", ", gears.Select(g => $"{g.name} k {(float)G(g, "springRate"):F0} c {(float)G(g, "dampingRate"):F0} fold {(float)G(g, "foldDegrees")}")));
                bool foldOk = true; var foldDetail = new List<string>();
                foreach (var g in gears)
                {
                    var h = (Transform)G(g, "gearHinge"); var wv = ((Transform[])G(g, "wheels"))[0];
                    var p0 = wv.position; var r0 = h.localRotation;
                    h.localRotation = r0 * Quaternion.Euler((float)G(g, "foldDegrees"), 0, 0);
                    var p1 = wv.position; h.localRotation = r0;
                    bool fwdUp = g.name.StartsWith("gear_main") ? (p1.z > p0.z + 0.8f && p1.y > p0.y + 1.0f) : (p1.y > p0.y + 0.3f);
                    foldOk &= fwdUp; foldDetail.Add($"{g.name}: wheel moves ({p1.x - p0.x:F2}, {p1.y - p0.y:F2}, {p1.z - p0.z:F2})");
                }
                R("gear folds: mains forward + up into the nacelles, tailwheel up into the tail", foldOk, string.Join("; ", foldDetail));
                // nose-over margin (noseover.py rule) and 3-point attitude from the built prefab
                var com = inst.transform.InverseTransformPoint(allParts.Aggregate(Vector3.zero, (s, p) => s + p.transform.TransformPoint(p.GetComponent<MeshCollider>() ? p.GetComponent<MeshCollider>().sharedMesh.bounds.center : Vector3.zero) * p.mass) / m);
                var mAx = inst.transform.InverseTransformPoint(((Transform)G(mains[0], "axle")).position); var tAx = inst.transform.InverseTransformPoint(((Transform)G(tailg, "axle")).position);
                float contactY = mAx.y - 0.711f, d = mAx.z - com.z, hh = com.y - contactY;
                float tailUp = Mathf.Atan2(d, hh) * Mathf.Rad2Deg, three = Mathf.Atan2((tAx.y - 0.33f) - contactY, mAx.z - tAx.z) * Mathf.Rad2Deg;
                R($"nose-over: tail-up CoM angle >= brake friction angle + 3 deg (coordinator 1.6.1 target; noseover.py; friction {BrakeFriction})", tailUp >= Mathf.Atan(BrakeFriction) * Mathf.Rad2Deg + 3.0f, $"CoM {com.ToString("F2")} (parts collider centres), axle z {mAx.z:F2}: {tailUp:F1} deg");
                R("3-point attitude 7-11 deg (restRotation spawns in it)", three > 7f && three < 11f, $"{three:F1} deg");
                // round 3 (user: tail assembly spun, no steering). LandingGear.cs 556-558 spins every `wheels` transform about local X;
                // 718-724 steers `unsprung` about local Y. A wheel transform may only carry a round tyre about its own axle.
                {
                    var bad = new List<string>(); var det = new List<string>();
                    foreach (var g in gears)
                        foreach (var wv in (Transform[])G(g, "wheels"))
                        {
                            float rr = (float)G(g, "wheelRadius"), maxR = 0f, maxOff = 0f; int nv = 0;
                            foreach (var mf in wv.GetComponentsInChildren<MeshFilter>(true))
                            {
                                if (mf.sharedMesh == null) continue;
                                foreach (var v in mf.sharedMesh.vertices) { var lp = wv.InverseTransformPoint(mf.transform.TransformPoint(v)); maxR = Mathf.Max(maxR, new Vector2(lp.y, lp.z).magnitude); nv++; }
                                var bc = wv.InverseTransformPoint(mf.transform.TransformPoint(mf.sharedMesh.bounds.center)); maxOff = Mathf.Max(maxOff, new Vector2(bc.y, bc.z).magnitude);
                            }
                            if (nv == 0 || maxR > rr * 1.06f || maxOff > 0.03f) bad.Add(wv.name);
                            det.Add($"{wv.name}: radius {maxR:F3}/{rr:F3}, off-axle {maxOff:F3}");
                        }
                    R("wheels spin-safe: each LandingGear wheel carries only a round tyre about its own axle (no fork / strut in a spinning transform)", bad.Count == 0, string.Join("; ", det));
                }
                {
                    var tl = tailg; float lockv = (float)G(tl, "steeringLock"), fr = (float)G(tl, "frictionCoef"), al = (float)G(tl, "aligningStrength"), sp = (float)G(tl, "steeringSpeed");
                    var uns = ((GameObject)G(tl, "unsprung")).transform;
                    var fork = T("fork_tail");
                    var u0 = uns.localRotation; uns.localEulerAngles = new Vector3(0f, 1f * lockv, 0f);          // full right rudder (yaw +1)
                    float headX = inst.transform.InverseTransformDirection(uns.forward).x; uns.localRotation = u0;
                    bool behind = tAx.z < com.z;
                    bool noseRight = behind ? headX < -0.05f : headX > 0.05f;          // a wheel behind the CG must point LEFT for a right turn
                    var right = mains.FirstOrDefault(x => inst.transform.InverseTransformPoint(((Transform)G(x, "axle")).position).x > 0f);
                    bool diffOk = right != null && (float)G(right, "differentialBrakeFactor") > 0f;
                    float wb = mAx.z - tAx.z, lockAbs = Mathf.Abs(lockv), eff5 = Mathf.Min(lockAbs, sp / (0.5f * Mathf.Max(al, 0.01f)));
                    float rFull = wb / Mathf.Tan(lockAbs * Mathf.Deg2Rad), r5 = wb / Mathf.Tan(eff5 * Mathf.Deg2Rad);
                    bool forkOk = fork != null && fork.parent == uns && !((Transform[])G(tl, "wheels")).Contains(fork);
                    R("tailwheel steering (taildragger, Nimrod / FD-32 technique): lock < 0 behind the CG -> right rudder turns the nose right; stock side grip >= 0.6; fork rides unsprung; right main brakes on right rudder; turn radius <= 25 m at 5 m/s",
                        noseRight && fr >= 0.6f && forkOk && diffOk && r5 <= 25f,
                        $"lock {lockv} (wheel {(behind ? "behind" : "ahead of")} the CoM), wheel heading x {headX:F2} at yaw +1, friction {fr}, aligning {al}, speed {sp}; fork parent {(fork != null ? fork.parent.name : "missing")}; wheelbase {wb:F2} m: R {rFull:F1} m at full lock, {r5:F1} m at 5 m/s (effective {eff5:F0} deg); mains friction {BrakeFriction}");
                }
                // ===== 1.6.1 rows (in-game catalogue of 1.6.0) =====
                {   // (13) colliders: PhysX cooks a convex hull of at most 255 polygons; ours come from <= 96 support points (hull <= 188 faces)
                    var big = inst.GetComponentsInChildren<MeshCollider>(true).Where(c => c.convex && c.sharedMesh != null && c.sharedMesh.vertexCount > 100).Select(c => $"{c.name} {c.sharedMesh.vertexCount}v").ToList();
                    int n = inst.GetComponentsInChildren<MeshCollider>(true).Count(c => c.convex);
                    R("convex colliders cook whole: <= 100 hull points each (<= 196 faces, PhysX cap 255; 1.6.0 Player.log: partial hulls on 8 B17G parts)", big.Count == 0, $"{n} convex colliders; over: {string.Join(", ", big.Take(6))}");
                }
                {   // (1) ground handling numbers from the prefab (LandingGear.cs 546-555 brakes, 331-342 soft ground, 718-724 steering)
                    float mass = allParts.Sum(p => p.mass), W = mass * 9.81f;
                    float zt = tAx.z, zm = mAx.z, zc = com.z;
                    float Nt = W * (zm - zc) / (zm - zt), Nm = W - Nt;
                    float mu = BrakeFriction, decel = mu * Nm / mass, hold = mu * Nm;
                    float tailUpDeg = Mathf.Atan2(zm - zc, com.y - (mAx.y - 0.711f)) * Mathf.Rad2Deg, muDeg = Mathf.Atan(mu) * Mathf.Rad2Deg;
                    float area = (float)G(mains[0], "contactArea") / (SplitMainGear ? Mathf.Pow(MainBrakeShare, 0.75f) : 1f), press = (Nm / 2f) / (area * 1e4f), depth = press * 0.003f / 5f;
                    float grass = 2.5f * depth * depth * 33f * press * press;     // per main at 33 m/s (119 km/h), typical ground noise num3 = 5
                    float overturn = 2f * grass * (com.y - (mAx.y - 0.711f)), restore = W * (zm - zc);
                    float wb = zm - zt, lockAbs = Mathf.Abs((float)G(tailg, "steeringLock")), rTurn = wb / Mathf.Tan(lockAbs * Mathf.Deg2Rad);
                    bool ok = decel >= 1.8f && tailUpDeg - muDeg >= 3f && grass <= 0.15f * Nm / 2f && overturn < 0.5f * restore && rTurn <= 30f && (float)G(tailg, "aligningStrength") == 0f;
                    R("ground handling: braking >= 1.8 m/s2 (1.7.3), nose-over margin >= 3 deg, grass drag at 33 m/s <= 15 % of the wheel load, taxi radius <= 30 m, tailwheel not castering",
                        ok, $"mass {mass:F0} kg, mains {Nm / 1e3:F0} kN / tail {Nt / 1e3:F0} kN; braking {decel:F2} m/s2 (mu {mu}), brake hold {hold / 1e3:F0} kN; tail-up {tailUpDeg:F1} deg vs atan(mu) {muDeg:F1} (margin {tailUpDeg - muDeg:F1}); contact {area:F3} m2 (single-gear equivalent of the split) -> {press:F0} N/cm2, grass drag {grass / 1e3:F1} kN per main (pitch-down moment {overturn / 1e3:F0} vs weight {restore / 1e3:F0} kNm); full-lock radius {rTurn:F1} m");
                }
                // physics queries on the instance (bail-out spots, crew inside the hull)
                Physics.SyncTransforms();
                {   // (10) bail-out: PilotDismounted.FindDismountSpot (PilotDismounted.cs 518-540) needs a spot 2..10 m to the side of the crew
                    //      member's part with nothing above it within 10 m; the down cast (20 m) must not land it on our own wing / tail
                    var det = new List<string>(); bool ok = ac.pilots != null && ac.pilots.Length == 10;
                    foreach (var pl in ac.pilots ?? new Pilot[0])
                    {
                        var up_ = pl.GetUnitPart(); var pt = up_ != null ? up_.transform : null;
                        if (pt == null) { ok = false; det.Add($"{pl.name}: no part"); continue; }
                        int sign = pl.exitDirection != Pilot.ExitDirection.Left ? 1 : -1; Vector3 spot = pt.position; int k = 1; bool found = false;
                        for (; k < 10; k++)
                        {
                            spot = pt.position + pt.right * (k + 1) * sign;
                            if (!Physics.Linecast(spot + Vector3.up * 10f, spot)) { found = true; break; }
                            sign = -sign;
                        }
                        bool landsOnUs = Physics.Linecast(spot, spot - Vector3.up * 20f, out var hdn) && hdn.collider != null && hdn.collider.transform.IsChildOf(inst.transform);
                        bool okp = !landsOnUs; ok &= okp;
                        det.Add($"{pl.name}:{(found ? $"{k + 1}m" : "NONE")}{(landsOnUs ? " ON " + hdn.collider.name : "")}");
                    }
                    R("bail-out: 10 crew; FindDismountSpot (incl. its 10 m fallback when every spot has airframe above) never drops a crew member onto our own airframe (spot found / NONE = fallback)", ok, string.Join(", ", det));
                }
                {   // (4) every crew vertex inside the hull: from each vertex, rays +-X and +-Y (4 m) against every airframe mesh (back faces on)
                    var tmp = new List<GameObject>(); int layer = 31;
                    var figs = new HashSet<Transform>((ac.pilots ?? new Pilot[0]).Select(p => p.transform));
                    foreach (var mf in inst.GetComponentsInChildren<MeshFilter>(true))
                    {
                        if (mf.sharedMesh == null || figs.Any(f => mf.transform.IsChildOf(f))) continue;
                        var go = new GameObject("hullprobe"); go.layer = layer; go.transform.SetPositionAndRotation(mf.transform.position, mf.transform.rotation); go.transform.localScale = mf.transform.lossyScale;
                        var mc = go.AddComponent<MeshCollider>(); mc.sharedMesh = mf.sharedMesh; mc.convex = false; tmp.Add(go);
                    }
                    Physics.SyncTransforms();
                    bool back = Physics.queriesHitBackfaces; Physics.queriesHitBackfaces = true;
                    var det = new List<string>(); bool ok = true; int mask = 1 << layer;
                    var right = inst.transform.right; var upv = inst.transform.up;
                    // round 5 (user review 2: legs still out in game after 1.6.1): the in-game pose is NOT the prefab's bind pose - each
                    // figure's Animator plays the stock PilotController 'seated' state (and 'deadCockpit' when the crew member dies). Both
                    // clips are sampled onto the figures (AnimationMode) before baking, so this check sees what the game shows.
                    var poseClips = new List<AnimationClip>();
                    foreach (var pl0 in ac.pilots ?? new Pilot[0])
                    {
                        var an0 = pl0.GetComponentInChildren<Animator>(true);
                        if (an0 != null && an0.runtimeAnimatorController != null)
                            foreach (var cl in an0.runtimeAnimatorController.animationClips)
                                if (cl != null && (cl.name.StartsWith("seated") || cl.name.StartsWith("deadCockpit")) && !poseClips.Contains(cl)) poseClips.Add(cl);
                    }
                    det.Add($"poses sampled: {(poseClips.Count > 0 ? string.Join("/", poseClips.Select(c => c.name)) : "NONE (no controller)")}");
                    ok &= poseClips.Count >= 2;
                    foreach (var poseClip in poseClips)
                    foreach (var pl in ac.pilots ?? new Pilot[0])
                    {
                        var anim = pl.GetComponentInChildren<Animator>(true);
                        if (anim != null)
                        {
                            if (!AnimationMode.InAnimationMode()) AnimationMode.StartAnimationMode();
                            AnimationMode.BeginSampling(); AnimationMode.SampleAnimationClip(anim.gameObject, poseClip, 0.03f); AnimationMode.EndSampling();
                        }
                        int outside = 0, total = 0; Vector3 worstV = Vector3.zero; string worstWhy = "";
                        var ballBody = pl.name == "crew_ball" ? inst.GetComponentsInChildren<Transform>(true).FirstOrDefault(t => t.name == "ball_el") : null;   // the ball gunner sits in the ball (open windows): sphere test
                        foreach (var smr in pl.GetComponentsInChildren<SkinnedMeshRenderer>(true))
                        {
                            var baked = new Mesh(); smr.BakeMesh(baked);
                            foreach (var v in baked.vertices)
                            {
                                var p = smr.transform.position + smr.transform.rotation * v; total++;      // BakeMesh: renderer space without its scale
                                if (ballBody != null) { if ((p - ballBody.position).magnitude > 0.57f) { outside++; worstV = p; } continue; }
                                bool r1 = Physics.Raycast(p, right, 4f, mask), r2 = Physics.Raycast(p, -right, 4f, mask);
                                bool u1 = Physics.Raycast(p, upv, 4f, mask), hd = Physics.Raycast(p, -upv, 4f, mask);
                                bool hx = r1 && r2, hy = u1 || hd;
                                if (!(hx && hy && hd)) { outside++; worstV = p; worstWhy = (r1 ? "" : "R") + (r2 ? "" : "L") + (hd ? "" : "D") + (hy ? "" : "U"); }   // 1.8.17: which rays left
                            }
                            Object.DestroyImmediate(baked);
                        }
                        bool okp = total > 0 && outside == 0; ok &= okp;
                        if (!okp || pl == ac.pilots[0]) det.Add($"{poseClip.name}: {pl.name} {outside}/{total}" + (okp ? "" : $" e.g. {inst.transform.InverseTransformPoint(worstV).ToString("F2")} misses {worstWhy}"));
                    }
                    if (AnimationMode.InAnimationMode()) AnimationMode.StopAnimationMode();
                    Physics.queriesHitBackfaces = back;
                    foreach (var go in tmp) Object.DestroyImmediate(go);
                    R("crew inside the hull in the game's animated poses (seated + deadCockpit sampled): every figure vertex has airframe on both sides and below (0 outside)", ok, string.Join("; ", det));
                }
                // weapons
                var wm = ac.weaponManager;
                var bayS = wm.hardpointSets.FirstOrDefault(x => x.name == "Bomb Bay");
                R("bomb bay: 8 x PAB-250 / 4 x GPO-500 / 2 x CBO-400 (own enabled copy) / GPO-N, every non-nuclear option allowed (WeaponMount.IsAllowed), two BayDoors", bayS != null && bayS.weaponOptions.Skip(1).Select(o => o.name.Replace("_PLACEHOLDER", "")).SequenceEqual(new[] { "bomb_250_internalx8", "bomb_500_internalx4_stack", "B17G_cbo400_x2", "nuclearBomb1_internal" })
                    && bayS.weaponOptions.Skip(1).Where(o => o.info == null || !o.info.nuclear).All(o => o.IsAllowed(false))
                    && bayS.hardpoints[0].bayDoors.Length == 2, bayS == null ? "" : string.Join(", ", bayS.weaponOptions.Skip(1).Select(o => o.name)));
                bool doorsOk = true; var dd = new List<string>();
                foreach (var bd in bayS.hardpoints[0].bayDoors)
                {
                    var tr = bd.transform; var mf = tr.GetComponentInChildren<MeshFilter>(); var c0 = mf.transform.TransformPoint(mf.sharedMesh.bounds.center);
                    var r0 = tr.localRotation; tr.localEulerAngles = new Vector3(0, 0, (float)G(bd, "hingeAngle")); var c1 = mf.transform.TransformPoint(mf.sharedMesh.bounds.center); tr.localRotation = r0;
                    bool ok = c1.y < c0.y - 0.15f && Mathf.Abs(c1.x) > Mathf.Abs(c0.x) + 0.3f; doorsOk &= ok; dd.Add($"{tr.name}: centre moves ({c1.x - c0.x:F2}, {c1.y - c0.y:F2})");
                }
                R("bay doors open down and out", doorsOk, string.Join("; ", dd));
                var tur = inst.GetComponentsInChildren<Turret>(true);
                var guns = tur.SelectMany(t => ((Transform[])G((Gun)G(t, "aimSafetyWeapon"), "muzzles"))).Count();
                var infos = tur.Select(t => ((Gun)G(t, "aimSafetyWeapon")).info).Distinct().ToList();
                R("9 gun positions, 13 x 12.7 mm, 5 stations (one WeaponInfo per station)", tur.Length == 9 && guns == 13 && infos.Count == 5 && wm.hardpointSets.Count(x => x.name.EndsWith(" guns")) == 5,
                    string.Join(", ", infos.Select(i => i.weaponName)));
                R("exclusion firing cones from the offline turret scan", !TurretExclusionCones || exclusionConeCount > 0, $"{exclusionConeCount} cones");
                // round 3 turret audit (Turret.cs 715-716: az localEulerAngles = (0, trav, 0), el = (elev, 0, 0) absolutely; Gun.cs 634: bullets
                // leave every muzzle along muzzle.forward): parenting, rest frames, muzzle axis = el axis, muzzles at the stock barrel tips,
                // bodies on the moving parts, a usable share of the envelope inside the firing cones
                {
                    var det = new List<string>(); bool ok = true;
                    foreach (var t in tur)
                    {
                        var az = t.transform; var el = (Transform)G(t, "elevationTransform"); var mount = az.parent;
                        var gun = el.GetComponent<Gun>(); var mz = gun != null ? (Transform[])G(gun, "muzzles") : new Transform[0];
                        bool par = gun != null && el.parent == az && mount != null && mount.name.EndsWith("_mount") && mz.Length > 0 && mz.All(x => x.IsChildOf(el));
                        bool rest = Quaternion.Angle(az.localRotation, Quaternion.identity) < 0.5f && Quaternion.Angle(el.localRotation, Quaternion.identity) < 0.5f;
                        float dirErr = 0f, tipErr = 0f;
                        foreach (var x in mz)
                        {
                            dirErr = Mathf.Max(dirErr, Vector3.Angle(x.forward, el.forward));
                            var mf = x.parent != null ? x.parent.GetComponentsInChildren<MeshFilter>(true).FirstOrDefault(f => f.sharedMesh != null && (f.sharedMesh.name.StartsWith("50cal") || f.sharedMesh.name.Contains("_anm2_") && !f.sharedMesh.name.EndsWith("grips"))) : null;
                            if (mf != null) tipErr = Mathf.Max(tipErr, (mf.transform.TransformPoint(mf.sharedMesh.name.Contains("_anm2_") ? new Vector3(0f, 0f, mf.sharedMesh.bounds.max.z) : BarrelTip(mf.sharedMesh)) - x.position).magnitude);
                        }
                        // envelope share inside the cones (5-deg grid over traverse x elevation, as Turret.AimTurret clamps)
                        var cones = (FiringCone[])G(t, "firingCones"); int tot = 0, inside = 0;
                        float tr = Mathf.Min((float)G(t, "traverseRange"), 180f), e0 = (float)G(t, "minElevation"), e1 = (float)G(t, "maxElevation");
                        for (float a = -tr; a <= tr + 0.01f; a += 5f)
                            for (float e = e0; e <= e1 + 0.01f; e += 5f)
                            {
                                var dir = mount.rotation * (Quaternion.Euler(0f, a, 0f) * (Quaternion.Euler(-e, 0f, 0f) * Vector3.forward)); tot++;
                                if (FiringConeChecker.VectorWithinFiringCones(cones, dir, out var _)) inside++;
                            }
                        float share = tot > 0 ? (float)inside / tot : 0f;
                        bool tOk = par && rest && dirErr < 1f && tipErr < 0.12f && share >= 0.4f; ok &= tOk;
                        det.Add($"{mount?.name}: {(par ? "" : "PARENT ")}{(rest ? "" : "REST ")}muzzle axis {dirErr:F1} deg, tip {tipErr:F2} m, envelope in cones {share * 100f:F0} %");
                    }
                    var bodies = new[] { ("topturret_body", "top_az"), ("ballturret_body", "ball_el"), ("chinturret_body", "chin_az"), ("tailmantlet_body", "tail_az") };   // round 5: the Cheyenne cover turns in azimuth, the guns elevate in its slots
                    foreach (var (b, host) in bodies) { var bt = T(b); var ht = T(host); bool bo = bt != null && ht != null && bt.IsChildOf(ht); ok &= bo; if (!bo) det.Add($"{b} NOT under {host}"); }
                    R("turret kinematics: mount > az > el > gun > muzzle, az / el rest at identity, muzzles along el +Z at the stock barrel tips, bodies on az / el, >= 40 % of each envelope inside its cones", ok, string.Join("; ", det));
                }
                if (FireClear1814On && DefensiveTurrets)
                {   // 1.8.14 (offline M): the saved cones re-swept on this instance with the game's own FiringConeChecker
                    var fc14 = FireClear1814.CheckInstance(inst);
                    R("1.8.14 fire clearance: no aim direction where a turret may fire into our own airframe (game FiringConeChecker + 1 deg onTarget; colliders, meshes, prop discs; 1 deg grid, posed muzzles)", fc14.bad == 0, fc14.detail);
                }
                if (ANM2Guns)
                {   // 1.8.13: 13 AN/M2 bodies (twins L + R, singles by feed side), grips on the 7 hand-held guns (tail twin, cheeks, waists, radio), none on chin / top / ball
                    var bodies2 = inst.GetComponentsInChildren<MeshFilter>(true).Where(f => f.sharedMesh != null && f.sharedMesh.name.StartsWith("B17G_anm2_") && !f.sharedMesh.name.EndsWith("grips")).ToList();
                    // round 2: powered turrets carry the turret gun (short slide, buffer stub), hand-held positions the flexible gun (lever + knob)
                    bool kinds = bodies2.All(f => (f.name.StartsWith("chin_") || f.name.StartsWith("top_") || f.name.StartsWith("ball_")) == f.sharedMesh.name.Contains("_turret_"));
                    var gripsN = inst.GetComponentsInChildren<MeshFilter>(true).Count(f => f.sharedMesh != null && f.sharedMesh.name == "B17G_anm2_grips");
                    bool noStock = !inst.GetComponentsInChildren<MeshFilter>(true).Any(f => f.sharedMesh != null && f.sharedMesh.name.StartsWith("50cal"));
                    bool turretNoGrips = bodies2.Where(f => f.name.StartsWith("chin_") || f.name.StartsWith("top_") || f.name.StartsWith("ball_")).All(f => f.transform.childCount == 0);
                    bool twinsLR = new[] { "chin", "top", "ball", "tail" }.All(s => bodies2.Count(f => f.name.StartsWith(s + "_gun0") && f.sharedMesh.name.EndsWith("_L")) == 1 && bodies2.Count(f => f.name.StartsWith(s + "_gun1") && f.sharedMesh.name.EndsWith("_R")) == 1);
                    R("1.8.13 AN/M2 on every gun slot: 13 bodies (twins gun_L + gun_R), turret guns on chin / top / ball, flexible guns + grips on the 7 hand-held, no stock door-gun barrel left", bodies2.Count == 13 && gripsN == 7 && noStock && turretNoGrips && twinsLR && kinds,
                        $"{bodies2.Count} bodies ({bodies2.Count(f => f.sharedMesh.name.EndsWith("_L"))} L / {bodies2.Count(f => f.sharedMesh.name.EndsWith("_R"))} R), {gripsN} grips, turret / flex kinds {(kinds ? "ok" : "WRONG")}, stock barrels left {(noStock ? 0 : 1)}");
                }
                else
                R("stock 12.7 mm barrel mesh on every gun slot", tur.All(t => ((Gun)G(t, "aimSafetyWeapon")).GetComponentsInChildren<MeshFilter>(true).Any(f => f.sharedMesh != null && f.sharedMesh.name.StartsWith("50cal"))) || inst.GetComponentsInChildren<MeshFilter>(true).Count(f => f.sharedMesh != null && f.sharedMesh.name.StartsWith("50cal")) == 13,
                    $"{inst.GetComponentsInChildren<MeshFilter>(true).Count(f => f.sharedMesh != null && f.sharedMesh.name.StartsWith("50cal"))} barrels");
                // crew / cockpit
                R("crew of 10, bail-out (no ejection seats), own figures", ac.pilots.Length == 10 && ac.pilots.All(p => p != null && !(bool)G(p, "ejectionSeat")), string.Join(", ", ac.pilots.Select(p => p.name)));
                R("cockpit view point = the left-seat pilot eye", ac.cockpitViewPoint != null && ac.cockpitViewPoint.position.x < -0.2f, ac.cockpitViewPoint ? ac.cockpitViewPoint.position.ToString("F2") : "none");
                var ck = inst.GetComponentInChildren<global::Cockpit>(true);
                var thr = ck != null ? (IList)G(ck, "throttles") : null;
                R("4 throttle levers on Cockpit.throttles, grips move forward at full throttle", thr != null && thr.Count == 4 && throttleForward.Count == 4 && throttleForward.Values.All(v => v > 0.03f), string.Join(", ", throttleForward.Select(k => $"{k.Key} +{k.Value:F2} m")));
                if (ColumnPlugin189)
                {   // 1.8.9 (user on 1.8.8: "The WHEEL moves, the stick does not"): no Cockpit.joysticks; B25H.Instruments pitches the columns about
                    // their floor pivots and turns the wheels about their hub axes (B17G.cs ColumnDeg = -pitch x 12, WheelDeg = roll x 30, about local +X).
                    // Same formula here on the built instance (the full proof with no-yaw rows: unity/Editor/ColumnCheck189.cs)
                    var jl = ck != null ? ((IEnumerable)G(ck, "joysticks")).Cast<object>().ToList() : new List<object>();
                    var det = new List<string>(); bool ok = jl.Count == 0;
                    foreach (var side in new[] { "L", "R" })
                    {
                        var col = T("cockpit_column_" + side); var yk = T("cockpit_yoke_" + side);
                        if (col == null || yk == null || !yk.IsChildOf(col)) { ok = false; det.Add(side + ": column / wheel missing or not nested"); continue; }
                        var cR = col.localRotation; var yR = yk.localRotation; var hub0 = inst.transform.InverseTransformPoint(yk.position); var top0 = inst.transform.InverseTransformPoint(yk.position + yk.up * 0.1f);
                        col.localRotation = cR * Quaternion.AngleAxis(12f, Vector3.right); var hubPush = inst.transform.InverseTransformPoint(yk.position); col.localRotation = cR;
                        yk.localRotation = yR * Quaternion.AngleAxis(30f, Vector3.right); var topRoll = inst.transform.InverseTransformPoint(yk.position + yk.up * 0.1f); yk.localRotation = yR;
                        bool o = hubPush.z - hub0.z > 0.08f && topRoll.x - top0.x > 0.02f; ok &= o;
                        det.Add($"{side}: push moves the hub {(hubPush.z - hub0.z) * 1000:F0} mm forward, roll right the wheel top {(topRoll.x - top0.x) * 1000:F0} mm right");
                    }
                    bool noCS = !inst.GetComponentsInChildren<ControlSurface>(true).Any(c => c.name.StartsWith("cockpit_"));
                    R("1.8.9 columns + wheels moved by B25H.Instruments (no Cockpit.joysticks): push = column forward about the floor pivot carrying the wheel, roll right = wheel top right, no cockpit ControlSurfaces", ok && noCS, string.Join("; ", det));
                }
                else
                {   // 1.6.1: wheels on Cockpit.joysticks (stock stick driver); a full right roll turns each wheel's top to the right
                    var jl = ck != null ? ((IEnumerable)G(ck, "joysticks")).Cast<object>().ToList() : new List<object>();
                    var det = new List<string>(); bool ok = jl.Count == 2;
                    foreach (var j in jl)
                    {
                        var t = (Transform)G(j, "transform"); float rg = (float)G(j, "range");
                        var wheel = t.GetComponentsInChildren<Transform>(true).FirstOrDefault(x => x.name.StartsWith("cockpit_yoke_") && !x.name.Contains("_js"));
                        bool rest = Quaternion.Angle(t.localRotation, Quaternion.identity) < 0.5f;
                        var topRest = t.position + t.up * 0.2f;
                        var r0 = t.localRotation; t.localEulerAngles = new Vector3(0f, 0f, -1f * rg); var top1 = t.position + t.up * 0.2f; t.localRotation = r0;
                        var topRolled = inst.transform.InverseTransformPoint(top1).x - inst.transform.InverseTransformPoint(topRest).x;
                        bool okj = wheel != null && rest && rg >= 20f && topRolled > 0.05f; ok &= okj;
                        det.Add($"{t.name}: range {rg}, wheel {(wheel ? wheel.name : "missing")}, rest {(rest ? "identity" : "NOT identity")}, full right roll moves the wheel top {topRolled:F2} m right");
                    }
                    bool noCS = !inst.GetComponentsInChildren<ControlSurface>(true).Any(c => c.name.StartsWith("cockpit_"));
                    R("yokes: 2 wheels on Cockpit.joysticks (stock stick driver, as the Nimrod / FD-32 sticks), roll right = wheel top right, no cockpit ControlSurfaces", ok && noCS, string.Join("; ", det));
                }
                var needles = inst.GetComponentsInChildren<Transform>(true).Count(t => t.name.StartsWith("gauge_") && (t.name.EndsWith("_needle") || t.name.EndsWith("_card") || t.name.EndsWith("_short")));
                R("40 gauge movers present (B25H.Instruments 1.8.4 B17G branch drives them by name; 19 until 1.8.3 + 21 formerly static dials)", needles == 40, $"{needles}");
                R("no rudder pedals, no screens", inst.GetComponentsInChildren<Transform>(true).All(t => !t.name.Contains("pedal")) && inst.GetComponentsInChildren<Transform>(true).All(t => !t.name.StartsWith("mfd_")), "");
                var ckR = (Renderer[])G(ac, "cockpitRenderers");
                R("cockpit layer copies, glass copies use the faint glass (no canopy_int)", ckR != null && ckR.Length > 10 && ckR.All(r => r.gameObject.layer == 3) && ckR.SelectMany(r => r.sharedMaterials).All(mt => mt == null || mt.shader == null || !mt.shader.name.Contains("canopy_int")), $"{ckR?.Length} renderers");
                R("HUD kept (COIN_HUDExtras)", ((AircraftDefinition)def).aircraftParameters.HUDExtras != null, "");
                { string abBad = InvisibleAirbrakeProblems(inst, InvisibleAirbrake1912, InvisibleAirbrakeDrag, InvisibleAirbrakeOpenSpeed, out string abDet); R("1.9.12 invisible airbrake: " + (InvisibleAirbrake1912 ? $"exactly one stock Airbrake, on the root object, part = the root part, dragAmount {InvisibleAirbrakeDrag}, openSpeed {InvisibleAirbrakeOpenSpeed}, maxAngle 0, no transforms (drag only, no parts), no sound, constraints not null, aircraft set" : "flag off, no Airbrake in the prefab"), abBad == "", abDet + (abBad == "" ? "" : "; WRONG: " + abBad)); }   // 1.9.12, ONE line in place of the "// flight model" comment: msb1780_sections/compose_check.py copies blocks of this file BY LINE NUMBER, so the line count must stay 499. Flight model rows follow
                var prm = ((AircraftDefinition)def).aircraftParameters;
                R("airfoils: wing / tail / aileron / flap; ailerons use the aileron curve, flaps the flap curve", prm.airfoils.Length == 4 && allParts.Where(p => p.name.StartsWith("aileron")).All(p => (int)G(p, "airfoil") == 2) && allParts.Where(p => p.name.StartsWith("flap_")).All(p => (int)G(p, "airfoil") == 3), string.Join(", ", prm.airfoils.Select(a => a.name)));
                var fbw = new SerializedObject(inst.GetComponentInChildren<ControlsFilter>(true));
                float lim = fbw.FindProperty("flyByWire.alphaLimiter").floatValue;
                R("alpha limiter + wing incidence = wing CLmax angle (16 deg)", Mathf.Abs(lim + WingIncidence - WingCLmaxDeg) < 0.05f, $"{lim} + {WingIncidence}");
                {   // 1.7.8 lateral (spiral + AI weave): handed props, no FBW roll trim, AI roll PID, terrain look-ahead
                    var dirs = props.Select(p => Convert.ToInt32(G(p, "turnDirection"))).ToList();
                    float worstLt = 1f;
                    foreach (var p in props)
                    {
                        int dir = Convert.ToInt32(G(p, "turnDirection"));
                        foreach (var b in (IList)G(p, "blades"))
                        {
                            var bt = (Transform)G(b, "transform"); var lt = (Transform)G(b, "liftTransform");
                            var motion = Vector3.Cross(-p.transform.forward, bt.forward).normalized * dir;
                            worstLt = Mathf.Min(worstLt, Vector3.Dot(lt.forward, motion));
                        }
                    }
                    var ap = new SerializedObject(inst.GetComponentInChildren<AutopilotPlane>(true));
                    var pid = ap.FindProperty("forwardFlightController.rollFlightPID.PID").vector3Value;
                    float trL = fbw.FindProperty("flyByWire.rollTrimLimit").floatValue, trR = fbw.FindProperty("flyByWire.rollTrimRate").floatValue;
                    R("1.7.8 lateral: handed props (turn sum 0, left 1 / right -1, every blade lift transform along its own motion), FBW roll trim off, AI roll PID, look-ahead gLimit",
                        dirs.Sum() == 0 && dirs.Count == 4 && worstLt > 0.98f && trL == FbwRollTrimLimit && trR == FbwRollTrimRate && (pid - AiRollPID).magnitude < 1e-5f && Mathf.Abs(prm.aircraftGLimit - AiLookaheadGLimit) < 1e-5f,
                        $"turn {string.Join("/", props.Select(p => p.name + ":" + Convert.ToInt32(G(p, "turnDirection"))))}, lift-transform alignment min {worstLt:F3}, trim {trL}/{trR}, roll PID {pid}, gLimit {prm.aircraftGLimit}");
                }
                R("every part (props excepted) has its own ImpactDamage", allParts.Where(p => !p.name.StartsWith("prop_")).All(p => { var x = G(p, "impactDamage"); return x != null && (float)G(x, "threshold") > 0f; }) && allParts.Where(p => !p.name.StartsWith("prop_")).Select(p => G(p, "impactDamage")).Distinct().Count() == allParts.Count(p => !p.name.StartsWith("prop_")), "");
                var noJ = allParts.Where(p => p.transform != inst.transform && (p.Joints == null || p.Joints.Length == 0)).Select(p => p.name).ToList();
                var wr = allParts.Where(p => p.name.StartsWith("wing_inner")).Select(p => p.Joints == null || p.Joints.Length == 0 ? 0f : p.Joints.Max(j => j.breakForce)).ToList();
                R("joints: wing roots >= 450 kN class, every part jointed", wr.Count == 2 && wr.All(f => f >= 450000f) && noJ.Count == 0, $"wing roots {string.Join("/", wr)}; without joints: {string.Join(",", noJ)}");
                var fuel = inst.GetComponentsInChildren<FuelTank>(true);
                {   // round 5 (wreck fire): one AB-4-style tank per tank-carrying part, on the part's own transform, origin inside the part's
                    // own collider bounds (the fire / fireball spawn point), links inner <-> mid <-> outer and inner <-> centre section
                    var bad = new List<string>();
                    foreach (var f in fuel)
                    {
                        var up = f.GetComponent<AeroPart>();
                        if (up == null || (UnitPart)G(f, "part") != up) { bad.Add(f.name + " not on its part"); continue; }
                        var mc = up.GetComponent<MeshCollider>();
                        var b = mc != null ? mc.bounds : new Bounds(up.transform.position, Vector3.zero);
                        b.Expand(0.05f);
                        if (!b.Contains(f.transform.position)) bad.Add($"{f.name} origin outside its part {inst.transform.InverseTransformPoint(f.transform.position).ToString("F1")}");
                        if ((float)G(f, "ignitionGMin") > 45f) bad.Add(f.name + " light-aircraft settings");
                    }
                    string[] must = { "wing_inner_L", "wing_mid_L", "wing_outer_L", "wing_inner_R", "wing_mid_R", "wing_outer_R", "nacelle_1", "nacelle_2", "nacelle_3", "nacelle_4", "B17G", "fus_waist" };
                    foreach (var mn in must) if (!fuel.Any(f => f.name.Replace("(Clone)", "") == mn)) bad.Add("no tank on " + mn);
                    var wi = fuel.FirstOrDefault(f => f.name == "wing_inner_L");
                    var links = wi != null ? ((FuelTank[])G(wi, "connectedTanks")).Select(x => x.name).ToList() : new List<string>();
                    if (!(links.Contains("wing_mid_L") && links.Any(x => x.StartsWith("B17G")))) bad.Add("wing_inner_L links " + string.Join("/", links));
                    var dfl = Fld(typeof(UnitPart), "damageEffects");
                    foreach (var ap in inst.GetComponentsInChildren<AeroPart>(true))
                    {
                        var fx = (IList)dfl.GetValue(ap);
                        if (ap.name.StartsWith("prop_") && fx != null && fx.Count > 0) bad.Add(ap.name + " still carries a fire effect");
                        if (ap.name.StartsWith("engine_") && (fx == null || fx.Count == 0)) bad.Add(ap.name + " has no fire effect");
                    }
                    R("fuel 4,600 kg in 12 linked AB-4-style tanks, each on its part at the tank (fire spawn inside the part); engine fire effect on engine_n, none on the props",
                      Mathf.Abs(fuel.Sum(f => (float)G(f, "fuelCapacity")) - FuelKg) < 1f && bad.Count == 0, $"{fuel.Length} tanks {fuel.Sum(f => (float)G(f, "fuelCapacity")):F0} kg; {string.Join("; ", bad.Take(8))}");
                }
                {   // 1.8.5 offline E (in-game 1.8.3 F1): internals look - stock vertex colours kept, drawn with the stock textures on the matte look material
                    bool okL = B25HTools.StockStructure.CheckLook(inst, out string msgL);
                    R("1.8.5 E internals look: every internals submesh carries a stock exterior-structure vertex grey (87-118, alpha 255) and is drawn with <prefix>_structure_look (URP Lit, the stock aircraft_structure_b / _n / _ao textures, neutral light grey, metallic <= 0.15); none left on the reflective stock material",
                        okL, msgL);
                }
                {   // 1.8.3: internals the stock way + the nacelle rebuild kept the 1.8.2 physics
                    var rs_ = inst.GetComponentsInChildren<MeshRenderer>(true);
                    var ourStruct = rs_.Where(r_ => r_.gameObject.layer != 3 && r_.sharedMaterials.Any(m_ => m_ != null && (m_.name == "B17G_structure" || m_.name == "B17G_engine"))).Select(r_ => r_.name).ToList();
                    var stockStruct = rs_.Where(r_ => r_.sharedMaterials.Any(m_ => StockStructure.IsStructMat(m_))).ToList();
                    bool vcolS = stockStruct.All(r_ => { var mm = r_.GetComponent<MeshFilter>().sharedMesh; return mm.colors32.Length == mm.vertexCount; });
                    R("1.8.3 internals: spars, ribs, frames, stringers, engine mounts / accessory sections drawn with the stock aircraft_structure (vertex colour); none left on our structure / engine materials",
                      !StockStructure.Enabled || (ourStruct.Count == 0 && stockStruct.Count >= 20 && vcolS), $"{stockStruct.Count} stock-structure renderers ({stockStruct.Sum(r_ => r_.GetComponent<MeshFilter>().sharedMesh.triangles.Length / 3)} tris); ours left on: {string.Join(", ", ourStruct.Take(6))}");
                    var hs = inst.GetComponentsInChildren<Transform>(true).Where(t_ => t_.name.EndsWith("_hullsrc")).Select(t_ => t_.name).ToList();
                    var engB = EngineNums.Select(en_ => { var ec_ = allParts.FirstOrDefault(p_ => p_.name == "engine_" + en_); var mc_ = ec_ != null ? ec_.GetComponent<MeshCollider>() : null; return mc_ != null ? $"e{en_} {inst.transform.InverseTransformPoint(mc_.bounds.center).ToString("F2")} {mc_.bounds.size.ToString("F2")}" : $"e{en_} ?"; }).ToList();
                    var com182 = new Vector3(0.00f, 0.02f, 0.12f);
                    R("1.8.3 nacelles: no collider-source child left; parts-collider CoM within 3.5 cm of 1.8.2 (0.00, 0.02, 0.12): engine colliders keep the 1.8.2 turbo",
                      hs.Count == 0 && (com - com182).magnitude < 0.035f, $"CoM {com.ToString("F3")}; left: {string.Join(",", hs)}; {string.Join("; ", engB)}");
                }
                {   // 1.8.8 (user 2026-11-08: engine housings / tail): nacelle bodies shaped on our wing from the reference sections (outboard
                    // underside ends y -0.20 = Unity z -0.92, inboard -1.06 = z -1.78); their colliders keep the 1.8.7 nacelle (nacelle_n_hullsrc
                    // baked in, then deleted) so the parts-collider CoM is unchanged; tail: glazed gunner's cab, Cheyenne cover centre z 0.70
                    // (Unity y 0.30), height 0.76 m, the guns in its slots (turret kinematics row)
                    var det = new List<string>(); bool ok = true;
                    foreach (var en_ in EngineNums)
                    {
                        var p_ = allParts.FirstOrDefault(q => q.name == "nacelle_" + en_);
                        var mf_ = p_ != null ? p_.GetComponent<MeshFilter>() : null; var mc_ = p_ != null ? p_.GetComponent<MeshCollider>() : null;
                        if (mf_ == null || mc_ == null || mc_.sharedMesh == null) { ok = false; det.Add($"nacelle_{en_} mesh / collider missing"); continue; }
                        float vis = mf_.sharedMesh.vertices.Min(v => inst.transform.InverseTransformPoint(mf_.transform.TransformPoint(v)).z);
                        float col = mc_.sharedMesh.vertices.Min(v => inst.transform.InverseTransformPoint(mc_.transform.TransformPoint(v)).z);
                        bool outer = en_ == 1 || en_ == 4;
                        bool o_ = outer ? (vis > -1.00f && vis < -0.85f && col < -1.95f) : (vis > -1.85f && vis < -1.70f && col < -2.05f);
                        ok &= o_; det.Add($"n{en_} visible end z {vis:F2}, collider end z {col:F2}{(o_ ? "" : " BAD")}");
                    }
                    var taz = T("tail_az"); var tb = T("tailmantlet_body"); var tg = T("tail_gun");
                    float tz = taz != null ? inst.transform.InverseTransformPoint(taz.position).y : 9f;
                    var tbm = tb != null ? tb.GetComponent<MeshFilter>() : null;
                    var tbv = tbm != null ? tbm.sharedMesh.vertices.Select(v => inst.transform.InverseTransformPoint(tb.TransformPoint(v)).y).ToList() : new List<float> { 0f };
                    float th = tbv.Max() - tbv.Min();
                    int glass = tg != null ? tg.GetComponent<MeshRenderer>().sharedMaterials.Count(m_ => m_ != null && m_.name.ToLower().Contains("glass")) : 0;
                    bool tOk = Mathf.Abs(tz - 0.303f) < 0.02f && Mathf.Abs(th - 0.76f) < 0.06f && glass > 0;
                    det.Add($"tail_az y {tz:F2}, cover height {th:F2}, tail_gun glass submeshes {glass}");
                    R("1.8.8 nacelles + tail: visible nacelle ends at the reference (outer z -0.92, inner -1.78), colliders still the 1.8.7 nacelle; Cheyenne cover at y 0.30 / 0.76 m tall, gunner's cab glazed",
                      ok && tOk, string.Join("; ", det));
                }
                // liveries
                R("AI performance parameters set (1.6.9 / 1.7.8 comment-swallow guard): PIDReferenceAirspeed 85, maxSpeed 100, takeoffSpeed 47, takeoffDistance 1150, minimumRadarAlt, groundTurningRadius 30", prm.PIDReferenceAirspeed == 85f && prm.maxSpeed == 100f && prm.takeoffSpeed == 47f && prm.takeoffDistance == 1150f && prm.minimumRadarAlt == AiMinRadarAlt && prm.groundTurningRadius == 30f, $"{prm.PIDReferenceAirspeed}/{prm.maxSpeed}/{prm.takeoffSpeed}/{prm.takeoffDistance}/{prm.minimumRadarAlt}/{prm.groundTurningRadius}");
                var liv = prm.liveries;
                R("liveries: 2 shared + 2 per faction (8 entries), none of the own ones shared", liv.Count == 8 && liv.Count(l => l.name.StartsWith("USAAF")) == 4 && liv.Where(l => l.name.StartsWith("BDF")).All(l => l.faction == liv[0].faction) && liv.Where(l => l.name.StartsWith("PALA")).All(l => l.faction != liv[0].faction),
                    string.Join(", ", liv.Select(l => l.name + "/" + (l.faction == liv[0].faction ? "BDF" : "PALA"))));
                // references
                var stray = new List<string>();
                foreach (var c in inst.GetComponentsInChildren<Component>(true))
                {
                    if (c == null) { stray.Add("missing script"); continue; }
                    var so = new SerializedObject(c); var it = so.GetIterator(); bool enter = true;
                    while (it.Next(enter))
                    {
                        enter = true;
                        if (it.propertyType != SerializedPropertyType.ObjectReference || it.objectReferenceValue == null) continue;
                        var v = it.objectReferenceValue;
                        Transform t = v is GameObject go ? go.transform : v is Component cc ? cc.transform : null;
                        if (t != null && !EditorUtility.IsPersistent(v) && t.root != inst.transform) stray.Add($"{c.GetType().Name}@{c.name}.{it.propertyPath}");
                    }
                }
                R("no references outside the prefab / no missing scripts", stray.Count == 0, string.Join("; ", stray.Take(10)));
                // round 3 (user: rogue polygons): every exported mesh arrives whole - triangle count per object = the Blender export table
                // (b17g_parts.json, written by export_b17g.py); the stray-geometry scan of the FBX itself is blender/b17g/check_b17g_stray.py
                {
                    var tab = Newtonsoft.Json.Linq.JArray.Parse(File.ReadAllText(Path.Combine(Path.GetDirectoryName(RepoModel), "b17g_parts.json")));
                    var want = tab.Where(r => (int)r["tris"] > 0 && !((string)r["name"]).EndsWith("_hullsrc")).ToDictionary(   // 1.8.8: collider sources are deleted in Unity (8 since 1.8.8)
                        r => (string)r["name"] == "B17G" ? "fus_center" : (string)r["name"], r => (int)r["tris"]);
                    var seen = new HashSet<string>(); var bad = new List<string>(); int cmp = 0;
                    foreach (var mf in inst.GetComponentsInChildren<MeshFilter>(true))
                    {
                        if (mf.sharedMesh == null || mf.name.StartsWith("prop_") || !want.TryGetValue(mf.name, out var wt) || !seen.Add(mf.name)) continue;
                        int got = 0; for (int sm = 0; sm < mf.sharedMesh.subMeshCount; sm++) got += (int)mf.sharedMesh.GetIndexCount(sm) / 3;
                        var stc = mf.transform.Find(mf.name + "_struct");      // 1.8.3: internals moved to the stock-structure child
                        if (stc != null && stc.GetComponent<MeshFilter>() != null) got += stc.GetComponent<MeshFilter>().sharedMesh.triangles.Length / 3;
                        cmp++; if (got != wt) bad.Add($"{mf.name} {got}/{wt}");
                    }
                    R("meshes arrive whole: Unity triangles per object = the Blender export table (no import split / loss; props are rebuilt by the prop code)", bad.Count == 0 && cmp >= want.Count - 30, $"{cmp} of {want.Count} compared; mismatches {string.Join(", ", bad.Take(8))}");
                }
            }
            finally { Object.DestroyImmediate(inst); }
            int w = rows.Max(r => r.name.Length);
            L("CHECK TABLE");
            foreach (var r in rows) L($"  {(r.ok ? "PASS" : "FAIL")}  {r.name.PadRight(w)}  {r.detail}");
            bool all = rows.All(r => r.ok);
            L($"CHECK {(all ? "ALL PASS" : "FAILURES: " + rows.Count(r => !r.ok))} ({rows.Count(r => r.ok)}/{rows.Count})");
            lastCheck = $"{rows.Count(r => r.ok)}/{rows.Count}";
            return all;
        }
        public static string lastCheck = "";
    }
}
