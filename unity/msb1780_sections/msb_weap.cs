        static WeaponMount ammoCannon, ammo50;
        static readonly List<(string station, WeaponMount ammo, HardpointSet set)> stationSets = new List<(string, WeaponMount, HardpointSet)>();
        static HardpointSet baySet;
        static readonly List<HardpointSet> msbSets = new List<HardpointSet>();
        // sets in loadout order (index = Loadout.weapons index): the three bay arrangements exclude each other (HardpointSet.BlockedByOtherHardpoint:
        // a set is blocked while any set listed in its precludingHardpointSets carries a weapon), then side bays, pylons, built-in stations
        static readonly string[] SetOrder = { "Bomb Bay", "Bay Tandem", "Bay Racks", "Defensive Bays", "Inner Pylons", "Outer Pylons" };
        static List<Gun> Weapons()
        {
            stationSets.Clear(); msbSets.Clear();
            var sets = msbSets;
            HardpointSet Set(string name, IEnumerable<WeaponMount> options, params Hardpoint[] hps)
            {
                var hs = new HardpointSet { name = name, precludingHardpointSets = new List<byte>(), SymmetryWithPrev = false, SymmetryName = "", weaponOptions = new List<WeaponMount> { null }, hardpoints = hps.ToList() };
                hs.weaponOptions.AddRange(options.Where(o => o != null));
                sets.Add(hs); return hs;
            }
            Hardpoint HP(Transform t, AeroPart part, Weapon[] builtIn = null, BayDoor[] doors = null, float doorTime = 1f)
            {
                var h = new Hardpoint { transform = t, part = part, bayDoors = doors ?? new BayDoor[0], doorOpenDuration = doorTime, BuiltInWeapons = builtIn ?? new Weapon[0], BuiltInTurrets = new Turret[0] };
                S(h, "pylonOptions", Array.CreateInstance(Elem(Fld(typeof(Hardpoint), "pylonOptions")), 0));
                return h;
            }
            WeaponMount M(string n) { var m = Asset<WeaponMount>($"MonoBehaviour/{n}_PLACEHOLDER.asset"); if (m == null) L($"WARN mount {n} missing"); return m; }
            var doorAudio = CloneComp(TplAudio("COIN:cockpit_F", "cricket_startup"), Find("hp_bay").gameObject);
            doorAudio.clip = null; doorAudio.loop = false; doorAudio.playOnAwake = false; doorAudio.volume = 0.8f;
            BayDoor[] Doors(params (string name, float open)[] ds)
            {
                var list = new List<BayDoor>();
                foreach (var (dn, open) in ds)
                {
                    var hb = DoorHinge(Find(dn), Vector3.forward, open, false);
                    var bd = CloneComp(TplComp<BayDoor>("EW1:weapon_door_hinge_L"), hb.gameObject);
                    S(bd, "hingeAngle", open); S(bd, "openSpeed", 1.0f); S(bd, "closeSpeed", 0.7f); S(bd, "doorAudioSource", doorAudio);
                    list.Add(bd);
                }
                return list.ToArray();
            }
            // ---- the 5.7 m bay: two doors hinged at the outer edges (EW-25 BayDoor values, B-17G method); three exclusive arrangements
            var bayDoors = Doors(("bay_door_L", -92f), ("bay_door_R", 92f));
            var root_ = parts["MSB17"];
            var bayCentre = new List<WeaponMount> { M("bomb_500_internalx8"), M("bomb_500_internalx6"), M("AGM_heavy_internalx8"), M("CruiseMissile1_internalx2"),
                M("bomb_penetrator1_internalx4"), M("ARM1_internalx4"), M("bomb_500_glide_internalx6"), M("AShM2_internalx6"), M("AAM4_triple_internal") };
            if (NuclearOptions) bayCentre.Add(M("nuclearBomb1_internalx4_stack"));
            if (NuclearOptions && StrategicGPON) bayCentre.Add(M("nuclearBomb1_strategic_internalx4_stack"));
            baySet = Set("Bomb Bay", bayCentre, HP(Find("hp_bay"), root_, null, bayDoors, 1.5f));
            var tandem = Set("Bay Tandem", new[] { M("bomb_250_internalx8"), M("bomb_250_glide_internalx8") },
                HP(Find("hp_bay_fwd"), root_, null, bayDoors, 1.5f), HP(Find("hp_bay_aft"), root_, null, bayDoors, 1.5f));
            var racks = Set("Bay Racks", new[] { M("bomb_glide1_six_internal"), M("bomb_125_internalx6") },
                HP(Find("hp_bay_L"), root_, null, bayDoors, 1.5f), HP(Find("hp_bay_R"), root_, null, bayDoors, 1.5f));
            baySet.precludingHardpointSets = new List<byte> { 1, 2 }; tandem.precludingHardpointSets = new List<byte> { 0, 2 }; racks.precludingHardpointSets = new List<byte> { 0, 1 };
            // ---- defensive side bays: MMR-S3 x2 each (or IRM-S2 x2), doors hinged at their top edge, open up and out
            if (SideBays190)
            {
                var sd = Doors(("side_bay_door_L", -100f), ("side_bay_door_R", 100f));
                Set("Defensive Bays", new[] { M("AAM1_double_internal"), M("AAM3_double_internal") },
                    HP(Find("hp_def_L"), parts["fus_waist"], null, new[] { sd[0] }, 0.8f), HP(Find("hp_def_R"), parts["fus_waist"], null, new[] { sd[1] }, 0.8f));
            }
            else Set("Defensive Bays", new WeaponMount[0], HP(Find("hp_def_L"), parts["fus_waist"]), HP(Find("hp_def_R"), parts["fus_waist"]));
            // ---- 4 pylons outboard of the outer prop discs (FD-32 lesson: every store launches outside a disc)
            var inner = new[] { M("AGM_heavy_triple"), M("AGM_heavy_double"), M("AShM2_double"), M("ARM1_double"), M("AAM2_triple"), M("bomb_500_double"),
                M("bomb_500_glide_single"), M("bomb_250_glide_double"), M("AGM1_triple"), M("ECMPod1") };
            var outer = new[] { M("AGM1_triple"), M("AGM1_quad"), M("AAM4_double"), M("AAM2_double"), M("AAM1_triple"), M("AGM_heavy_single"), M("ARM1_single"),
                M("AShM2_single"), M("bomb_500_glide_single"), M("ECMPod1") };
            Set("Inner Pylons", Pylons190 ? inner : new WeaponMount[0], HP(Find("hp_inner_L"), parts["wing_outer_L"]), HP(Find("hp_inner_R"), parts["wing_outer_R"]));
            Set("Outer Pylons", Pylons190 ? outer : new WeaponMount[0], HP(Find("hp_outer_L"), parts["wing_outer_L"]), HP(Find("hp_outer_R"), parts["wing_outer_R"]));

            // ---- built-in stations: chin / tail twin 20 mm (own weapon), dorsal / ventral 120 kW lasers; one WeaponInfo per station
            var tAmmo = Asset<WeaponMount>("MonoBehaviour/gun_ammo_35mm_720_PLACEHOLDER.asset");
            var ammoPrefabGO = new GameObject("MSB17_internal_ammo");
            var ammoPrefab = PrefabUtility.SaveAsPrefabAsset(ammoPrefabGO, Folder + "/MSB17_internal_ammo.prefab");
            Object.DestroyImmediate(ammoPrefabGO);
            if (DefensiveTurrets && contract != null)
            {
                BuildTurrets();
                foreach (var st in StationOrder)
                {
                    var tt = turrets.Where(t => t.station == st).ToList();
                    if (tt.Count == 0) continue;
                    var info = stationInfos[st];
                    var ammo = Object.Instantiate(tAmmo); ammo.name = "MSB17_ammo_" + st.ToLowerInvariant();
                    ammo.prefab = ammoPrefab; ammo.jsonKey = ammo.name; ammo.info = info;
                    Hardpoint h;
                    if (tt[0].laser)
                    {
                        ammo.mountName = $"120 kW Laser ({st})"; ammo.ammo = 1; ammo.GunAmmo = false; ammo.mass = 0f;
                        h = HP(TryFind(tt[0].mount.name.Replace("_mount", "_aperture")), tt[0].part);
                    }
                    else
                    {
                        int cycles = (int)G(tt[0].gun, "magazineCapacity"), barrels = ((Transform[])G(tt[0].gun, "muzzles")).Length;
                        ammo.ammo = cycles; ammo.GunAmmo = true; ammo.mass = cycles * barrels * Gun20MassPerRound;
                        ammo.mountName = $"{info.weaponName} ({cycles * barrels} rds)";
                        h = HP(tt[0].mount, tt[0].part, new Weapon[] { tt[0].gun });
                    }
                    AssetDatabase.CreateAsset(ammo, Folder + "/" + ammo.name + ".asset");
                    h.BuiltInTurrets = new[] { tt[0].turret };
                    var hs = Set(StationLabel[st], new[] { ammo }, h);
                    stationSets.Add((st, ammo, hs));
                }
            }
            var all = sets.SelectMany(x => x.hardpoints).Distinct().OrderByDescending(h => h.transform.position.x).ThenByDescending(h => h.transform.position.z).ToList();
            for (int i = 0; i < all.Count; i++) all[i].HardpointIndex = i;
            weaponManager.hardpointSets = sets.ToArray();
            S(weaponManager, "aircraft", aircraft);
            L($"hardpoint sets: {string.Join(" | ", sets.Select(x => $"{x.name} ({x.hardpoints.Count} hp, {x.weaponOptions.Count - 1} options{(x.precludingHardpointSets.Count > 0 ? ", excludes " + string.Join("/", x.precludingHardpointSets) : "")})"))}");
            return turrets.Where(t => t.gun != null).Select(t => t.gun).ToList();
        }
