        // four 4.03 MW turboshafts, each driving two contra-rotating 6-blade rows (design 3.1): TurbineEngine + one Transmission on engine_n;
        // ConstantSpeedProp + PropStrikeDetector on prop_n (front row, the part) and on prop_n_aft (aft row, a child of the same part = the
        // same rigidbody, so the two strike triggers never touch each other). Transmission.cs 41-67 shares the delivered power between its
        // outputs in proportion to their requests (each row requests throttle x nominalPower = half the engine): a stock multi-output
        // transmission (UtilityHelo1). turnDirection +1 / -1: the rows' engine torques and blade torques cancel on every engine.
        static readonly int[] EngineNums = { 1, 2, 3, 4 };
        static readonly List<ConstantSpeedProp> propRows = new List<ConstantSpeedProp>();
        static void Engines()
        {
            propRows.Clear();
            var startup = CloneComp(TplAudio("COIN:cockpit_F", "cricket_startup"), parts["fus_cockpit"].gameObject);
            var ab4 = AB4EngineMessages ? AB4Messages() : new Dictionary<int, (string, AudioClip)>();
            foreach (var n in EngineNums)
            {
                var side = n <= 2 ? "L" : "R";
                var eng = parts["engine_" + n].gameObject;
                CloneComp(TplAudio("COIN:COIN", "cricket_turbine"), eng);
                var te = CloneComp(TplComp<TurbineEngine>("CAS1:engine_" + side), eng);
                te.maxRPM = 14000f; te.minRPM = 5600f; te.maxPower = EnginePower; te.spoolUpTime = 4f; S(te, "startupTime", 8f + n * 0.8f);
                S(te, "pitch", 0.15f); S(te, "volume", 0.06f);
                S(te, "startupAudio", startup); te.aircraft = aircraft;
                S(te, "heatHazeParticles", new ParticleSystem[0]);
                S(te, "maxFuelConsumption", 0.45f); S(te, "IRMin", 1.0f); S(te, "IRMax", 1.4f);
                S(te, "IRSourceTransform", Find("exhaust_" + n));
                S(te, "criticalParts", new UnitPart[] { parts["engine_" + n], parts["prop_" + n] });
                S(te, "criticalDamageThreshold", 40f);
                if (ab4.TryGetValue(n, out var msg)) { S(te, "failureMessage", msg.Item1); S(te, "failureMessageAudio", msg.Item2); }
                else S(te, "failureMessage", $"ENGINE {n} FIRE");
                S(te, "failureTransform", NewGO("engine_" + n + "_fail", eng.transform, eng.transform.position + new Vector3(0, 0.3f, -0.4f), Quaternion.identity).transform);
                var tr = CloneComp(TplComp<Transmission>("COIN:COIN"), eng);
                S(tr, "powerSources", new[] { eng });

                var propGO = parts["prop_" + n].gameObject;
                foreach (var (row, rowGO, hubName, turn) in new[] { ("front", propGO, "prop_hub_" + n, PropTurn[n]), ("aft", Find("prop_" + n + "_aft").gameObject, "prop_hub_" + n + "_aft", AftRowTurn) })
                {
                    if (row == "aft" && !ContraProps190)
                    {   // fallback: the aft row stays a visual (it does not turn); the front row takes the full power
                        L($"prop {n} aft row: visual only (ContraProps190 off)");
                        continue;
                    }
                    var hubVis = Find(hubName);
                    var pa = CloneComp(TplAudio("COIN:propHub", "cricket_exterior"), rowGO);
                    if (row == "aft") pa.volume *= 0.5f;
                    var csp = CloneComp(TplComp<ConstantSpeedProp>("COIN:propHub"), rowGO);
                    S(csp, "unitPart", parts["prop_" + n]); S(csp, "transmission", tr); S(csp, "oppositeCorner", null);
                    var fTurn = Fld(typeof(ConstantSpeedProp), "turnDirection"); fTurn.SetValue(csp, Enum.ToObject(fTurn.FieldType, turn));
                    var fPitch = Fld(typeof(ConstantSpeedProp), "pitchDirection"); fPitch.SetValue(csp, Enum.ToObject(fPitch.FieldType, -1));
                    var blades = new List<object>(); var dmgMeshes = new List<Mesh>();
                    float R = 0f;
                    var bladeMFs = hubVis.GetComponentsInChildren<MeshFilter>(true).Where(m => m.name.Contains("_blade") && m.transform.parent == hubVis).OrderBy(m => m.name).ToList();
                    foreach (var bmf in bladeMFs)
                    {
                        var radial = bmf.transform.up;
                        float tip = bmf.sharedMesh.bounds.max.y; R = Mathf.Max(R, tip);
                        var F = rowGO.transform.forward;
                        var broot = NewGO(bmf.name + "_root", hubVis, hubVis.position, Quaternion.LookRotation(radial, Vector3.Cross(radial, -F)));
                        bmf.transform.SetParent(broot.transform, true);
                        var tang = Vector3.Cross(-F, radial) * turn;
                        var lt = NewGO(bmf.name + "_lift", broot.transform, hubVis.position + radial * tip, Quaternion.LookRotation(tang, F));
                        var b = New(typeof(ConstantSpeedProp.PropBlade));
                        S(b, "transform", broot.transform); S(b, "liftTransform", lt.transform); S(b, "mass", 35f);
                        ((ConstantSpeedProp.PropBlade)b).renderer = bmf.GetComponent<MeshRenderer>();
                        ((ConstantSpeedProp.PropBlade)b).bladeMeshFilter = bmf;
                        blades.Add(b);
                        if (dmgMeshes.Count == 0)
                            foreach (var frac in new[] { 0.25f, 0.5f, 0.75f, 0.95f }) dmgMeshes.Add(TruncatedBlade(bmf.sharedMesh, tip * frac, $"{bmf.name}_dmg{(int)(frac * 100)}"));
                    }
                    if (R < 1f) R = 1.70f;
                    SetSeq(csp, "blades", blades);
                    S(csp, "hubVisible", hubVis.gameObject);
                    var disc = NewGO(rowGO.name + "_disc", hubVis, hubVis.position + rowGO.transform.forward * 0.02f, Quaternion.LookRotation(rowGO.transform.forward, Vector3.up));
                    disc.AddComponent<MeshFilter>(); var dr = disc.AddComponent<MeshRenderer>(); dr.sharedMaterial = mats["propdisc"];
                    dr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                    disc.GetComponent<MeshFilter>().sharedMesh = null;
                    var stage1 = BlurStageMesh($"prop_blur1_{n}_{row}", R * 1.01f, 0.5f); var stage2 = BlurStageMesh($"prop_blur2_{n}_{row}", R * 1.01f, 0f);
                    S(csp, "propDisc", disc.GetComponent<MeshFilter>());
                    S(csp, "bladeDamageMeshes", dmgMeshes.ToArray());
                    S(csp, "fragmentPrefab", null);
                    SetSeq(csp, "propDiscMeshes", new Mesh[] { null, stage1, stage2 });
                    S(csp, "propDiskThicknessMin", 1f); S(csp, "propDiskThicknessMax", 1f);
                    S(csp, "propBlurLightsMaterial", null);
                    var strikeGO = NewGO(rowGO.name + "_strike", rowGO.transform, hubVis.position, Quaternion.LookRotation(rowGO.transform.forward, Vector3.up), 15);
                    var smc = strikeGO.AddComponent<MeshCollider>(); smc.sharedMesh = CylinderMesh($"prop_strike_{n}_{row}", R, 0.06f, 24); smc.convex = true; smc.isTrigger = true;
                    var psd = CloneComp(TplComp<PropStrikeDetector>("COIN:propDiscCollider"), strikeGO);
                    S(psd, "currentRadius", R); S(psd, "propCollider", smc);
                    S(csp, "propDiscCollider", smc); S(csp, "propStrikeDetector", psd);
                    float share = ContraProps190 ? 0.5f : 1f;
                    S(csp, "momentOfInertia", 120f); S(csp, "bladeLength", R); S(csp, "hubRadius", 0.40f);
                    S(csp, "rpmLimit", PropRpm); S(csp, "nominalPower", EnginePower * share); S(csp, "propTorqueLimit", ContraProps190 ? PropTorqueLimitRow : 2f * PropTorqueLimitRow);
                    S(csp, "propAudio", pa);
                    propRows.Add(csp);
                    L($"prop {n} {row} row: radius {R:F3} m, {blades.Count} blades, turn {turn}, rpmLimit {PropRpm}, nominal {EnginePower * share / 1e6f:F3} MW, hub {hubVis.position.ToString("F3")}{(ab4.ContainsKey(n) && row == "front" ? ", AB-4 message '" + ab4[n].Item1 + "'" : "")}");
                }
            }
        }

