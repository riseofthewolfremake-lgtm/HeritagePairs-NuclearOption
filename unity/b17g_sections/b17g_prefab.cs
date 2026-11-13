        static void BuildPrefab()
        {
            // the FBX root (B17G_root at the CG) is the prefab root; the centre fuselage mesh object is called B17G in the model
            var centre = root.GetComponentsInChildren<Transform>(true).FirstOrDefault(t => t != root.transform && t.name == "B17G");
            if (centre == null) throw new Exception("centre fuselage object B17G missing");
            centre.name = "fus_center";
            // 1. our meshes and materials on every renderer
            foreach (var mf in root.GetComponentsInChildren<MeshFilter>(true))
            {
                var mr = mf.GetComponent<MeshRenderer>();
                var names = mr.sharedMaterials.Select(m => m ? m.name.Replace(" (Instance)", "") : "null").ToArray();
                mf.sharedMesh = CopyMesh(mf.sharedMesh, mf.name, names, out var ordered);
                mr.sharedMaterials = ordered.Select(n => mats.TryGetValue(n, out var m) ? m : throw new Exception($"no material '{n}' for {mf.name}")).ToArray();
            }
            foreach (var t in root.GetComponentsInChildren<Transform>(true)) t.gameObject.layer = 14;

            // 2. root components first
            GameObjectUtility.RemoveMonoBehavioursWithMissingScript(root);
            root.AddComponent<Mirage.NetworkIdentity>();
            var rb = root.AddComponent<Rigidbody>();
            EditorUtility.CopySerialized(tpl["COIN"].GetComponent<Rigidbody>(), rb);
            CloneComp(tpl["COIN"].GetComponent<Aircraft>(), root);

            // 3. structure
            var specs = Parts();
            foreach (var s in specs) MakePartObject(s);
            foreach (var s in specs) MakeAeroPart(s);
            AddJoints(specs);

            // 4. systems on the cockpit part (as CI-22 cockpit_F)
            var cockpitGO = parts["fus_cockpit"].gameObject;
            controlsFilter = CloneComp(TplComp<ControlsFilter>("COIN:cockpit_F"), cockpitGO);
            weaponManager = CloneComp(TplComp<WeaponManager>("COIN:cockpit_F"), cockpitGO);
            CloneComp(TplComp<AutopilotPlane>("COIN:cockpit_F"), cockpitGO);
            Remap(aircraft); Remap(controlsFilter); Remap(weaponManager);

            ControlSurfaces();
            Flaps();
            var gears = Gear();
            Engines();
            Weapons();
            Cockpit(gears);
            RootSystems(gears);
            FlyByWire(gears[0]);

            int dropped = 0;
            foreach (var c in root.GetComponentsInChildren<Component>(true))
            {
                if (c == null) continue;
                var so = new SerializedObject(c); var it = so.GetIterator(); bool enter = true, changed = false;
                while (it.Next(enter))
                {
                    enter = true;
                    if (it.propertyType == SerializedPropertyType.ObjectReference && it.objectReferenceValue != null && IsTemplateObject(it.objectReferenceValue))
                    { L($"WARN dropped stale stock ref {c.GetType().Name}@{c.name}.{it.propertyPath} -> {it.objectReferenceValue.name}"); it.objectReferenceValue = null; dropped++; changed = true; }
                }
                if (changed) so.ApplyModifiedPropertiesWithoutUndo();
            }
            L($"final sweep dropped {dropped} stock refs");
            // 1.8.3: internals the stock way (StockStructure.cs): frames, ribs, spars, stringers, engine mounts / accessory sections drawn
            // with the stock aircraft_structure material (vertex colour 93 / engines 99), after the colliders are baked
            var ss = StockStructure.Apply(root, StockStructure.LookMaterial(Asset<Material>("Material/aircraft_structure_PLACEHOLDER.mat"), Folder, "B17G"),
                new Dictionary<Material, Color32> { { mats["structure"], StockStructure.StockGrey }, { mats["engine"], StockStructure.StockEngineGrey } }, 1f, generatedMeshes);
            L($"stock structure: {ss.renderers} renderers, {ss.triangles} tris, {ss.children} structure children");
        }

        // ------------------------------------------------------------------ parts
        static void MakePartObject(PartSpec s)
        {
            GameObject go;
            if (s.name == "B17G") go = root;
            else if (s.name.StartsWith("prop_")) go = Find(s.name).gameObject;        // model empty at the hub (prop_hub_n + blades under it)
            else if (s.lift == Lift.Hinge)
            {
                var mesh = Find(s.mesh);
                mesh.name = s.name + "_visible";
                Quaternion rot = s.name.StartsWith("rudder") ? Quaternion.LookRotation(Vector3.forward, Vector3.left) : mesh.rotation;
                go = NewGO(s.name, mesh.parent, mesh.position, rot);
                var hinge = NewGO(s.name + "_hinge", go.transform, mesh.position, rot);
                mesh.SetParent(hinge.transform, true);
                liftNormals[s.name] = hinge.transform;
            }
            else go = Find(s.mesh).gameObject;
            go.name = s.name;
            if (s.parent != null) go.transform.SetParent(partGO[s.parent].transform, true);
            parts[s.name] = null;
            partGO[s.name] = go;
        }
        static readonly Dictionary<string, GameObject> partGO = new Dictionary<string, GameObject>();

        static void MakeAeroPart(PartSpec s)
        {
            var go = partGO[s.name];
            var src = TplComp<AeroPart>(s.template);
            var ap = CloneComp(src, go);
            parts[s.name] = ap;
            S(ap, "parentUnit", aircraft);
            ap.mass = s.mass;
            S(ap, "criticalPart", false);
            S(ap, "wingArea", s.wingArea);
            ap.dragArea = s.dragArea * PartDragScale;
            S(ap, "airfoil", s.airfoil);
            S(ap, "disintegrateObjects", new GameObject[0]);
            S(ap, "centerOfMass", null);
            S(ap, "connectedAnchor", null);
            S(ap, "joints", new PartJoint[0]);
            if (CrashImpactDamage && !s.name.StartsWith("prop_"))
            {   // Nimrod 1.4.1 lesson: a new ImpactDamage per part (stock templates: threshold 0 = no crash damage except the fuselage)
                var idf = Fld(ap.GetType(), "impactDamage");
                var id = Activator.CreateInstance(idf.FieldType);
                bool fabric = s.name.StartsWith("aileron") || s.name.StartsWith("elevator") || s.name.StartsWith("rudder");
                S(id, "threshold", fabric ? FabricImpactG : MetalImpactG); S(id, "multiplier", fabric ? FabricImpactMult : MetalImpactMult);
                idf.SetValue(ap, id);
            }
            MeshFilter own = s.name == "B17G" ? Find("fus_center").GetComponent<MeshFilter>()
                : s.lift == Lift.Hinge ? Find(s.name + "_visible").GetComponent<MeshFilter>()
                : s.mesh != null ? go.GetComponent<MeshFilter>() : null;
            if (own != null)
            {
                var mc = go.AddComponent<MeshCollider>();
                mc.sharedMesh = BakeCollider(go.transform, s.name + "_col", own);
                mc.convex = true;
            }
            Transform ln = null;
            if (s.lift == Lift.Hinge) ln = liftNormals[s.name];
            else if (s.lift == Lift.Wing || s.lift == Lift.Stab || s.lift == Lift.Fin)
            {
                Vector3 x = Vector3.right;
                if (s.lift == Lift.Wing) x = SpanDir(s.name);
                Quaternion q;
                if (s.lift == Lift.Fin) q = Quaternion.LookRotation(Vector3.forward, Vector3.left);
                else
                {
                    var y = Vector3.Cross(Vector3.forward, x).normalized;
                    q = Quaternion.LookRotation(Vector3.forward, y);
                    float inc = s.lift == Lift.Wing ? WingIncidence : StabIncidence;
                    q = Quaternion.AngleAxis(-inc, q * Vector3.right) * q;
                }
                ln = NewGO(s.name + "_liftNormal", go.transform, go.transform.position, q).transform;
                liftNormals[s.name] = ln;
            }
            S(ap, "liftNormal", ln);
            Vector3 col = Vector3.zero;
            if (s.wingArea > 0.9f && own != null && ln != null)
            {
                var b = own.sharedMesh.bounds;
                var lePt = own.transform.TransformPoint(new Vector3(b.center.x, b.center.y, b.max.z));
                var tePt = own.transform.TransformPoint(new Vector3(b.center.x, b.center.y, b.min.z));
                var qc = Vector3.Lerp(lePt, tePt, 0.25f);
                var centroid = go.transform.TransformPoint(go.GetComponent<MeshCollider>().sharedMesh.bounds.center);
                col = ln.InverseTransformVector(qc - centroid);
                // 1.6.4: a flap's lift increment acts near the wing's mid-chord, not on the flap itself (1.6.3 in game: the flap lift
                // behind the main wheels pitched the take-off roll down to 2 deg, wing AoA 5.5, no lift-off below 72 m/s)
                if (s.name.StartsWith("flap_")) col += ln.InverseTransformVector(Vector3.forward * FlapLiftForward);
            }
            S(ap, "centerOfLift", col);
            L($"part {s.name}: mass {s.mass} wingArea {s.wingArea} drag {s.dragArea} airfoil {s.airfoil} lift {(ln ? ln.name : "own")} col {col.ToString("F2")}");
            var rends = PartRenderers(go).Where(r => r.sharedMaterials.Length > 0 && r.sharedMaterials[0] == mats["paint"]).Cast<Renderer>().ToList();
            var dm = G(ap, "damageMaterial");
            S(dm, "renderers", rends);
        }

        static IEnumerable<MeshRenderer> PartRenderers(GameObject partGo)
        {
            var result = new List<MeshRenderer>();
            void Walk(Transform t)
            {
                if (t != partGo.transform && t.GetComponent<AeroPart>() != null) return;
                if (t != partGo.transform && partGO.Values.Contains(t.gameObject)) return;
                var r = t.GetComponent<MeshRenderer>(); if (r) result.Add(r);
                foreach (Transform c in t) Walk(c);
            }
            Walk(partGo.transform);
            return result;
        }

        // span direction of a wing panel: 4 deg dihedral (blender/b17g/b17g_spec.py DIHEDRAL), +X on both sides like the stock wings
        static Vector3 SpanDir(string name)
        {
            float d = AeroDihedralDeg * Mathf.Deg2Rad;   // 1.7.4: aero dihedral 4 -> 8 deg (lift normals only; the model keeps its 4 deg)
            return name.EndsWith("_R") ? new Vector3(Mathf.Cos(d), Mathf.Sin(d), 0f) : new Vector3(Mathf.Cos(d), -Mathf.Sin(d), 0f);
        }

