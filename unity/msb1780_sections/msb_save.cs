        static GameObject SaveEverything()
        {
            var bank = Folder + "/Generated/MSB17_meshes.asset";
            AssetDatabase.CreateAsset(generatedMeshes[0], bank);
            foreach (var m in generatedMeshes.Skip(1)) AssetDatabase.AddObjectToAsset(m, bank);

            // airfoils: the B-17G set (same wing / tail / flaps / ailerons; the wing's minimum drag lowered to WingCd0)
            var coinParams = Asset<AircraftParameters>("MonoBehaviour/COINParameters_PLACEHOLDER.asset");
            var wing = new Airfoil { name = "MSB17_wing", liftCoef = Mirror(WingCL), dragCoef = B17GWingDrag() };
            var tail = new Airfoil { name = "MSB17_tail", liftCoef = Mirror(new[] { (-3.142f, 0f), (-1.571f, 0f), (-0.785f, -0.9f), (-0.45f, -0.8f), (-0.3f, -1.1f), (0f, 0f), (0.3f, 1.1f), (0.45f, 0.8f), (0.785f, 0.9f), (1.571f, 0f), (3.142f, 0f) }), dragCoef = WingDrag() };
            var ail = new Airfoil { name = "MSB17_aileron", liftCoef = Mirror(OwnAileronAirfoil ? AileronCL : WingCL), dragCoef = WingDrag() };
            var flp = new Airfoil { name = "MSB17_flap", liftCoef = Mirror(FlapCL), dragCoef = FlapDrag() };
            var rud = new Airfoil { name = "MSB17_rudder", liftCoef = Mirror(RudderCL194), dragCoef = WingDrag() };   // 1.9.4 (RudderAirfoil194): the tail's drag

            // liveries: two per faction, none shared (memory liveries-both-factions; design 4.3)
            var facBDF = coinParams.liveries[0].faction; var facPALA = coinParams.liveries[2].faction;
            var livs = new List<AircraftParameters.Livery>();
            foreach (var (file, label, fac, _) in Liveries)
            {
                var ld = ScriptableObject.CreateInstance<LiveryData>();
                var (gloss, cols) = LiveryJson(file);
                ld.Texture = tex[file]; ld.Glossiness = gloss; ld.Colors = cols;
                var p = $"{Folder}/Liveries/{file}.asset";
                AssetDatabase.CreateAsset(ld, p);
                livs.Add(new AircraftParameters.Livery { name = label, faction = fac == "BDF" ? facBDF : facPALA, assetReference = new AssetReferenceLiveryData(AssetDatabase.AssetPathToGUID(p)) });
            }

            var prm = Object.Instantiate(Asset<AircraftParameters>("MonoBehaviour/CAS1Parameters_PLACEHOLDER.asset"));
            prm.HUDExtras = StockHUDExtras ? Asset<GameObject>("GameObject/COIN_HUDExtras_PLACEHOLDER.prefab") : null;
            prm.name = "MSB17_Parameters";
            if (OwnStatusDisplay || OwnMapIcon) BuildDiagramSprites();
            if (OwnStatusDisplay) prm.StatusDisplay = BuildStatusDisplayPrefab();
            prm.aircraftName = DisplayName; prm.rankRequired = 4;
            prm.airfoils = RudderAirfoil194 ? new[] { wing, tail, ail, flp, rud } : new[] { wing, tail, ail, flp };
            prm.liveries = livs;
            // loadouts: one entry per hardpoint set (SetOrder, then the built-in stations); design 2.4 standard loadouts
            var nSets = weaponManager.hardpointSets.Length;
            var builtIn = stationSets.Select(x => x.ammo).ToList();
            WeaponMount Mt(string n) => Asset<WeaponMount>($"MonoBehaviour/{n}_PLACEHOLDER.asset");
            NuclearOption.SavedMission.Loadout LO(string bay = null, string tandem = null, string racks = null, string def = "AAM1_double_internal", string inner = null, string outer = null)
            {
                var w = new List<WeaponMount> { bay != null ? Mt(bay) : null, tandem != null ? Mt(tandem) : null, racks != null ? Mt(racks) : null, def != null ? Mt(def) : null,
                                                 inner != null ? Mt(inner) : null, outer != null ? Mt(outer) : null };
                w.AddRange(builtIn);
                return new NuclearOption.SavedMission.Loadout { weapons = w };
            }
            var strike = LO(bay: "bomb_500_internalx8", inner: "AGM_heavy_triple", outer: "AGM1_triple");
            prm.loadouts = new List<NuclearOption.SavedMission.Loadout>
            {
                new NuclearOption.SavedMission.Loadout { weapons = Enumerable.Repeat<WeaponMount>(null, 6).Concat(builtIn).ToList() },
                strike,
            };
            prm.StandardLoadouts = new[]
            {
                new StandardLoadout { Name = "Strike (8 x GPO-500, 6 x AGM-68, 6 x AGM-48, 4 x MMR-S3)", loadout = strike, FuelRatio = 0.6f },
                new StandardLoadout { Name = "Precision strike (16 x PAB-250LR, 2 x GBM-500LR, 6 x AGM-48)", loadout = LO(tandem: "bomb_250_glide_internalx8", inner: "bomb_500_glide_single", outer: "AGM1_triple"), FuelRatio = 0.6f },
                new StandardLoadout { Name = "SEAD (6 x ARAD-116, 6 x AGM-68)", loadout = LO(bay: "ARM1_internalx4", inner: "AGM_heavy_triple", outer: "ARM1_single"), FuelRatio = 0.6f },
                new StandardLoadout { Name = "Anti-ship (8 x AGM-99, 6 x AGM-68)", loadout = LO(bay: "AShM2_internalx6", inner: "AGM_heavy_triple", outer: "AShM2_single"), FuelRatio = 0.6f },
                new StandardLoadout { Name = "Nuclear (4 x GPO-N 1.5 kt, 4 x AAM-29)", loadout = LO(bay: "nuclearBomb1_internalx4_stack", outer: "AAM2_double"), FuelRatio = 0.8f },
                new StandardLoadout { Name = "Stand-off (2 x ALM-C450, 6 x AGM-68, 4 x AAM-29)", loadout = LO(bay: "CruiseMissile1_internalx2", inner: "AGM_heavy_triple", outer: "AAM2_double"), FuelRatio = 0.7f },
                new StandardLoadout { Name = "Bunker (4 x GPO-2P, 4 x GPO-500, 6 x AGM-48)", loadout = LO(bay: "bomb_penetrator1_internalx4", inner: "bomb_500_double", outer: "AGM1_triple"), FuelRatio = 0.6f },
                new StandardLoadout { Name = "Air defence (3 x AAM-36 bay, 6 x AAM-29, 4 x AAM-36)", loadout = LO(bay: "AAM4_triple_internal", inner: "AAM2_triple", outer: "AAM4_double"), FuelRatio = 0.7f },
            };
            prm.DefaultFuelLevel = 0.6f;
            prm.PIDReferenceAirspeed = 140f; prm.maxSpeed = 215f; prm.takeoffSpeed = 52f; prm.takeoffDistance = 1000f;
            prm.aircraftGLimit = AiLookaheadGLimit;
            prm.turningRadius = AiTurningRadius; prm.cornerSpeed = AiCornerSpeed; prm.approachSpeed = AiApproachSpeed; prm.landingSpeed = AiLandingSpeed; prm.shortLandingSpeed = AiLandingSpeed;
            prm.cruiseThrottle = AiCruiseThrottle; prm.minimumRadarAlt = AiMinRadarAlt; prm.groundTurningRadius = 30f;
            AssetDatabase.CreateAsset(prm, Folder + "/MSB17_Parameters.asset");

            float total = parts.Values.Sum(p => p.mass);
            var def = Object.Instantiate(Asset<AircraftDefinition>("MonoBehaviour/CI-22_PLACEHOLDER.asset"));
            def.name = "MSB17";
            def.jsonKey = JsonKey; def.WorkshopTag = DisplayName; def.unitName = DisplayName; def.code = DisplayName; def.bogeyName = "";
            def.description = "MSB-17, the B-17 rebuilt for the 2080s: a BDF heavy multirole strike aircraft. Four 5,400 shp turboshafts drive " +
                "contra-rotating propellers; a 5.7 m digital weapons bay, two defensive side bays and four wing pylons carry up to 7 t; automated " +
                "twin 20 mm turrets in the chin and tail and two 120 kW anti-missile lasers defend it. Crew of four in ejection seats.";
            def.length = 23.2f; def.width = 31.62f; def.height = 6.1f; def.mass = total;
            def.value = 110f; def.radarSize = 1.2f; def.visibleRange = 7000f; def.manpower = 4;
            def.roleIdentity.antiSurface = 1.0f; def.roleIdentity.antiAir = 0.4f; def.roleIdentity.antiMissile = 0.3f; def.roleIdentity.antiRadar = 0.4f;
            def.armorTier = 1f; def.damageTolerance = 1.5f;
            def.spawnOffset = new Vector3(0f, spawnHeight, 0f);
            def.restRotation = SpawnThreePoint ? new Vector3(-ThreePointDeg, 0f, 0f) : Vector3.zero;
            def.aircraftParameters = prm;
            if (OwnMapIcon) { def.mapIcon = mapIconSprite; def.mapIconSize = 1.3f; def.mapOrient = true; }
            def.aircraftInfo = new AircraftInfo { emptyWeight = 24500f, maxSpeed = 790f, stallSpeed = 170f, maneuverability = 5.5f, maxWeight = 43000f };
            def.unitPrefab = null;
            AssetDatabase.CreateAsset(def, Folder + "/MSB17.asset");
            foreach (var u in root.GetComponentsInChildren<Unit>(true)) u.definition = def;
            var rb = root.GetComponent<Rigidbody>(); rb.mass = total;
            // laser mount prefabs (GA-25X pattern): one per laser station, spawned on its aperture hardpoint
            foreach (var t in turrets.Where(t => t.laser && t.laserGO != null))
            {
                var lp = PrefabUtility.SaveAsPrefabAsset(t.laserGO, Folder + "/" + t.laserGO.name + ".prefab");
                Object.DestroyImmediate(t.laserGO); t.laserGO = null;
                var ss = stationSets.First(x => x.station == t.station);
                ss.ammo.prefab = lp; EditorUtility.SetDirty(ss.ammo);
                L($"laser mount prefab {lp.name} -> {ss.ammo.name}");
            }
            if (FireClear1814On && DefensiveTurrets)
            {   // bore-line sweep: the 20 mm from both muzzles, the lasers from their aperture (FireClear1814.MuzzleOverride, MSB-only hook)
                FireClear1814.MuzzleOverride = tr => { var ap = tr.transform.parent != null ? tr.transform.parent.GetComponentsInChildren<Transform>(true).FirstOrDefault(x => x.name.EndsWith("_aperture")) : null; return ap != null ? new[] { ap } : null; };
                try { FireClear1814.Apply(root, L, FireClearJson); } finally { FireClear1814.MuzzleOverride = null; }
            }
            var prefab = PrefabUtility.SaveAsPrefabAsset(root, Folder + "/MSB17.prefab");
            def.unitPrefab = prefab;
            EditorUtility.SetDirty(def);
            var op = ScriptableObject.CreateInstance<Blueprinter.OpAddAircraftToHangars>();
            op.aircraftJsonKey = JsonKey;
            op.hangars.Add(new Blueprinter.OpAddAircraftToHangars.HangarTarget { hangarUnitJsonKey = "hangar_med", hangarNames = { "hangar_med" } });
            AssetDatabase.CreateAsset(op, Folder + "/OpAddAircraftToHangars.asset");
            AssetDatabase.SaveAssets();
            L($"saved prefab, definition (mass {total} kg, spawn y {spawnHeight:F3}, rest {def.restRotation}), parameters, {livs.Count} liveries, {nSets} hardpoint sets, {generatedMeshes.Count} meshes");
            return prefab;
        }

