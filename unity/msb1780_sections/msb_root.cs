        static void RootSystems(List<LandingGear> gears)
        {
            var coin = tpl["COIN"]; var ew1 = tpl["EW1"]; var ab4 = tpl["FastBomber1"];
            // optical search sensor: the AB-4's TargetDetector (heavy-bomber EOTS values) when the template has one, else the CI-22's
            var dsrc = ab4.GetComponent<TargetDetector>() ?? coin.GetComponent<TargetDetector>();
            if (ab4.GetComponent<TargetDetector>() == null) dsrc = coin.GetComponent<TargetDetector>();
            var detector = CloneComp(dsrc, root);
            S(detector, "attachedUnit", aircraft); S(detector, "scanner", parts["fus_cockpit"].transform);
            aircraft.EOTS = detector;
            // air-search radar, 60 km (user decision 2026-11-10): the EW-25's Radar values with maxRange 60 km, antenna in the nose
            if (Radar190)
            {
                var ant = NewGO("radar_antenna", parts["fus_nose"].transform, root.transform.TransformPoint(new Vector3(0f, 0.55f, 6.9f)), Quaternion.identity);
                var radar = CloneComp(ew1.GetComponent<Radar>(), root);
                S(radar, "attachedUnit", aircraft); S(radar, "scanner", ant.transform);
                var so = new SerializedObject(radar); var mr = so.FindProperty("RadarParameters.maxRange"); if (mr != null) { mr.floatValue = RadarRange; so.ApplyModifiedPropertiesWithoutUndo(); }
                try { S(aircraft, "radar", radar); } catch (Exception e) { L("note: no Unit.radar field to set (" + e.Message + ")"); }
                L($"radar: EW-25 values, maxRange {RadarRange / 1000f:F0} km, antenna {ant.transform.position.ToString("F2")}");
            }
            // power: capacitor charged by all four engines (PowerSupply: charge += chargePerRPM x engine rpm per second, PowerSupply.cs 86-91)
            var cap = CloneComp(TplAudio("COIN:COIN", "capacitor"), root);
            var power = CloneComp(ew1.GetComponent<PowerSupply>(), root);
            S(power, "powerSources", EngineNums.Select(n => parts["engine_" + n].gameObject).ToArray());
            S(power, "maxCharge", PowerMaxCharge); S(power, "chargePerRPM", PowerChargePerRPM); S(power, "maxPower", 2f * LaserPowerKW + JammerPowerKW);
            S(power, "source", cap); S(power, "aircraft", aircraft);
            S(aircraft, "powerSupply", power);
            if (RadarJammer190)
            {
                var jam = CloneComp(ew1.GetComponent<RadarJammer>(), root);   // EW-25: jammingIntensity 8, capacitance 100
                S(jam, "aircraft", aircraft); S(jam, "powerUsage", JammerPowerKW);
            }
            CloneComp(coin.GetComponent<NuclearOption.NetworkTransforms.AircraftNetworkTransform>(), root);

            // fuel 10,000 kg (B-17G wreck-fire method: one FuelTank per tank-carrying part, on the part's own GameObject, AB-4 heavy-bomber
            // settings, linked); SelfSealing190: half the leak per hit point and leak rate, 1.5 x the ignition thresholds (the sheet's
            // compartmentalised self-sealing tanks; the fields exist in FuelTank.cs 8-40)
            var tplWingTank = TplComp<FuelTank>("FastBomber1:wingroot_L");
            var tplBodyTank = TplComp<FuelTank>("FastBomber1:fuselage_R");
            tplWingLeakPerHP190 = (float)G(tplWingTank, "leakPerHP");     // for the check (the templates are unloaded before RunCheck)
            var tankKg = new List<(string part, float kg, FuelTank tpl)>();
            foreach (var sd in new[] { "L", "R" })
            {
                tankKg.Add(("wing_inner_" + sd, 2000f, tplWingTank));
                tankKg.Add(("wing_mid_" + sd, 1400f, tplWingTank));
                tankKg.Add(("wing_outer_" + sd, 700f, tplWingTank));
            }
            foreach (var n in EngineNums) tankKg.Add(("nacelle_" + n, 50f, tplWingTank));
            tankKg.Add(("MSB17", 1200f, tplBodyTank));
            tankKg.Add(("fus_waist", 400f, tplBodyTank));
            if (Mathf.Abs(tankKg.Sum(t => t.kg) - FuelKg) > 0.5f) throw new Exception($"fuel split {tankKg.Sum(t => t.kg)} != {FuelKg}");
            var tanks = new Dictionary<string, FuelTank>();
            var sealLog = new List<string>();
            foreach (var (p, kg, tp) in tankKg)
            {
                var ft = CloneComp(tp, parts[p].gameObject);
                S(ft, "fuelCapacity", kg); S(ft, "fuelMass", kg); S(ft, "part", parts[p]);
                if (SelfSealing190)
                    foreach (var (f, k) in new[] { ("leakPerHP", 0.5f), ("maxLeakRate", 0.5f), ("ignitionPierceMin", 1.5f), ("ignitionPierceMax", 1.5f), ("ignitionBlastMin", 1.5f), ("ignitionBlastMax", 1.5f) })
                    {
                        var fi = typeof(FuelTank).GetField(f, BF);
                        if (fi == null || fi.FieldType != typeof(float)) { if (!sealLog.Contains("no " + f)) sealLog.Add("no " + f); continue; }
                        fi.SetValue(ft, (float)fi.GetValue(ft) * k);
                    }
                tanks[p] = ft;
            }
            foreach (var t in tanks.Values) SetSeq(t, "connectedTanks", new object[0]);
            void Link(string a, string b) { var la = ((FuelTank[])G(tanks[a], "connectedTanks")).ToList(); if (!la.Contains(tanks[b])) la.Add(tanks[b]); S(tanks[a], "connectedTanks", la.ToArray()); }
            foreach (var sd in new[] { "L", "R" })
            {
                Link("wing_inner_" + sd, "wing_mid_" + sd); Link("wing_mid_" + sd, "wing_inner_" + sd);
                Link("wing_mid_" + sd, "wing_outer_" + sd); Link("wing_outer_" + sd, "wing_mid_" + sd);
                Link("wing_inner_" + sd, "MSB17"); Link("MSB17", "wing_inner_" + sd);
            }
            L("fuel tanks: " + string.Join(", ", tanks.Select(kv => $"{kv.Key} {G(kv.Value, "fuelCapacity")} kg")) + (SelfSealing190 ? $"; self-sealing x0.5 leak / x1.5 ignition{(sealLog.Count > 0 ? " (" + string.Join(", ", sealLog) + ")" : "")}" : ""));
            {
                var dfl = Fld(typeof(UnitPart), "damageEffects");
                var hubFx = ((IList)dfl.GetValue(TplComp<AeroPart>("COIN:propHub"))).Cast<DamageEffect>().FirstOrDefault(d => d.prefab != null);
                foreach (var n in EngineNums)
                {
                    dfl.SetValue(parts["prop_" + n], new List<DamageEffect>());
                    var lst = new List<DamageEffect>();
                    if (hubFx != null) lst.Add(new DamageEffect { prefab = hubFx.prefab, threshold = 30f });
                    dfl.SetValue(parts["engine_" + n], lst);
                }
            }

            // nav lights
            var nl = CloneComp(coin.GetComponent<NavLights>(), root);
            var entries = new List<object>();
            void Nav(string name, AeroPart part, Vector3 pos, string litMat, Color col)
            {
                var g = NewGO(name, part.transform, pos, Quaternion.identity);
                g.AddComponent<MeshFilter>().sharedMesh = OctaMesh(name, 0.06f);
                var r = g.AddComponent<MeshRenderer>(); r.sharedMaterial = mats["navlight"];
                var lg = NewGO(name + "_light", g.transform, pos, Quaternion.identity);
                var li = lg.AddComponent<Light>(); li.type = LightType.Point; li.color = col; li.range = 6f; li.intensity = 2f; lg.SetActive(false);
                var e = NewElem(nl, "navLights");
                S(e, "renderer", r); S(e, "objects", new[] { lg }); S(e, "litMaterial", Asset<Material>($"Material/{litMat}_PLACEHOLDER.mat"));
                S(e, "part", part); S(e, "gear", null);
                var fcs = Fld(e.GetType(), "controlState"); fcs.SetValue(e, Enum.ToObject(fcs.FieldType, 1));
                entries.Add(e);
            }
            var tipL = parts["wing_tip_L"]; var tipR = parts["wing_tip_R"];
            Nav("navLight_L", tipL, TipPoint(tipL, -1), "navlight_L", Color.red);
            Nav("navLight_R", tipR, TipPoint(tipR, 1), "navlight_R", Color.green);
            if (FormationLights1912)
            {   // 1.9.12: green formation / gear-down strips (the stock slimelight pattern; the GA-25X block of GA25XBuild.RootSystems): the model's
                // own strip meshes (material light_off = the stock light_green_off), whole-renderer swap to the stock slimelight_on while the
                // gear is extended (NavLights Auto; the nav-light key forces them on with the gear up). A missing strip is skipped with a WARN
                // (NavLight.Initialize has no null test on its renderer); the check row fails on a count != FormationLightCount.
                var slimeOn = Asset<Material>("Material/slimelight_on_PLACEHOLDER.mat");
                int nStrips = 0;
                foreach (var lj in JList("lights", "formation"))
                {
                    var t = TryFind((string)lj["name"]); var r = t != null ? t.GetComponent<MeshRenderer>() : null;
                    if (r == null) { L($"WARN formation light {(string)lj["name"]} missing"); continue; }
                    r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                    var part = OwningPart(t);
                    var e = NewElem(nl, "navLights");
                    S(e, "renderer", r); S(e, "objects", new GameObject[0]); S(e, "litMaterial", slimeOn);
                    S(e, "part", part); S(e, "gear", null);
                    var fcs = Fld(e.GetType(), "controlState"); fcs.SetValue(e, Enum.ToObject(fcs.FieldType, 1));
                    entries.Add(e); nStrips++;
                }
                L($"1.9.12 formation lights: {nStrips} slimelight strips (NavLights Auto, litMaterial slimelight_on)");
            }
            if (GearLight1914.Enabled)
            {   // 1.9.14: gear light = a modelled lamp clamped to each main strut (tail-wheel aircraft: aimed 5 deg down at the ground attitude)
                float gp = GearLight1914.GroundPitch(root.transform, new[] { gears[0], gears[1] }, gears[2]);
                foreach (var (mg, sd) in new[] { (gears[0], "L"), (gears[1], "R") })
                {
                    var b = GearLight1914.Make(DNS, mg, Find("gear_main_" + sd), root.transform, "main_" + sd, gp, GearLight1914.StrutMaterial(Find("gear_main_" + sd), mats["metal_dark"]), mats["navlight"], generatedMeshes, 0.045f, 0.30f);
                    var e1 = NewElem(nl, "navLights"); var e2 = NewElem(nl, "navLights");
                    GearLight1914.Entries(e1, e2, b, (UnitPart)G(mg, "attachedPart"), mg, DNS);
                    entries.Add(e1); entries.Add(e2);
                    L($"gear light: lamp {b.lamp.name} on {b.lamp.transform.parent.name}, lens at {b.lensCentre.ToString("F3")}, ground pitch {gp:F1}, aim {b.pitchDown:F1} deg down, housing {b.lamp.GetComponent<MeshRenderer>().sharedMaterial.name}, tyre gap {GearLight1914.TyreGap(b, mg, root.transform):F3} m");
                }
            }
            SetSeq(nl, "navLights", entries);
            S(nl, "aircraft", aircraft);

            // countermeasures: 120 flares from the four dispenser panels on the lower aft fuselage (no automatic release for the player: user
            // decision; the game's AI pilots pop flares themselves, CountermeasureManager)
            if (KeepFlareEjector)
            {
                var fe = CloneComp(coin.GetComponent<FlareEjector>(), root);
                var pts = new List<object>();
                foreach (var dn in new[] { "flare_disp_L1", "flare_disp_L2", "flare_disp_R1", "flare_disp_R2" })
                {
                    var disp = TryFind(dn); if (disp == null) { L($"WARN flare dispenser {dn} missing"); continue; }
                    var mf = disp.GetComponent<MeshFilter>();
                    var c = mf != null ? disp.TransformPoint(mf.sharedMesh.bounds.center) : disp.position;
                    var outw = new Vector3(Mathf.Sign(c.x) * 0.8f, -0.6f, 0f).normalized;
                    var n = parts["fus_waist"];
                    var g = NewGO(dn + "_eject", n.transform, c + outw * 0.05f, Quaternion.LookRotation(outw));
                    var a = CloneComp(TplAudio("COIN:flareEjector_L", "flare"), g);
                    var ep = NewElem(fe, "ejectionPoints");
                    S(ep, "part", n); S(ep, "transform", g.transform); S(ep, "sound", a);
                    pts.Add(ep);
                }
                SetSeq(fe, "ejectionPoints", pts);
                foreach (var f in new[] { "doors", "flareDoors" }) { try { SetSeq(fe, f, new object[0]); } catch { } }
                S(fe, "aircraft", aircraft);
                try { S(fe, "ammo", FlareCount); } catch { }
                try { S(fe, "maxAmmo", FlareCount); } catch { }
                L($"flares: {FlareCount}, {pts.Count} ejection points");
            }

            var sparks = CopyParticle(TplFind("COIN:contactSparks").GetComponent<ParticleSystem>(), root.transform, root.transform.position, "contactSparks");
            S(aircraft, "sparksEmitter", sparks);
            var sgp = root.AddComponent<SetGlobalParticles>();
            S(sgp, "systems", ourParticles.ToList());
            var doppler = new List<AudioSource>();
            foreach (var s in EngineNums) { doppler.Add(parts["engine_" + s].GetComponent<AudioSource>()); doppler.Add(parts["prop_" + s].GetComponent<AudioSource>()); }
            S(aircraft, "dopplerSounds", doppler);
            aircraft.maxRadius = 16.5f;
            aircraft.obstacleTop = 5.1f;
            // 1.9.2 speed brake (in game 1.9.0: AI MSBs reached the final at 96-145 m/s with gear down and kept going round). The stock Airbrake
            // (Airbrake.cs: opens at throttle 0 over 1 / openSpeed s, force = dragAmount x rho x V^2 at the part, against its velocity) on the
            // root part (no yaw / roll moment); AIPilotLandingState sets throttle 0 whenever it is faster than its glide-slope speed schedule
            // (landing speed + 0.015 x distance), the player at idle. Drag only: the design's spoiler panels are not modelled (no visible panels).
            if (Airbrake192)
            {
                var ab = root.AddComponent<global::Airbrake>();
                S(ab, "transforms", new Transform[0]); S(ab, "dragAmount", AirbrakeDrag); S(ab, "maxAngle", 0f); S(ab, "openSpeed", AirbrakeOpenSpeed);
                S(ab, "part", parts["MSB17"]); S(ab, "airbrakeSound", null); S(ab, "constraints", new UnityEngine.Animations.AimConstraint[0]);
                S(ab, "volumeMultiplier", 0f); S(ab, "aircraft", aircraft);
                L($"airbrake: stock Airbrake on the root, dragAmount {AirbrakeDrag} (rho V^2: {AirbrakeDrag * 1.225f * 100f * 100f / 1000f:F0} kN at 100 m/s SL), opens at throttle 0 in {1f / AirbrakeOpenSpeed:F1} s");
                if (AirbrakePanels1912)
                {   // 1.9.12: the same component now also turns the six upper-wing spoiler panels (Airbrake.Update: each transform back to its
                    // rest angles, then Rotate(openAmount x maxAngle about local X)). The panels are plain renderers under hinge empties on the
                    // wing parts: no collider, no part, paint material = in the wing's livery list. dragAmount / part / drag point unchanged.
                    // The hinge frame is set HERE from the contract (not taken from the FBX): +X the hinge line (+x on both sides), +Y the skin
                    // normal, +Z forward along the skin, so a positive angle lifts the panel's rear (-Z) edge.
                    var hinges = new List<Transform>();
                    foreach (var pj in JList("airbrake", "panels"))
                    {
                        var h = TryFind((string)pj["hinge"]); var panel = TryFind((string)pj["name"]);
                        if (h == null || panel == null || panel.GetComponent<MeshFilter>() == null) throw new Exception($"airbrake panel {(string)pj["name"]} / its hinge missing in the model");
                        Vector3 Dir(Newtonsoft.Json.Linq.JToken t) => root.transform.TransformDirection(new Vector3((float)t[0], (float)t[2], (float)t[1])).normalized;   // Blender (x, y fwd, z up) -> Unity
                        var kids = h.Cast<Transform>().ToList();
                        foreach (var k in kids) k.SetParent(h.parent, true);
                        h.rotation = Quaternion.LookRotation(Dir(pj["fwd"]), Dir(pj["up"]));
                        foreach (var k in kids) k.SetParent(h, true);
                        // opening sense, measured: the panel vertex farthest aft of the hinge line must rise along the skin normal
                        var far = panel.GetComponent<MeshFilter>().sharedMesh.vertices.Select(v => h.InverseTransformPoint(panel.TransformPoint(v))).OrderBy(v => v.z).First();
                        float rise = Vector3.Dot(h.TransformPoint(Quaternion.AngleAxis(AirbrakePanelAngle, Vector3.right) * far) - h.TransformPoint(far), h.up);
                        if (rise < 0.2f) throw new Exception($"airbrake panel {panel.name}: opening {AirbrakePanelAngle} deg moves its free edge {rise:F3} m along the skin normal (wrong sense / hinge frame)");
                        L($"  1.9.12 airbrake panel {panel.name} on {OwningPart(h)?.name}: hinge {h.localPosition.ToString("F3")}, free edge {far.ToString("F3")} in the hinge frame, rises {rise:F2} m at {AirbrakePanelAngle} deg");
                        hinges.Add(h);
                    }
                    if (hinges.Count != AirbrakePanelCount) throw new Exception($"airbrake panels: {hinges.Count} in the contract, {AirbrakePanelCount} expected (model built with msb_spec.SPOILERS1912 = False? then set AirbrakePanels1912 = false)");
                    if (Mathf.Abs((float)contract["airbrake"]["max_angle"] - AirbrakePanelAngle) > 0.01f) throw new Exception($"airbrake max_angle: contract {(float)contract["airbrake"]["max_angle"]} != AirbrakePanelAngle {AirbrakePanelAngle}");
                    S(ab, "transforms", hinges.ToArray()); S(ab, "maxAngle", AirbrakePanelAngle);
                    L($"1.9.12 airbrake panels: {hinges.Count} spoiler panels on the stock Airbrake, maxAngle {AirbrakePanelAngle}");
                }
            }
        }

