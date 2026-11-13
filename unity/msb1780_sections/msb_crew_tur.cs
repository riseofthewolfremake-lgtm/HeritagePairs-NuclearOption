        static Pilot MakeCrewMember(CrewSpec c, int index)
        {   // GA-25X 0.3.1 kitbash: the stock figure keeps its stock EjectionSeat child (mesh ejectionSeat, material Seats): the seat in the
            // aircraft IS the seat that fires (Pilot.ejectionSeat true; Aircraft.EjectionSequence jettisons the Canopy hatches first)
            var src = index == 0 ? TplFind("COIN:pilot") : TplFind("COIN:WSO");
            var fig = (GameObject)Object.Instantiate(src.gameObject);
            fig.SetActive(true); fig.name = index == 0 ? "pilot" : "crew_" + c.role;
            foreach (var t in fig.GetComponentsInChildren<Transform>(true).Where(t => t.name == "EjectionSeat").ToList())
            {
                if (!EjectionSeats190) { Object.DestroyImmediate(t.gameObject); continue; }
                var mf = t.GetComponent<MeshFilter>(); var mr = t.GetComponent<MeshRenderer>();
                if (mf != null) mf.sharedMesh = Asset<Mesh>("Mesh/ejectionSeat_PLACEHOLDER.asset");
                if (mr != null) mr.sharedMaterials = new[] { Asset<Material>("Material/Seats_PLACEHOLDER.mat") };
                var sc = t.GetComponent<MeshCollider>();
                if (sc != null) sc.sharedMesh = Asset<Mesh>("Mesh/ejectionSeat_PLACEHOLDER.asset");
            }
            var part = parts[c.part];
            fig.transform.SetParent(c.eye.parent, false);
            var cam = fig.GetComponentsInChildren<Transform>(true).First(t => t.name == "helmetCamPoint");
            fig.transform.rotation = Quaternion.LookRotation(Vector3.ProjectOnPlane(c.eye.forward, Vector3.up).sqrMagnitude > 1e-4f ? Vector3.ProjectOnPlane(c.eye.forward, Vector3.up) : Vector3.forward, Vector3.up);
            fig.transform.position += c.eye.position - cam.position;
            foreach (var comp in fig.GetComponentsInChildren<Component>(true)) if (comp != null) Remap(comp);
            var pc = fig.GetComponent<Pilot>();
            S(pc, "aircraft", aircraft); S(pc, "unitPart", part); S(pc, "ejectionSeat", EjectionSeats190); S(pc, "autoTrimmer", controlsFilter);
            S(pc, "pilotCollider", fig.GetComponent<CapsuleCollider>());
            pc.exitDirection = c.exit;
            L($"crew {index} {c.role}: part {c.part}, eye {c.eye.position.ToString("F3")}, figure eye {cam.position.ToString("F3")}, exit {c.exit}, hatch {c.hatch}, ejection seat {EjectionSeats190}");
            if (index == 0) helmetCam = cam;
            return pc;
        }

        // ------------------------------------------------------------------ defensive stations
        static readonly string[] StationOrder = { "Chin", "Tail", "Dorsal", "Ventral" };
        static readonly Dictionary<string, string> StationLabel = new Dictionary<string, string> { { "Chin", "Chin 20mm" }, { "Tail", "Tail 20mm" }, { "Dorsal", "Dorsal Laser" }, { "Ventral", "Ventral Laser" } };
        static readonly Dictionary<string, WeaponInfo> stationInfos = new Dictionary<string, WeaponInfo>();
        class MsbTurret { public Turret turret; public Gun gun; public AeroPart part; public Transform mount; public string station; public bool laser; public GameObject laserGO; public Laser laserComp; }
        static readonly List<MsbTurret> turrets = new List<MsbTurret>();
        static WeaponInfo turretInfo; static WeaponMount ammoTurrets;
        static int exclusionConeCount;
        static AeroPart OwningPart(Transform t) { for (var x = t; x != null; x = x.parent) { var ap = x.GetComponent<AeroPart>(); if (ap != null) return ap; } return null; }

        // 20 mm: own WeaponInfo per station (stations are keyed by WeaponInfo, WeaponManager.cs 403-438: one per station so the chin and the
        // tail fire independently, the B-17G lesson); values in the stock 20 mm class (msb_head.cs Gun20*). Gun component = the stock
        // turret_20mm_rotary Gun (sounds, tracer, heat), two muzzles on our twin barrel tips, magazineCapacity = cycles (one cycle = both).
        // Lasers: the GA-25X pattern - the Laser lives in a mount prefab spawned on the aperture hardpoint (Hardpoint.SpawnMount casts every
        // BuiltInWeapon to Gun), the station starts with a proxy base Weapon carrying the laser info; HLT (LaserTrailer1) turret values, its
        // own TargetDetector (15 km), onlyDefensive (missiles aimed at us only).
        static void BuildTurrets()
        {
            turrets.Clear(); stationInfos.Clear(); exclusionConeCount = 0;
            var tGunPrefab = tpl["turret_20mm_rotary"];
            var tplGun = tGunPrefab.GetComponentInChildren<Gun>(true);
            var tplTurret20 = tGunPrefab.GetComponentInChildren<Turret>(true);
            var tLaser = tpl["Laser_EW1"].GetComponent<Laser>();
            var tTurL = tpl["LaserTrailer1"].GetComponentInChildren<Turret>(true);
            foreach (var tj in JList("turrets"))
            {
                var mount = TryFind((string)tj["mount"]["name"]); var az = TryFind((string)tj["az"]["name"]); var el = TryFind((string)tj["el"]["name"]);
                if (mount == null || az == null || el == null) { L($"WARN turret {(string)tj["mount"]["name"]}: objects missing, skipped"); continue; }
                var station = (string)tj["station"]; bool laser = (string)tj["weapon"] == "laser";
                if (laser && !LaserTurrets190) { L($"turret {mount.name}: laser off (LaserTurrets190)"); continue; }
                var part = OwningPart(mount);
                var tl = tj["Turret"];
                float trav = (float)tl["traverseRange"], emin = (float)tl["minElevation"], emax = (float)tl["maxElevation"];
                var rec = new MsbTurret { part = part, mount = mount, station = station, laser = laser };
                Turret tr;
                if (!laser)
                {
                    var info = Object.Instantiate(Asset<WeaponInfo>("MonoBehaviour/Gun20mm_Rotary_Turret_PLACEHOLDER.asset")); info.name = "MSB17_" + station.ToLowerInvariant() + "_20mm_info";
                    if (Gun20Custom190)
                    {
                        info.weaponName = $"DTC-20 Twin 20mm ({station})"; info.shortName = $"{station.ToUpperInvariant()} 20MM";
                        info.description = "DTC-20 automated twin 20 mm defence cannon: radar / EO-cued remote turret, two barrels on one cradle, 600 rounds per barrel. Engages aircraft (and missiles at short range) in its own sector.";
                        info.muzzleVelocity = Gun20Velocity; info.pierceDamage = Gun20Pierce; info.blastDamage = Gun20Blast; info.dragCoef = Gun20Drag;
                        info.massPerRound = Gun20MassPerRound; info.targetRequirements.maxRange = Gun20Range;
                    }
                    info.boresight = false;
                    info.effectiveness.antiSurface = 0f; info.effectiveness.antiRadar = 0f;      // B-17G 1.6.1 lesson: air targets only (no ground fire, no ground-target pull)
                    info.effectiveness.antiAir = 0.25f; info.effectiveness.antiMissile = TurretAntiMissile ? 0.1f : 0f;
                    AssetDatabase.CreateAsset(info, Folder + "/" + info.name + ".asset");
                    stationInfos[station] = info;
                    var muzzles = ((Newtonsoft.Json.Linq.JArray)tj["guns"]).Select(g => TryFind((string)g["muzzle"]["name"])).Where(m => m != null).ToList();
                    foreach (var a in tplGun.GetComponents<AudioSource>()) CloneComp(a, el.gameObject).loop = false;
                    var gun = CloneComp(tplGun, el.gameObject);
                    gun.attachedUnit = aircraft; gun.info = info;
                    S(gun, "muzzles", muzzles.ToArray());
                    S(gun, "magazineCapacity", Gun20Cycles); S(gun, "magazines", 0); S(gun, "startLoaded", true);
                    S(gun, "fireRate", Gun20Custom190 ? Gun20CyclesPerMin : (float)G(tplGun, "fireRate"));
                    S(gun, "recoilTransform", null); S(gun, "spinTransform", null); S(gun, "ejectionTransform", null); S(gun, "ejectionPrefab", null);
                    var ps = new List<ParticleSystem>(); foreach (var mz in muzzles) ps.AddRange(CopyMuzzleParticles(tplGun, mz));
                    S(gun, "muzzleParticles", ps.ToArray());
                    tr = CloneComp(tplTurret20 != null ? tplTurret20 : tTurL, az.gameObject);
                    S(tr, "attachedUnit", aircraft);
                    var fMode = Fld(typeof(Turret), "targetAcquisitionMode"); fMode.SetValue(tr, Enum.ToObject(fMode.FieldType, 0));
                    S(tr, "fireControl", null); S(tr, "firesWithoutAiming", false);
                    SetSeq(tr, "targetDetectors", new TargetDetector[0]);
                    var ws = (WeaponStation)System.Runtime.Serialization.FormatterServices.GetUninitializedObject(typeof(WeaponStation));
                    ws.Weapons = new List<Weapon> { gun }; ws.Turrets = new List<Turret> { tr };
                    SetSeq(tr, "weaponStations", new[] { ws });
                    S(tr, "aimSafetyWeapon", gun);
                    rec.gun = gun;
                    L($"turret {mount.name} ({station}): DTC-20 v0 {info.muzzleVelocity} pierce {info.pierceDamage} {G(gun, "fireRate")} cycles/min x {muzzles.Count} barrels, {Gun20Cycles} cycles = {Gun20Cycles * muzzles.Count} rds");
                }
                else
                {
                    var info = Object.Instantiate(tLaser.info); info.name = "MSB17_" + station.ToLowerInvariant() + "_laser_info";
                    info.weaponName = $"120kW Laser ({station})"; info.shortName = $"{station.ToUpperInvariant()} LASER";
                    AssetDatabase.CreateAsset(info, Folder + "/" + info.name + ".asset");
                    stationInfos[station] = info;
                    var ap = TryFind((string)tj["aperture"]["name"]);
                    var lgo = new GameObject("MSB17_" + station.ToLowerInvariant() + "_laser_mount") { layer = 14 };
                    var lroot = lgo.transform;
                    var lz = CloneComp(tLaser, lgo);
                    lz.attachedUnit = null; lz.info = info;
                    if (LaserBeam197) S(lz, "maxAngle", LaserBeamAngle197);   // 1.9.7: beam = bore line (stock 30)
                    var tBeam = TplFind("Laser_EW1:beam");
                    var beam = NewGO("laser_beam", lroot, lroot.position, lroot.rotation);
                    beam.transform.localScale = tBeam.localScale;
                    beam.AddComponent<MeshFilter>().sharedMesh = tBeam.GetComponent<MeshFilter>().sharedMesh;
                    var br = beam.AddComponent<MeshRenderer>(); br.sharedMaterials = tBeam.GetComponent<MeshRenderer>().sharedMaterials; br.enabled = false;
                    br.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                    S(lz, "beamRenderer", br); S(lz, "directionTransform", lroot);
                    var aimPS = TplFind("Laser_EW1:aimTransform").GetComponent<ParticleSystem>();
                    var lmps = aimPS != null ? new[] { CopyParticle(aimPS, lroot, lroot.position, "laser_muzzle") } : new ParticleSystem[0];
                    S(lz, "muzzleParticles", lmps);
                    foreach (var p in lmps) ourParticles.Remove(p);
                    if (lmps.Length > 0) S(lgo.AddComponent<SetGlobalParticles>(), "systems", lmps.ToList());
                    S(lz, "vehicularPowerSupply", false);
                    tr = CloneComp(tTurL, az.gameObject);
                    S(tr, "attachedUnit", aircraft);
                    var fMode = Fld(typeof(Turret), "targetAcquisitionMode"); fMode.SetValue(tr, Enum.ToObject(fMode.FieldType, 1));
                    var det = CloneComp(tTurL.GetComponent<TargetDetector>(), az.gameObject);
                    S(det, "attachedUnit", aircraft); S(det, "scanner", el); S(det, "part", part); S(det, "visualRange", 15000f);
                    SetSeq(tr, "targetDetectors", new[] { det });
                    S(tr, "fireControl", null); S(tr, "firesWithoutAiming", false);
                    var proxy = el.gameObject.AddComponent<Weapon>(); proxy.attachedUnit = aircraft; proxy.info = info; proxy.Rearmable = false;
                    var ws = (WeaponStation)System.Runtime.Serialization.FormatterServices.GetUninitializedObject(typeof(WeaponStation));
                    ws.Weapons = new List<Weapon> { proxy }; ws.Turrets = new List<Turret> { tr }; ws.WeaponInfo = info;
                    SetSeq(tr, "weaponStations", new[] { ws });
                    S(tr, "aimSafetyWeapon", null);
                    S(tr, "onlyDefensive", true);
                    rec.laserGO = lgo; rec.laserComp = lz;
                    L($"turret {mount.name} ({station}): 120 kW laser (power {G(lz, "power")} kW, maxAngle {G(lz, "maxAngle")}), aperture {(ap != null ? ap.position.ToString("F3") : "MISSING")}, own detector 15 km, onlyDefensive");
                }
                // 1.9.2: Turret.AimTurret elevates only while |traverse error| < 45 deg (Turret.cs 746): at 60 deg/s the dorsal head never left 0 before the missile arrived
                S(tr, "traverseRate", laser && LaserSlew192 ? Mathf.Max((float)tl["traverseRate"], LaserTraverseRate) : (float)tl["traverseRate"]); S(tr, "traverseRange", trav >= 180f ? 999999f : trav);
                S(tr, "elevationRate", (float)tl["elevationRate"]); S(tr, "minElevation", emin); S(tr, "maxElevation", emax);
                S(tr, "elevationTransform", el);
                // inclusion cone: full-traverse turrets about the mount's up (dorsal) / down (ventral) as the GA-25X laser; sector turrets as the B-17G
                Vector3 fwd = mount.forward; float cone;
                if (trav >= 180f) { bool ventral = emax <= 0f; fwd = ventral ? -mount.up : mount.up; cone = ventral ? 90f + emax + 1f : 90f - emin + 1f; }
                else cone = Mathf.Rad2Deg * Mathf.Acos(Mathf.Cos(trav * Mathf.Deg2Rad) * Mathf.Cos(Mathf.Max(Mathf.Abs(emin), Mathf.Abs(emax)) * Mathf.Deg2Rad)) + 1f;
                var cg = NewGO(mount.name + "_cone", mount.parent, mount.position, Quaternion.LookRotation(fwd, Mathf.Abs(Vector3.Dot(fwd, Vector3.up)) > 0.99f ? Vector3.forward : Vector3.up));
                var fc = New(typeof(FiringCone)); S(fc, "transform", cg.transform); S(fc, "coneAngle", cone); S(fc, "exclusion", false);
                SetSeq(tr, "firingCones", new List<object> { fc });
                S(tr, "criticalParts", new UnitPart[] { part });
                S(tr, "manual", false); S(tr, "stowed", false);
                rec.turret = tr;
                turrets.Add(rec);
                L($"turret {mount.name}: part {part.name}, traverse {trav}, el {emin}..{emax}, inclusion cone {cone:F0} deg");
            }
        }

