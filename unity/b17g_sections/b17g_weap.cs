        static WeaponMount ammoCannon, ammo50;
        static readonly List<(string station, WeaponMount ammo, HardpointSet set)> stationSets = new List<(string, WeaponMount, HardpointSet)>();
        static HardpointSet baySet;
        static List<Gun> Weapons()
        {
            stationSets.Clear();
            var sets = new List<HardpointSet>();
            HardpointSet Set(string name, IEnumerable<WeaponMount> options, params Hardpoint[] hps)
            {
                var hs = new HardpointSet { name = name, precludingHardpointSets = new List<byte>(), SymmetryWithPrev = false, SymmetryName = "", weaponOptions = new List<WeaponMount> { null }, hardpoints = hps.ToList() };
                hs.weaponOptions.AddRange(options);
                sets.Add(hs); return hs;
            }
            Hardpoint HP(Transform t, AeroPart part, Weapon[] builtIn = null, BayDoor[] doors = null, float doorTime = 1f)
            {
                var h = new Hardpoint { transform = t, part = part, bayDoors = doors ?? new BayDoor[0], doorOpenDuration = doorTime, BuiltInWeapons = builtIn ?? new Weapon[0], BuiltInTurrets = new Turret[0] };
                S(h, "pylonOptions", Array.CreateInstance(Elem(Fld(typeof(Hardpoint), "pylonOptions")), 0));
                return h;
            }
            // bomb bay: centre hardpoint, two doors hinged at the outer edges (EW1 BayDoor values, B-25H method). Blender +92 deg about +Y (L)
            // = Unity -92 about +Z; the check verifies both doors swing DOWN and OUT.
            var bay = Find("hp_bombbay");
            var doorAudio = CloneComp(TplAudio("COIN:cockpit_F", "cricket_startup"), bay.gameObject);
            doorAudio.clip = null; doorAudio.loop = false; doorAudio.playOnAwake = false; doorAudio.volume = 0.8f;
            var bayDoors = new List<BayDoor>();
            foreach (var (dn, open) in new[] { ("bay_door_L", -92f), ("bay_door_R", 92f) })
            {
                var hb = DoorHinge(Find(dn), Vector3.forward, open, false);
                var bd = CloneComp(TplComp<BayDoor>("EW1:weapon_door_hinge_L"), hb.gameObject);
                S(bd, "hingeAngle", open); S(bd, "openSpeed", 1.0f); S(bd, "closeSpeed", 0.7f); S(bd, "doorAudioSource", doorAudio);
                bayDoors.Add(bd);
            }
            // user decision 2026-11-03: 8 x PAB-250 (default), 4 x GPO-500 (stacked, bay lengthened to 2.95 m), 2 x CBO-400, GPO-N; no wing racks
            // 1.6.1: the stock CBO-400 mounts are switched off in the game data (bomb_cluster1_dual_internal.asset 'disabled: 1'; WeaponChecker
            // .MountAllowedHQ -> WeaponMount.IsAllowed drops them, WeaponMount.cs 93-97), so 1.6.0 showed no CBO-400. The B-17G carries its
            // own enabled copy (same prefab, info and 2 bombs). GPO-N stays the stock mount: the hangar offers a nuclear mount only when the
            // mission allows tactical weapons, the player's rank reaches tacticalMinRank and the airbase holds the warheads
            // (WeaponChecker.MountAllowedNuclear, WeaponChecker.cs 184-199) - mission rules, not the aircraft.
            var bayMounts = new List<WeaponMount> { Mount("bomb_250_internalx8"), Mount("bomb_500_internalx4_stack") };
            if (ClusterBombOption)
            {
                var cbo = Object.Instantiate(Mount("bomb_cluster1_dual_internal")); cbo.name = "B17G_cbo400_x2"; cbo.jsonKey = cbo.name; cbo.mountName = "CBO-400 x2";
                S(cbo, "disabled", false);
                AssetDatabase.CreateAsset(cbo, Folder + "/" + cbo.name + ".asset");
                bayMounts.Add(cbo);
            }
            if (NuclearOptions) bayMounts.Add(Mount("nuclearBomb1_internal"));
            baySet = Set("Bomb Bay", bayMounts, HP(bay, parts["B17G"], null, bayDoors.ToArray(), 1.5f));

            // gun stations: 13 stock 12.7 mm in 9 positions. One renamed copy of the stock Gun12.7mm info per STATION (stations are keyed by
            // WeaponInfo: WeaponManager.cs:403-438, Turret.cs:242), so a power turret never fires because a waist gun saw a target
            // (WeaponStation.Fire fires every gun of its station, WeaponStation.cs:523).
            var tAmmo = Asset<WeaponMount>("MonoBehaviour/gun_ammo_35mm_720_PLACEHOLDER.asset");
            var ammoPrefabGO = new GameObject("B17G_internal_ammo");
            var ammoPrefab = PrefabUtility.SaveAsPrefabAsset(ammoPrefabGO, Folder + "/B17G_internal_ammo.prefab");
            Object.DestroyImmediate(ammoPrefabGO);
            if (DefensiveTurrets && contract != null)
            {
                BuildTurrets();
                foreach (var g in turrets.GroupBy(t => t.station).OrderBy(g => Array.IndexOf(StationOrder, g.Key)))
                {
                    var info = stationInfos[g.Key];
                    var ammo = Object.Instantiate(tAmmo); ammo.name = "B17G_ammo_" + g.Key.ToLowerInvariant();
                    ammo.prefab = ammoPrefab; ammo.jsonKey = ammo.name; ammo.info = info;
                    int perCycle = g.Sum(t => (int)G(t.gun, "magazineCapacity")), barrels = g.Sum(t => ((Transform[])G(t.gun, "muzzles")).Length);
                    ammo.ammo = perCycle; ammo.GunAmmo = true; ammo.mass = g.Sum(t => (int)G(t.gun, "magazineCapacity") * ((Transform[])G(t.gun, "muzzles")).Length) * 0.11f;
                    ammo.mountName = $".50 cal {g.Key} x{barrels}";
                    AssetDatabase.CreateAsset(ammo, Folder + "/" + ammo.name + ".asset");
                    var hs = Set(g.Key + " guns", new[] { ammo }, g.Select(t => { var h = HP(t.mount, t.part, new Weapon[] { t.gun }); h.BuiltInTurrets = new[] { t.turret }; return h; }).ToArray());
                    stationSets.Add((g.Key, ammo, hs));
                }
            }
            var all = sets.SelectMany(x => x.hardpoints).OrderByDescending(h => h.transform.position.x).ThenByDescending(h => h.transform.position.z).ToList();
            for (int i = 0; i < all.Count; i++) all[i].HardpointIndex = i;
            weaponManager.hardpointSets = sets.ToArray();
            S(weaponManager, "aircraft", aircraft);
            L($"hardpoint sets: {string.Join(" | ", sets.Select(x => $"{x.name} ({x.hardpoints.Count} hp, {x.weaponOptions.Count - 1} options)"))}");
            return turrets.Select(t => t.gun).ToList();
        }

