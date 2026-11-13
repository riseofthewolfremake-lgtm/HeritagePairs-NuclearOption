            // round 5 (wreck fire, coordinator 2026-11-06; study: nuclearoption-ref/study/b17g/ai_round/d_ab4_fx.txt, d_stock_fx.txt):
            // stock wrecks burn through FuelTank components. A tank leaks / ignites from damage, crash g or detachment, spawns fire_med +
            // a fireball at its part's ORIGIN, burns nearby colliders (FuelTankFire) and punctures its connectedTanks when its part breaks
            // off (FuelTank.cs FuelTank_OnDetach). Unit.RpcFuelTankStatus finds the tank with part.TryGetComponent<FuelTank>(), so one tank
            // per part, on the part's own GameObject. The model puts those parts' origins on their tank (wing cells between the spars,
            // nacelle oil tanks, waist section; the centre section's origin is the datum in the bomb bay = the bay ferry tank).
            // Settings: the AB-4 (FastBomber1) heavy-bomber tanks (ruptureG 50-300, ignitionG 40-400, pierce 5-100, blast 4-100,
            // fireIntensity 1.5) instead of the CI-22 light-aircraft tank (rupture 100-500, ignition 200-500, fireIntensity 1).
            var tplWingTank = TplComp<FuelTank>("FastBomber1:wingroot_L");      // fuelLeak, fire_med, fireball_medium
            var tplBodyTank = TplComp<FuelTank>("FastBomber1:fuselage_R");      // fuelLeak, fire_med, fireball_large
            var tankKg = new List<(string part, float kg, FuelTank tpl)>();
            foreach (var sd in new[] { "L", "R" })
            {
                tankKg.Add(("wing_inner_" + sd, 1000f, tplWingTank));   // inboard engine tanks
                tankKg.Add(("wing_mid_" + sd, 650f, tplWingTank));      // outboard engine tank + feeder
                tankKg.Add(("wing_outer_" + sd, 400f, tplWingTank));    // Tokyo tanks (9 cells)
            }
            foreach (var n in EngineNums) tankKg.Add(("nacelle_" + n, 50f, tplWingTank));   // oil tank + feed lines behind the firewall
            tankKg.Add(("B17G", 200f, tplBodyTank));                     // bomb-bay ferry tank / centre-section lines (fus_center)
            tankKg.Add(("fus_waist", 100f, tplBodyTank));                // waist: transfer lines aft (fus_radio keeps the datum origin, see design 17)
            if (Mathf.Abs(tankKg.Sum(t => t.kg) - FuelKg) > 0.5f) throw new Exception($"fuel split {tankKg.Sum(t => t.kg)} != {FuelKg}");
            var tanks = new Dictionary<string, FuelTank>();
            foreach (var (p, kg, tp) in tankKg)
            {
                var ft = CloneComp(tp, parts[p].gameObject);
                S(ft, "fuelCapacity", kg); S(ft, "fuelMass", kg); S(ft, "part", parts[p]);
                tanks[p] = ft;
            }
            foreach (var t in tanks.Values) SetSeq(t, "connectedTanks", new object[0]);
            void Link(string a, string b) { var la = ((FuelTank[])G(tanks[a], "connectedTanks")).ToList(); if (!la.Contains(tanks[b])) la.Add(tanks[b]); S(tanks[a], "connectedTanks", la.ToArray()); }
            foreach (var sd in new[] { "L", "R" })
            {   // inner <-> mid <-> outer, inner <-> centre section; a detaching wing part punctures its neighbours
                Link("wing_inner_" + sd, "wing_mid_" + sd); Link("wing_mid_" + sd, "wing_inner_" + sd);
                Link("wing_mid_" + sd, "wing_outer_" + sd); Link("wing_outer_" + sd, "wing_mid_" + sd);
                Link("wing_inner_" + sd, "B17G"); Link("B17G", "wing_inner_" + sd);
            }
            L("fuel tanks: " + string.Join(", ", tanks.Select(kv => $"{kv.Key} {G(kv.Value, "fuelCapacity")} kg -> [{string.Join(" ", ((FuelTank[])G(kv.Value, "connectedTanks")).Select(c => c.name))}]")));
            // the small 'fire_tiny' damage effect: off the prop hubs (CI-22 propHub template: 3 small fires on the wreck, 11_wreck.jpg),
            // onto the engine parts (origin at the cowl) below 30 hit points
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
                L($"engine fire effect: {(hubFx != null ? hubFx.prefab.name : "NONE")} at 30 hp on engine_1..4, none on the props");
            }
