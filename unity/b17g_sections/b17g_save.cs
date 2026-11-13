        static GameObject SaveEverything()
        {
            var bank = Folder + "/Generated/B17G_meshes.asset";
            AssetDatabase.CreateAsset(generatedMeshes[0], bank);
            foreach (var m in generatedMeshes.Skip(1)) AssetDatabase.AddObjectToAsset(m, bank);

            // airfoils (AeroJob_Math sign convention: physical curves mirrored, B-25H): 0 wing (Boeing 103-like, CLmax 1.45 at 16 deg,
            // gentle post-stall), 1 tail (symmetric), 2 aileron (Nimrod 1.4.2 lesson: a deflected aileron is a plain flap)
            var coinParams = Asset<AircraftParameters>("MonoBehaviour/COINParameters_PLACEHOLDER.asset");
            var drag = coinParams.airfoils[0].dragCoef;
            var wing = new Airfoil { name = "B17G_wing", liftCoef = Mirror(WingCL), dragCoef = B17GWingDrag() };
            var tail = new Airfoil { name = "B17G_tail", liftCoef = Mirror(new[] { (-3.142f, 0f), (-1.571f, 0f), (-0.785f, -0.9f), (-0.45f, -0.8f), (-0.3f, -1.1f), (0f, 0f), (0.3f, 1.1f), (0.45f, 0.8f), (0.785f, 0.9f), (1.571f, 0f), (3.142f, 0f) }), dragCoef = new AnimationCurve(drag.keys) };
            var ail = new Airfoil { name = "B17G_aileron", liftCoef = Mirror(OwnAileronAirfoil ? AileronCL : WingCL), dragCoef = WingDrag() };
            var flp = new Airfoil { name = "B17G_flap", liftCoef = Mirror(FlapCL), dragCoef = FlapDrag() };

            var facBDF = coinParams.liveries[0].faction; var facPALA = coinParams.liveries[2].faction;
            var livs = new List<AircraftParameters.Livery>();
            var livGuid = new Dictionary<string, string>();
            foreach (var (file, label, fac, _) in Liveries)
            {
                var ld = ScriptableObject.CreateInstance<LiveryData>();
                var (gloss, cols) = LiveryJson(file);
                ld.Texture = tex[file]; ld.Glossiness = gloss; ld.Colors = cols;
                var p = $"{Folder}/Liveries/{file}.asset";
                AssetDatabase.CreateAsset(ld, p);
                livGuid[file] = AssetDatabase.AssetPathToGUID(p);
            }
            // user decision: the two USAAF schemes for both factions, two own schemes per faction (own faction's first)
            foreach (var side in new[] { "BDF", "PALA" })
                foreach (var (file, label, fac, both) in Liveries.Where(x => !x.both && x.faction == side).Concat(Liveries.Where(x => x.both)))
                    livs.Add(new AircraftParameters.Livery { name = label, faction = side == "BDF" ? facBDF : facPALA, assetReference = new AssetReferenceLiveryData(livGuid[file]) });

            var prm = Object.Instantiate(Asset<AircraftParameters>("MonoBehaviour/CAS1Parameters_PLACEHOLDER.asset"));
            prm.HUDExtras = StockHUDExtras ? Asset<GameObject>("GameObject/COIN_HUDExtras_PLACEHOLDER.prefab") : null;
            prm.name = "B17G_Parameters";
            if (OwnStatusDisplay || OwnMapIcon) BuildDiagramSprites();
            if (OwnStatusDisplay) prm.StatusDisplay = BuildStatusDisplayPrefab();
            prm.aircraftName = DisplayName; prm.rankRequired = 3;
            prm.airfoils = new[] { wing, tail, ail, flp };
            prm.liveries = livs;
            // loadouts: one entry per hardpoint set (Bomb Bay, then the gun stations in StationOrder)
            var ammo = stationSets.Select(x => x.ammo).ToList();
            NuclearOption.SavedMission.Loadout LO(WeaponMount bay) => new NuclearOption.SavedMission.Loadout { weapons = new[] { bay }.Concat(ammo).ToList() };
            prm.loadouts = new List<NuclearOption.SavedMission.Loadout>
            {
                new NuclearOption.SavedMission.Loadout { weapons = Enumerable.Repeat<WeaponMount>(null, 1 + ammo.Count).ToList() },
                LO(Mount("bomb_250_internalx8")),
            };
            prm.StandardLoadouts = new[]
            {
                new StandardLoadout { Name = "General purpose (8 x PAB-250)", loadout = LO(Mount("bomb_250_internalx8")), FuelRatio = 0.6f },
                new StandardLoadout { Name = "Heavy (4 x GPO-500)", loadout = LO(Mount("bomb_500_internalx4_stack")), FuelRatio = 0.5f },
                new StandardLoadout { Name = "Area (2 x CBO-400)", loadout = LO(Mount("bomb_cluster1_dual_internal")), FuelRatio = 0.6f },
            };
            prm.DefaultFuelLevel = 0.6f;
            prm.PIDReferenceAirspeed = 85f; prm.maxSpeed = 100f; prm.takeoffSpeed = 47f; prm.takeoffDistance = 1150f;
            prm.aircraftGLimit = AiLookaheadGLimit;   // 1.7.8: 3 -> 0.8 (terrain-follow look-ahead only; b17g_head.cs). 1.7.10: the line above was swallowed by this comment in 1.7.8/1.7.9 (template 180/215/80/500 in game)
            // 1.7.0 AI landing (AIPilotLandingState): pattern speed = cornerSpeed + 0.02 x distance, glideslope aimpoint 3 x turningRadius out,
            // final speed = sqrt(m / maxWeight) x landingSpeed + 0.015 x (distance - 500). 1.6.9 flew the pattern at 100-111 m/s, 7.5 km
            // out over the Maris hills, could not slow down and went around / flew into the ridge. Stock heavy SFB-81: turningRadius 1500.
            prm.turningRadius = AiTurningRadius; prm.cornerSpeed = AiCornerSpeed; prm.approachSpeed = 58f; prm.landingSpeed = AiLandingSpeed; prm.shortLandingSpeed = AiLandingSpeed;
            // cruiseThrottle is also the AI landing-state throttle cap (0.55 in 1.6.8 left an AI B-17 mushing into a hill); stock heavies 1.0.
            // 1.6.9 bug: a // comment swallowed minimumRadarAlt / groundTurningRadius (CAS1 template values were used).
            prm.cruiseThrottle = AiCruiseThrottle; prm.minimumRadarAlt = AiMinRadarAlt; prm.groundTurningRadius = 30f;
            AssetDatabase.CreateAsset(prm, Folder + "/B17G_Parameters.asset");

            float total = parts.Values.Sum(p => p.mass);
            var def = Object.Instantiate(Asset<AircraftDefinition>("MonoBehaviour/CI-22_PLACEHOLDER.asset"));
            def.name = "B17G";
            def.jsonKey = JsonKey; def.WorkshopTag = DisplayName; def.unitName = DisplayName; def.code = "B-17G"; def.bogeyName = "";
            def.description = "Boeing B-17G Flying Fortress, 1944. A four-engine heavy bomber built to fight its way to the target: thirteen " +
                ".50 calibre guns in chin, top, ball and tail turrets and flexible cheek, waist and radio positions, a bomb bay for up to 4,400 lb, " +
                "and four 1,200 hp Wright R-1820 Cyclones. Slow and steady, it takes punishment no other bomber can; crew of ten.";
            def.length = 22.66f; def.width = 31.62f; def.height = 5.82f; def.mass = total;
            def.value = 45f; def.radarSize = 3.0f; def.visibleRange = 7000f; def.manpower = 10;
            def.roleIdentity.antiSurface = 0.9f; def.roleIdentity.antiAir = 0.1f;
            def.spawnOffset = new Vector3(0f, spawnHeight, 0f);
            def.restRotation = SpawnThreePoint ? new Vector3(-ThreePointDeg, 0f, 0f) : Vector3.zero;
            def.aircraftParameters = prm;
            if (OwnMapIcon) { def.mapIcon = mapIconSprite; def.mapIconSize = 1.3f; def.mapOrient = true; }
            def.aircraftInfo = new AircraftInfo { emptyWeight = 16390f, maxSpeed = 460f, stallSpeed = 150f, maneuverability = 3f, maxWeight = 29700f };
            def.unitPrefab = null;
            AssetDatabase.CreateAsset(def, Folder + "/B17G.asset");
            foreach (var u in root.GetComponentsInChildren<Unit>(true)) u.definition = def;
            var rb = root.GetComponent<Rigidbody>(); rb.mass = total;
            if (FireClear1814On && DefensiveTurrets) FireClear1814.Apply(root, L, FireClearJson);   // 1.8.14: after colliders / meshes / guns are final
            var prefab = PrefabUtility.SaveAsPrefabAsset(root, Folder + "/B17G.prefab");
            def.unitPrefab = prefab;
            EditorUtility.SetDirty(def);
            var op = ScriptableObject.CreateInstance<Blueprinter.OpAddAircraftToHangars>();
            op.aircraftJsonKey = JsonKey;
            op.hangars.Add(new Blueprinter.OpAddAircraftToHangars.HangarTarget { hangarUnitJsonKey = "hangar_med", hangarNames = { "hangar_med" } });
            AssetDatabase.CreateAsset(op, Folder + "/OpAddAircraftToHangars.asset");
            AssetDatabase.SaveAssets();
            L($"saved prefab, definition (mass {total} kg, spawn y {spawnHeight:F3}, rest {def.restRotation}), parameters, {livs.Count} liveries, {generatedMeshes.Count} meshes");
            return prefab;
        }

        static (float t, float v)[] WingCL => new[] { (-3.142f, 0f), (-1.571f, 0f), (-0.785f, -0.95f), (-0.36f, -0.75f), (-0.24f, -0.95f), (0f, 0.15f), (0.15f, 0.90f),
            (0.2443f, 1.40f), (0.2793f, 1.45f), (0.33f, 1.38f), (0.42f, 1.25f), (0.6f, 1.10f), (0.785f, 0.95f), (1.571f, 0f), (3.142f, 0f) };
        // 1.6.3 flap (airfoil 3): the wing curve up to 14 deg (retracted flaps fly as wing), then a deflected-flap section peaking ~2.0 at 34 deg
        static (float t, float v)[] FlapCL => new[] { (-3.142f, 0f), (-1.571f, 0f), (-0.785f, -0.95f), (-0.36f, -0.75f), (-0.24f, -0.95f), (0f, 0.15f), (0.15f, 0.90f),
            (0.2443f, 1.40f), (0.33f, 1.62f), (0.45f, 1.85f), (0.59f, 2.0f), (0.75f, 1.7f), (1.0f, 1.15f), (1.571f, 0f), (3.142f, 0f) };
        // 1.6.7 wing drag (airfoil 0): the B-25H curve below 1.5 deg (top speed), more induced drag at climb / take-off angles (CD 0.036 at
        // 4.3 deg, 0.072 at 7.2 deg; B-25H 0.024 / 0.040) so a power that gives ~450 km/h does not climb at 10+ m/s (spec ~4.6)
        static AnimationCurve B17GWingDrag()
        {
            var pts = new[] { (0f, 0.008f), (0.025f, 0.0114f), (0.05f, 0.022f), (0.075f, 0.036f), (0.1f, 0.052f), (0.126f, 0.072f), (0.15f, 0.092f), (0.2f, 0.14f), (0.28f, 0.20f), (0.35f, 0.29f), (0.5f, 0.5f), (1.51f, 1.7f), (3.14159f, 0f) };
            var keys = new List<Keyframe>();
            foreach (var (t, v) in pts.Reverse()) if (t > 0f) keys.Add(new Keyframe(-t, v));
            foreach (var (t, v) in pts) keys.Add(new Keyframe(t, v));
            var c = new AnimationCurve(keys.ToArray());
            for (int i = 0; i < c.length; i++) c.SmoothTangents(i, 0f);
            return c;
        }
        static AnimationCurve FlapDrag()
        {
            var pts = new[] { (0f, 0.008f), (0.06f, 0.021f), (0.1f, 0.036f), (0.2f, 0.075f), (0.35f, 0.12f), (0.5f, 0.17f), (0.65f, 0.25f), (0.9f, 0.6f), (1.51f, 1.7f), (3.14159f, 0f) };
            var keys = new List<Keyframe>();
            foreach (var (t, v) in pts.Reverse()) if (t > 0f) keys.Add(new Keyframe(-t, v));
            foreach (var (t, v) in pts) keys.Add(new Keyframe(t, v));
            var c = new AnimationCurve(keys.ToArray());
            for (int i = 0; i < c.length; i++) c.SmoothTangents(i, 0f);
            return c;
        }
        static (float t, float v)[] AileronCL => new[] { (-3.142f, 0f), (-1.571f, 0f), (-0.785f, -1.10f), (-0.62f, -1.30f), (-0.52f, -1.35f), (-0.40f, -1.25f), (-0.24f, -0.95f), (0f, 0.15f), (0.15f, 0.90f),
            (0.2793f, 1.45f), (0.40f, 1.70f), (0.52f, 1.85f), (0.62f, 1.80f), (0.785f, 1.40f), (1.571f, 0f), (3.142f, 0f) };

        // spawn: root (CG) height so that, pitched to the 3-point attitude about the root, the lowest wheel bottom touches y = 0 (+3 cm)
        static float spawnHeight = 3f;
        static void ComputeSpawn(List<LandingGear> gears)
        {
            var q = Quaternion.Euler(SpawnThreePoint ? -ThreePointDeg : 0f, 0, 0);
            float low = float.MaxValue;
            foreach (var g in gears)
            {
                var ax = root.transform.InverseTransformPoint(((Transform)G(g, "axle")).position);
                var p = q * (ax - new Vector3(0, (float)G(g, "wheelRadius"), 0));
                low = Mathf.Min(low, p.y);
            }
            spawnHeight = -low + 0.03f;
            L($"spawn: 3-point {ThreePointDeg} deg, root {spawnHeight:F3} m above ground");
        }

