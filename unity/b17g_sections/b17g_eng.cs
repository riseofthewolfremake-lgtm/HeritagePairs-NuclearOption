        // four engines: the B-25H's per-engine set (TurbineEngine + own Transmission on engine_n, ConstantSpeedProp + PropStrikeDetector on
        // prop_n), so an engine kill stops only its own prop; asymmetric thrust comes from the physics. AB-4 messages "ENGINE n FIRE".
        static readonly int[] EngineNums = { 1, 2, 3, 4 };
        static void Engines()
        {
            var startup = CloneComp(TplAudio("COIN:cockpit_F", "cricket_startup"), parts["fus_cockpit"].gameObject);
            var ab4 = AB4EngineMessages ? AB4Messages() : new Dictionary<int, (string, AudioClip)>();
            foreach (var n in EngineNums)
            {
                var side = n <= 2 ? "L" : "R";
                var eng = parts["engine_" + n].gameObject;
                CloneComp(TplAudio("COIN:COIN", "cricket_turbine"), eng);
                var te = CloneComp(TplComp<TurbineEngine>("CAS1:engine_" + side), eng);
                te.maxRPM = 2300f; te.minRPM = 550f; te.maxPower = EnginePower; te.spoolUpTime = 3f; S(te, "startupTime", 6f + n * 0.8f);
                S(te, "pitch", 0.15f); S(te, "volume", 0.06f);
                S(te, "startupAudio", startup); te.aircraft = aircraft;
                S(te, "heatHazeParticles", new ParticleSystem[0]);
                S(te, "maxFuelConsumption", 0.075f); S(te, "IRMin", 1.2f); S(te, "IRMax", 1.6f);
                S(te, "IRSourceTransform", Find("exhaust_" + n));
                S(te, "criticalParts", new UnitPart[] { parts["engine_" + n], parts["prop_" + n] });
                S(te, "criticalDamageThreshold", 40f);
                if (ab4.TryGetValue(n, out var msg)) { S(te, "failureMessage", msg.Item1); S(te, "failureMessageAudio", msg.Item2); }
                else S(te, "failureMessage", $"ENGINE {n} FIRE");
                S(te, "failureTransform", NewGO("engine_" + n + "_fail", eng.transform, eng.transform.position + new Vector3(0, 0.3f, -0.4f), Quaternion.identity).transform);
                var tr = CloneComp(TplComp<Transmission>("COIN:COIN"), eng);
                S(tr, "powerSources", new[] { eng });

                var propGO = parts["prop_" + n].gameObject;
                var hubVis = Find("prop_hub_" + n);
                var pa = CloneComp(TplAudio("COIN:propHub", "cricket_exterior"), propGO);
                var csp = CloneComp(TplComp<ConstantSpeedProp>("COIN:propHub"), propGO);
                S(csp, "unitPart", parts["prop_" + n]); S(csp, "transmission", tr); S(csp, "oppositeCorner", null);
                var fTurn = Fld(typeof(ConstantSpeedProp), "turnDirection"); fTurn.SetValue(csp, Enum.ToObject(fTurn.FieldType, PropTurn[n]));   // 1.7.8: handed (3-4 turn the other way, mirrored blades): no net torque
                var fPitch = Fld(typeof(ConstantSpeedProp), "pitchDirection"); fPitch.SetValue(csp, Enum.ToObject(fPitch.FieldType, -1));
                var blades = new List<object>(); var dmgMeshes = new List<Mesh>();
                float R = 0f;
                var bladeMFs = hubVis.GetComponentsInChildren<MeshFilter>(true).Where(m => m.name.Contains("_blade")).OrderBy(m => m.name).ToList();
                foreach (var bmf in bladeMFs)
                {
                    var radial = bmf.transform.up;
                    float tip = bmf.sharedMesh.bounds.max.y; R = Mathf.Max(R, tip);
                    var F = propGO.transform.forward;
                    var broot = NewGO(bmf.name + "_root", hubVis, hubVis.position, Quaternion.LookRotation(radial, Vector3.Cross(radial, -F)));
                    bmf.transform.SetParent(broot.transform, true);
                    var tang = Vector3.Cross(-F, radial) * PropTurn[n];     // the blade's motion direction (ConstantSpeedProp: Cross(-hub.fwd, blade.fwd) x turnDirection)
                    var lt = NewGO(bmf.name + "_lift", broot.transform, hubVis.position + radial * tip, Quaternion.LookRotation(tang, F));
                    var b = New(typeof(ConstantSpeedProp.PropBlade));
                    S(b, "transform", broot.transform); S(b, "liftTransform", lt.transform); S(b, "mass", 60f);
                    ((ConstantSpeedProp.PropBlade)b).renderer = bmf.GetComponent<MeshRenderer>();
                    ((ConstantSpeedProp.PropBlade)b).bladeMeshFilter = bmf;
                    blades.Add(b);
                    if (dmgMeshes.Count == 0)
                        foreach (var frac in new[] { 0.25f, 0.5f, 0.75f, 0.95f }) dmgMeshes.Add(TruncatedBlade(bmf.sharedMesh, tip * frac, $"{bmf.name}_dmg{(int)(frac * 100)}"));
                }
                if (R < 1f) R = 1.765f;
                SetSeq(csp, "blades", blades);
                S(csp, "hubVisible", hubVis.gameObject);
                var disc = NewGO("prop_" + n + "_disc", hubVis, hubVis.position + propGO.transform.forward * 0.02f, Quaternion.LookRotation(propGO.transform.forward, Vector3.up));
                disc.AddComponent<MeshFilter>(); var dr = disc.AddComponent<MeshRenderer>(); dr.sharedMaterial = mats["propdisc"];
                dr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                disc.GetComponent<MeshFilter>().sharedMesh = null;
                var stage1 = BlurStageMesh("prop_blur1_" + n, R * 1.01f, 0.5f); var stage2 = BlurStageMesh("prop_blur2_" + n, R * 1.01f, 0f);
                S(csp, "propDisc", disc.GetComponent<MeshFilter>());
                S(csp, "bladeDamageMeshes", dmgMeshes.ToArray());
                S(csp, "fragmentPrefab", null);
                SetSeq(csp, "propDiscMeshes", new Mesh[] { null, stage1, stage2 });
                S(csp, "propDiskThicknessMin", 1f); S(csp, "propDiskThicknessMax", 1f);
                S(csp, "propBlurLightsMaterial", null);
                var strikeGO = NewGO("prop_" + n + "_strike", propGO.transform, hubVis.position, Quaternion.LookRotation(propGO.transform.forward, Vector3.up), 15);
                var smc = strikeGO.AddComponent<MeshCollider>(); smc.sharedMesh = CylinderMesh("prop_strike_" + n, R, 0.06f, 24); smc.convex = true; smc.isTrigger = true;
                var psd = CloneComp(TplComp<PropStrikeDetector>("COIN:propDiscCollider"), strikeGO);
                S(psd, "currentRadius", R); S(psd, "propCollider", smc);
                S(csp, "propDiscCollider", smc); S(csp, "propStrikeDetector", psd);
                S(csp, "momentOfInertia", 180f); S(csp, "bladeLength", R); S(csp, "hubRadius", 0.30f);
                S(csp, "rpmLimit", PropRpm); S(csp, "nominalPower", EnginePower); S(csp, "propTorqueLimit", 15000f);
                S(csp, "propAudio", pa);
                L($"prop {n}: radius {R:F3} m, {blades.Count} blades, turn {PropTurn[n]}, rpmLimit {PropRpm}, hub {hubVis.position.ToString("F3")}{(ab4.ContainsKey(n) ? ", AB-4 message '" + ab4[n].Item1 + "'" : "")}");
            }
        }

        // the AB-4 (FastBomber1) failure messages + voice clips: the component that carries failureMessage "ENGINE n FIRE"
        static Dictionary<int, (string, AudioClip)> AB4Messages()
        {
            var d = new Dictionary<int, (string, AudioClip)>();
            var p = AssetDatabase.LoadAssetAtPath<GameObject>($"{DNS}/GameObject/FastBomber1_PLACEHOLDER.prefab");
            if (p == null) { L("WARN AB-4 placeholder missing: plain ENGINE n FIRE text"); return d; }
            foreach (var c in p.GetComponentsInChildren<Component>(true))
            {
                if (c == null) continue;
                FieldInfo fm = null, fa = null;
                for (var t = c.GetType(); t != null && fm == null; t = t.BaseType) { fm = t.GetField("failureMessage", BF | BindingFlags.DeclaredOnly); fa = t.GetField("failureMessageAudio", BF | BindingFlags.DeclaredOnly); }
                if (fm == null) continue;
                var m = fm.GetValue(c) as string;
                if (m == null || !m.StartsWith("ENGINE ") || !m.EndsWith(" FIRE")) continue;
                if (int.TryParse(m.Substring(7, 1), out int n)) d[n] = (m, fa != null ? fa.GetValue(c) as AudioClip : null);
            }
            L($"AB-4 engine messages: {string.Join(", ", d.OrderBy(k => k.Key).Select(k => k.Value.Item1 + (k.Value.Item2 ? " (voice)" : "")))}");
            return d;
        }

