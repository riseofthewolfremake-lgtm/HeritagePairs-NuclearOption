        static readonly string[] StationOrder = { "Chin", "Top", "Ball", "Tail", "Flexible" };
        static readonly Dictionary<string, int> TurretRounds = new Dictionary<string, int>
        {   // rounds per gun (one Gun cycle fires every muzzle of that Gun and costs 1 round)
            { "chin_mount", 365 }, { "top_mount", 375 }, { "ball_mount", 500 }, { "tail_mount", 500 },
            { "cheek_R_mount", 250 }, { "cheek_L_mount", 250 }, { "waist_R_mount", 300 }, { "waist_L_mount", 300 }, { "radio_mount", 250 },
        };
        static readonly Dictionary<string, WeaponInfo> stationInfos = new Dictionary<string, WeaponInfo>();
        static readonly List<(Turret turret, Gun gun, AeroPart part, Transform mount, string station)> turrets = new List<(Turret, Gun, AeroPart, Transform, string)>();
        static WeaponInfo turretInfo; static WeaponMount ammoTurrets;
        static int exclusionConeCount;
        const string TurretScan = @"C:\Users\User\Nuclear Option B-25\assets\model_b17g\b17g_turret_scan.json";

        static AeroPart OwningPart(Transform t) { for (var x = t; x != null; x = x.parent) { var ap = x.GetComponent<AeroPart>(); if (ap != null) return ap; } return null; }
        static Vector3 barrelTip; static string barrelTipSource = "";
        // 1.8.0 (user: "none of the guns actually line up with where they are meant to be"): the stock barrel asset is NOT readable
        // (m_IsReadable 0), so BarrelTip fell back to the BOUNDS centre (-0.078, 0.065) instead of the bore (0.000, 0.042): every one of
        // the 13 barrels sat 8 cm to its right and 2 cm high of its slot / muzzle line. The vertices are now read from the asset's own
        // serialized vertex data (m_VertexData, float32 position stream) when the mesh API refuses; the bounds stay the last fallback.
        static Vector3[] AssetVertices(Mesh m)
        {
            try { if (m.isReadable) { barrelTipSource = "mesh API"; return m.vertices; } } catch { }
            try
            {
                var path = AssetDatabase.GetAssetPath(m);
                if (string.IsNullOrEmpty(path) || !path.EndsWith(".asset")) return new Vector3[0];
                var y = File.ReadAllText(path);
                int vc = int.Parse(System.Text.RegularExpressions.Regex.Match(y, @"m_VertexCount: (\d+)").Groups[1].Value);
                var chs = System.Text.RegularExpressions.Regex.Matches(System.Text.RegularExpressions.Regex.Match(y, @"m_Channels:(.*?)m_DataSize", System.Text.RegularExpressions.RegexOptions.Singleline).Groups[1].Value,
                    @"stream: (\d+)\s+offset: (\d+)\s+format: (\d+)\s+dimension: (\d+)");
                var hex = System.Text.RegularExpressions.Regex.Match(y, @"_typelessdata: ([0-9a-f]+)").Groups[1].Value;
                if (chs.Count == 0 || hex.Length == 0) return new Vector3[0];
                var pc = chs[0];                                    // channel 0 = position
                if (pc.Groups[1].Value != "0" || pc.Groups[3].Value != "0" || (int.Parse(pc.Groups[4].Value) & 0xf) != 3) return new Vector3[0];
                var data = new byte[hex.Length / 2];
                for (int i = 0; i < data.Length; i++) data[i] = Convert.ToByte(hex.Substring(2 * i, 2), 16);
                int stride0 = data.Length / vc;                    // single-stream layout (stock meshes): bytes per vertex
                var v = new Vector3[vc];
                for (int i = 0; i < vc; i++) { int o = i * stride0 + int.Parse(pc.Groups[2].Value); v[i] = new Vector3(BitConverter.ToSingle(data, o), BitConverter.ToSingle(data, o + 4), BitConverter.ToSingle(data, o + 8)); }
                barrelTipSource = "serialized vertex data";
                return v;
            }
            catch (Exception e) { L("WARN barrel vertices: " + e.Message); return new Vector3[0]; }
        }
        static Vector3 BarrelTip(Mesh m)
        {   // bore axis at the tip: centroid of the vertices within 3 cm of the mesh's max z (falls back to the bounds)
            var v = AssetVertices(m);
            if (v.Length == 0) { barrelTipSource = "bounds (fallback)"; var b = m.bounds; return new Vector3(b.center.x, b.center.y, b.max.z); }
            float zmax = v.Max(p => p.z); var tp = v.Where(p => p.z > zmax - 0.03f).ToList();
            return new Vector3(tp.Average(p => p.x), tp.Average(p => p.y), zmax);
        }

        static void BuildTurrets()
        {
            turrets.Clear(); stationInfos.Clear(); exclusionConeCount = 0;
            var doorTpl = tpl["turret_12.7mm_door"];
            var tplTurret = doorTpl.GetComponentInChildren<Turret>(true);
            var tplGun = doorTpl.GetComponentInChildren<Gun>(true);
            var barrelMesh = Asset<Mesh>("Mesh/50cal_doorGun_barrel_PLACEHOLDER.asset");
            var barrelMat = Asset<Material>("Material/utilityHelo1_attachments_PLACEHOLDER.mat");
            var scan = File.Exists(TurretScan) ? Newtonsoft.Json.Linq.JObject.Parse(File.ReadAllText(TurretScan)) : null;
            // 1.6.1: the stock door-gun barrel mesh is NOT centred on its origin (in game mbounds x -0.08..0.52, y 0.06..0.37, z 0.43..1.54):
            // its bore axis is offset ~0.22 m right and up, so on our slot the guns sat beside the turret and the muzzles (slot +1.20 m)
            // were 0.3 m off the bore and 0.34 m short of the tip. The barrel goes on a child shifted so the bore lies on the slot axis, and
            // the muzzle moves to the bore tip (Gun.cs 634: rounds leave every muzzle along muzzle.forward).
            // 1.8.13 (offline L): our own AN/M2 (ANM2Gun.cs, blender/anm2/anm2_model.py) instead of the stock door-gun barrel: bore through the
            // contract muzzle, tip on it, gun_L / gun_R per side, spade grips on the hand-held positions. ANM2Guns false = the stock barrel.
            var anm2 = ANM2Guns ? ANM2Gun.Load(Folder, "B17G") : null;
            if (anm2 != null) L($"AN/M2: tip z {anm2.TipZ}, meshes {anm2.FL.name} / {anm2.FR.name} / {anm2.TL.name} / {anm2.TR.name} / {anm2.Grips.name}");
            barrelTip = BarrelTip(barrelMesh);
            L($"stock barrel bore at the tip: ({barrelTip.x:F3}, {barrelTip.y:F3}, {barrelTip.z:F3}) from {barrelTipSource}; bounds centre ({barrelMesh.bounds.center.x:F3}, {barrelMesh.bounds.center.y:F3})");
            foreach (var st in StationOrder)
            {
                var info = Object.Instantiate(Asset<WeaponInfo>("MonoBehaviour/Gun12.7mm_PLACEHOLDER.asset")); info.name = "B17G_turret_" + st.ToLowerInvariant() + "_info";
                info.weaponName = $"12.7mm {st} Guns"; info.shortName = $"{st.ToUpperInvariant()} 12.7MM"; info.boresight = false;
                if (TurretAntiMissile) info.effectiveness.antiMissile = 0.05f;
                // 1.6.1 AIR TARGETS ONLY (in game 1.6.0: 830+ hits on helipads / revetments, the tail turret ignored a CI-22 astern):
                // Turret.AssessTargetPriority (Turret.cs 484-486) skips a candidate whose opportunity is 0; WeaponStation.CalcOpportunityThreat
                // (WeaponStation.cs 435) = target type . WeaponInfo.effectiveness x target type . aircraft roleIdentity (RoleIdentity.cs 19-22).
                // Stock Gun12.7mm (0.12 surface / 0.12 air) x B17G role (0.9 / 0.1) made ground targets 9x more attractive than fighters.
                info.effectiveness.antiSurface = 0f; info.effectiveness.antiRadar = 0f;
                AssetDatabase.CreateAsset(info, Folder + "/" + info.name + ".asset");
                stationInfos[st] = info;
            }
            foreach (var tj in JList("turrets"))
            {
                var mount = TryFind((string)tj["mount"]["name"]); var az = TryFind((string)tj["az"]["name"]); var el = TryFind((string)tj["el"]["name"]);
                if (mount == null || az == null || el == null) { L($"WARN turret {(string)tj["mount"]["name"]}: objects missing, skipped"); continue; }
                var station = (string)tj["station"];
                var part = OwningPart(mount);
                if (Quaternion.Angle(az.localRotation, Quaternion.identity) > 0.01f || Quaternion.Angle(el.localRotation, Quaternion.identity) > 0.01f)
                    L($"WARN turret {mount.name}: az/el do not rest at identity");
                var muzzles = new List<Transform>();
                bool twin = ((Newtonsoft.Json.Linq.JArray)tj["guns"]).Count > 1;
                foreach (var g in (Newtonsoft.Json.Linq.JArray)tj["guns"])
                {
                    var gb = TryFind((string)g["gun"]["name"]); var mz = TryFind((string)g["muzzle"]["name"]);
                    if (gb == null || mz == null) continue;
                    if (anm2 != null)
                    {   // trunnion 0.10 m ahead of the elevation pivot on the contract bore line (receiver / grips inside, as the real mounts), muzzle moved to the tip
                        mz.localRotation = Quaternion.identity;
                        var (right, grips) = ANM2Gun.Variant(mount.name.Replace("_mount", ""), gb, el, twin);
                        var gt = ANM2Gun.Place(anm2, gb, mz, el, right, grips);
                        L($"AN/M2 {gb.name}: {(right ? "gun_R" : "gun_L")}{(grips ? " + grips" : "")}, gun at slot z {gt.localPosition.z:F3}, muzzle z {mz.localPosition.z:F3}");
                        muzzles.Add(mz);
                        continue;
                    }
                    var old = gb.GetComponent<MeshFilter>(); if (old != null) { var orr = gb.GetComponent<MeshRenderer>(); if (orr != null) Object.DestroyImmediate(orr); Object.DestroyImmediate(old); }
                    var bgo = NewGO(gb.name + "_barrel", gb, gb.TransformPoint(new Vector3(-barrelTip.x, -barrelTip.y, 0f)), gb.rotation);
                    bgo.AddComponent<MeshFilter>().sharedMesh = barrelMesh; bgo.AddComponent<MeshRenderer>().sharedMaterials = new[] { barrelMat };   // the stock M2 barrel, bore on the slot axis
                    mz.localPosition = new Vector3(0f, 0f, barrelTip.z); mz.localRotation = Quaternion.identity;
                    muzzles.Add(mz);
                }
                var tl = tj["Turret"];
                int rounds = TurretRounds.TryGetValue(mount.name, out var rr) ? rr : 300;
                foreach (var a in tplGun.GetComponents<AudioSource>()) CloneComp(a, el.gameObject).loop = false;
                var gun = CloneComp(tplGun, el.gameObject);
                gun.attachedUnit = aircraft; gun.info = stationInfos[station];
                S(gun, "muzzles", muzzles.ToArray());
                S(gun, "magazineCapacity", rounds); S(gun, "magazines", 0); S(gun, "startLoaded", true);
                S(gun, "recoilTransform", null); S(gun, "spinTransform", null); S(gun, "ejectionTransform", null); S(gun, "ejectionPrefab", null);
                var ps = new List<ParticleSystem>(); foreach (var mz in muzzles) ps.AddRange(CopyMuzzleParticles(tplGun, mz));
                S(gun, "muzzleParticles", ps.ToArray());
                var tr = CloneComp(tplTurret, az.gameObject);
                S(tr, "attachedUnit", aircraft);
                var fMode = Fld(typeof(Turret), "targetAcquisitionMode"); fMode.SetValue(tr, Enum.ToObject(fMode.FieldType, 0));
                S(tr, "fireControl", null); S(tr, "firesWithoutAiming", false);
                SetSeq(tr, "targetDetectors", new TargetDetector[0]);
                var ws = (WeaponStation)System.Runtime.Serialization.FormatterServices.GetUninitializedObject(typeof(WeaponStation));
                ws.Weapons = new List<Weapon> { gun }; ws.Turrets = new List<Turret> { tr };
                SetSeq(tr, "weaponStations", new[] { ws });
                S(tr, "aimSafetyWeapon", gun);
                float trav = (float)tl["traverseRange"], emin = (float)tl["minElevation"], emax = (float)tl["maxElevation"];
                S(tr, "traverseRate", (float)tl["traverseRate"]); S(tr, "traverseRange", trav >= 180f ? 999999f : trav);
                S(tr, "elevationRate", (float)tl["elevationRate"]); S(tr, "minElevation", emin); S(tr, "maxElevation", emax);
                S(tr, "elevationTransform", el);
                // inclusion cone (B-25H) + exclusion cones from the offline scan (blocked 5-deg grid directions, 6 deg each)
                Vector3 fwd = mount.forward, up = mount.up; float cone;
                if (trav >= 180f) { fwd = emax <= 0f ? -up : up; cone = 90f + Mathf.Max(Mathf.Abs(emin), Mathf.Abs(emax)) * 0f + 1f + (emax <= 0f ? emax : -emin); }
                else cone = Mathf.Rad2Deg * Mathf.Acos(Mathf.Cos(trav * Mathf.Deg2Rad) * Mathf.Cos(Mathf.Max(Mathf.Abs(emin), Mathf.Abs(emax)) * Mathf.Deg2Rad)) + 1f;
                var cones = new List<object>();
                var cg = NewGO(mount.name + "_cone", mount.parent, mount.position, Quaternion.LookRotation(fwd, Mathf.Abs(Vector3.Dot(fwd, Vector3.up)) > 0.99f ? Vector3.forward : Vector3.up));
                var fc = New(typeof(FiringCone)); S(fc, "transform", cg.transform); S(fc, "coneAngle", cone); S(fc, "exclusion", false); cones.Add(fc);
                var tname = mount.name.Replace("_mount", "");
                if (TurretExclusionCones && scan != null && scan[tname] != null)
                    foreach (var c in (Newtonsoft.Json.Linq.JArray)scan[tname]["exclusion_cones"])
                    {
                        var d = new Vector3((float)c[0][0], (float)c[0][2], (float)c[0][1]);      // Blender world dir -> Unity
                        var eg = NewGO($"{mount.name}_excl{cones.Count}", mount.parent, mount.position, Quaternion.LookRotation(d, Mathf.Abs(d.y) > 0.99f ? Vector3.forward : Vector3.up));
                        var ec = New(typeof(FiringCone)); S(ec, "transform", eg.transform); S(ec, "coneAngle", (float)c[1]); S(ec, "exclusion", true); cones.Add(ec);
                        exclusionConeCount++;
                    }
                SetSeq(tr, "firingCones", cones);
                S(tr, "criticalParts", new UnitPart[] { part });
                S(tr, "manual", false); S(tr, "stowed", false);
                turrets.Add((tr, gun, part, mount, station));
                L($"turret {tname} ({station}): part {part.name}, traverse {trav}, el {emin}..{emax}, {muzzles.Count} gun(s) x {rounds} rds, inclusion cone {cone:F0} deg, {cones.Count - 1} exclusion cones");
            }
        }

