        static void Cockpit(List<LandingGear> gears)
        {
            var cp = parts["fus_cockpit"];
            var eye = Find("cockpit_eye");

            // ---- crew of four (contract stations): pilot, co-pilot, WSO (nose), EWO (behind the co-pilot); stock ejection seats
            crew.Clear();
            int ci = 0;
            foreach (var st in JList("crew", "stations"))
            {
                var e = TryFind((string)st["eye"]["name"]);
                if (e == null) { L($"WARN crew {(string)st["role"]}: eye {(string)st["eye"]["name"]} not in the model, skipped"); continue; }
                var exit = e.position.x > 0.05f ? Pilot.ExitDirection.Right : Pilot.ExitDirection.Left;
                crew.Add(MakeCrewMember(new CrewSpec { role = (string)st["role"], part = (string)st["part"], eye = e, exit = exit, hatch = (string)st["exit_hatch"] }, ci));
                ci++;
            }
            if (crew.Count == 0) crew.Add(MakeCrewMember(new CrewSpec { role = "pilot", part = "fus_cockpit", eye = eye, exit = Pilot.ExitDirection.Left, hatch = null }, 0));
            L($"pilot eye {helmetCam.position.ToString("F3")} vs cockpit_eye {eye.position.ToString("F3")}");

            // ---- escape hatches (stock Canopy, jettisoned before the seats fire)
            var canopies = new List<Canopy>();
            foreach (var h in JList("hatches", "hatches"))
            {
                var hatch = TryFind((string)h["hatch"]["name"]); var hinge = TryFind((string)h["hinge"]["name"]);
                var pp = (string)h["parent_part"];
                if (hatch == null || hinge == null || !parts.ContainsKey(pp)) { L($"WARN hatch {(string)h["hatch"]["name"]} missing, skipped"); continue; }
                var glass = hatch.GetComponent<MeshRenderer>() != null && hatch.GetComponent<MeshRenderer>().sharedMaterials.Contains(mats["glass"]) ? new Renderer[] { hatch.GetComponent<MeshRenderer>() } : new Renderer[0];
                canopies.Add(MakeHatchFromContract(hatch, hinge, (float)h["hingeAngle"], parts[pp], glass));
            }
            S(aircraft, "canopies", canopies.ToArray());

            // ---- 1.9.1 kitbash (memory kitbash-stock-parts; coordinator: the 1.9.0 flat panel was not acceptable): the stock EW-25 two-pilot
            // glass cockpit - its tub (panel with MFD glass, glare shield, pedestal, side consoles, floor), wide tac screen, sticks and throttle -
            // on the contract's stock_parts anchors (blender/msb1780/msb_stations.py: EW-25 helmet point -> our pilot eye; identity frames as the
            // EW-25 nodes). Meshes + the template's own materials (placeholders, swapped for the game's at load). Drivers as on the EW-25.
            // 1.9.5 (user order "Rebuild a custom cockpit using stock parts"; memory kitbash-stock-parts): OUR flight deck (blender/msb1780/msb_deck195.py)
            // with single stock parts on its anchors - sfb_joystick x2, sfb_throttle (the SFB-81's one centre quadrant), EW1_warningLights x2 (missile-
            // warning lamps, stock CockpitWarningLights) - meshes and materials from the user's install (placeholders, swapped for the game's at load).
            var warnLamps = new List<Renderer>();
            foreach (var sp in JList("stock_parts"))
            {
                string n = (string)sp["name"], mesh = (string)sp["mesh"], tplN = (string)sp["template"];
                var t = TryFind(n); if (t == null) { L($"WARN stock anchor {n} missing"); continue; }
                var m = Asset<Mesh>("Mesh/" + mesh + "_PLACEHOLDER.asset");
                var mf = t.GetComponent<MeshFilter>(); if (mf == null) mf = t.gameObject.AddComponent<MeshFilter>(); mf.sharedMesh = m;
                var mr = t.GetComponent<MeshRenderer>(); if (mr == null) mr = t.gameObject.AddComponent<MeshRenderer>();
                if (tplN != null) mr.sharedMaterials = TplFind(tplN).GetComponent<MeshRenderer>().sharedMaterials.ToArray();
                else mr.sharedMaterials = ((Newtonsoft.Json.Linq.JArray)sp["materials"]).Select(x => Asset<Material>("Material/" + (string)x + "_PLACEHOLDER.mat")).ToArray();
                mr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                if (sp["layer"] != null && sp["layer"].Type == Newtonsoft.Json.Linq.JTokenType.Integer) t.gameObject.layer = (int)sp["layer"];   // the lamps: CockpitAndExternal (14), as the stock lamps
                if ((string)sp["role"] == "missile_warning_lamp") warnLamps.Add(mr);
                L($"stock part {n}: {mesh} [{string.Join(", ", mr.sharedMaterials.Select(x => x != null ? x.name : "null"))}] {(tplN != null ? "from " + tplN : "(contract materials)")} at {t.position.ToString("F3")} in {t.parent.name}, layer {t.gameObject.layer}");
            }
            if (WarnLamps195 && warnLamps.Count > 0)
            {   // the stock missile-warning blinker (CockpitWarningLights.cs: renderers off at init, blink at 10 Hz while a missile is known, local aircraft
                // only); the lamps are in neither cockpitRenderers nor exteriorRenderers (the stock SFB-81 / EW-25 pattern), so only it switches them
                var cwl = CloneComp(TplComp<global::CockpitWarningLights>("EW1:cockpit_F_int"), Find("cockpit_interior").gameObject);
                S(cwl, "lightRenderers", warnLamps.ToArray()); S(cwl, "aircraft", aircraft);
                L($"CockpitWarningLights on cockpit_interior: {warnLamps.Count} lamps ({string.Join(", ", warnLamps.Select(r => r.name))})");
            }

            // ---- cockpit-only copies on the Cockpit layer (3); exterior originals hidden in cockpit view (stock pattern)
            var cockpitR = new List<Renderer>(); var exteriorR = new List<Renderer>();
            var copyNames = new List<string> { "fus_cockpit", "stick_L", "stick_R", "cockpit_throttle", "hatch_pilot_L", "hatch_pilot_R" };   // + every cockpit_* (EW-25 tub / tac screen, stations)
            copyNames.AddRange(root.GetComponentsInChildren<MeshFilter>(true).Where(m => m.name.StartsWith("cockpit_")).Select(m => m.name));
            foreach (var n in copyNames.Distinct())
            {
                var orig = TryFind(n);
                if (orig == null || orig.GetComponent<MeshRenderer>() == null) continue;
                var src = orig.GetComponent<MeshRenderer>();
                if (src.sharedMaterials.All(m => m == mats["glass"])) continue;
                var copy = NewGO(n + "_int", orig, orig.position, orig.rotation, 3);
                copy.AddComponent<MeshFilter>().sharedMesh = orig.GetComponent<MeshFilter>().sharedMesh;
                var cr = copy.AddComponent<MeshRenderer>();
                cr.sharedMaterials = src.sharedMaterials.Select(m => m == mats["glass"] ? mats["glass_int"] : m).ToArray();
                cr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                cr.enabled = false;
                cockpitR.Add(cr); exteriorR.Add(src);
                if (CockpitPropsNoShadow && !(n == "fus_cockpit")) src.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                if (src.sharedMaterials[0] == mats["paint"])
                {
                    var owner = parts.Values.First(p => PartRenderers(p.gameObject).Contains(src));
                    ((List<Renderer>)G(G(owner, "damageMaterial"), "renderers")).Add(cr);
                }
            }
            S(aircraft, "cockpitRenderers", cockpitR.ToArray());
            S(aircraft, "exteriorRenderers", exteriorR.ToArray());

            // ---- screens: mfd_center / mfd_left / mfd_right = the stock tac page (Cockpit.tacScreenRender + TargetCam.targetScreenRenderer;
            // TacScreenPanels: map + three upright side panels, B-25H method); the other screens (pilot / co-pilot side, EWO, WSO) = the stock
            // dark display glass (Touchscreen_off, EW-25), the GA-25X aux-pane rule
            var tacMat = Asset<Material>("Material/tacScreenDisplay_PLACEHOLDER.mat");
            var offMat = Asset<Material>("Material/Touchscreen_off_PLACEHOLDER.mat");
            Renderer tacR = null;
            foreach (var n in new[] { "mfd_center", "mfd_left", "mfd_right" })
            {
                var t = TryFind(n); if (t == null || !MFDScreens) continue;
                foreach (var r in t.GetComponentsInChildren<MeshRenderer>(true).Where(r => r.transform == t || r.name == n + "_int"))
                {
                    r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                    if (TacScreenPanels) { var mf = r.GetComponent<MeshFilter>(); mf.sharedMesh = TacScreenMesh(mf.sharedMesh, r.name + "_tac"); r.sharedMaterials = new[] { tacMat, offMat }; }
                    else r.sharedMaterials = new[] { tacMat };
                }
                if (n == "mfd_center") tacR = t.GetComponent<MeshRenderer>();
            }
            int dark = 0, live = 0;
            stationScreenLog.Clear(); deckScreenLog.Clear();
            var deckContent = new Dictionary<string, string>();
            if (contract["deck195"] != null && contract["deck195"].Type == Newtonsoft.Json.Linq.JTokenType.Object)
                foreach (var kv in (Newtonsoft.Json.Linq.JObject)contract["deck195"]["screens"]) deckContent[kv.Key] = (string)kv.Value;
            var deckMesh = new Dictionary<string, Mesh>();
            foreach (var r in root.GetComponentsInChildren<MeshRenderer>(true).Where(r => r.name.StartsWith("cockpit_screen_deck_")).OrderBy(r => r.name.EndsWith("_int") ? 1 : 0))
            {   // 1.9.5: our MFD units on our panel - the CI-22 tac page (tacScreen_cricket, the 1.9.3 page layout method) laid out per screen:
                // map (outboard, each pilot), panels12 = power + engine dials (inboard, each pilot), panel3 = attitude (centre), dark = standby glass;
                // the exterior original and its cockpit-view copy (_int) share one built mesh
                var baseName = r.name.EndsWith("_int") ? r.name.Substring(0, r.name.Length - 4) : r.name;
                if (!deckContent.TryGetValue(baseName, out var content)) { L($"WARN deck screen {r.name} not in the contract"); continue; }
                var mf = r.GetComponent<MeshFilter>();
                if (Deck195Screens && content != "dark")
                {
                    if (!deckMesh.TryGetValue(baseName, out var bm)) deckMesh[baseName] = bm = StationScreenMesh(mf.sharedMesh, baseName + "_tac", content);
                    mf.sharedMesh = bm; r.sharedMaterials = new[] { tacMat, offMat }; live++;
                }
                else { r.sharedMaterials = new[] { offMat }; dark++; }
                r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                deckScreenLog[baseName] = Deck195Screens ? content : "dark";
            }
            foreach (var r in root.GetComponentsInChildren<MeshRenderer>(true).Where(r => r.name.StartsWith("cockpit_screen_") && !r.name.StartsWith("cockpit_screen_deck_")))
            {   // 1.9.1: screen 1 of the WSO and EWO stations shows the live tac page (one shared tacScreenDisplay page, GA-25X two-screen rule)
                bool s1 = r.name.StartsWith("cockpit_screen_wso1") || r.name.StartsWith("cockpit_screen_ewo1");
                bool s2 = r.name.StartsWith("cockpit_screen_wso2") || r.name.StartsWith("cockpit_screen_ewo2");
                bool tac = s1 || (StationScreens193 && s2);
                if (tac && StationScreens193)
                {   // 1.9.3 (in game 1.9.2: WSO / EWO screen 2 dark, the map small beside the panels on screen 1): screen 1 = the tac map alone,
                    // screen 2 = the three tac panels (power, engine dials, attitude) side by side; same render texture, same UV method
                    var mf = r.GetComponent<MeshFilter>(); string content = s1 ? "map" : "panels";
                    mf.sharedMesh = StationScreenMesh(mf.sharedMesh, r.name + "_tac", content); r.sharedMaterials = new[] { tacMat, offMat };
                    stationScreenLog[r.name] = content;
                }
                else if (tac && TacPanels192)
                {   // 1.9.2: the B-25H / GA-25X tac-page layout (map + three upright side panels from the 1024 x 512 render texture, black backing),
                    // proven in game on those aircraft; 1.9.1 mapped the whole 2:1 texture onto a 1.1:1 screen
                    var mf = r.GetComponent<MeshFilter>(); mf.sharedMesh = TacScreenMesh(mf.sharedMesh, r.name + "_tac"); r.sharedMaterials = new[] { tacMat, offMat };
                }
                else r.sharedMaterials = Enumerable.Repeat(tac ? tacMat : offMat, r.sharedMaterials.Length).ToArray();
                r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                if (tac) live++; else dark++;
            }
            var ewTac = TryFind("cockpit_ew1_tacscreen");
            if (ewTac != null && ewTac.GetComponent<MeshRenderer>() != null)
            {
                tacR = ewTac.GetComponent<MeshRenderer>(); live++;
                if (EwScreens193)
                {   // 1.9.3 (in game 1.9.2: the centre screens showed the right part of the CI-22 page, the map split between the outer and the inner
                    // screen, the lower-left centre screen black): the stock EW1_targetScreen mesh carries ELEVEN screen rectangles with UVs laid out
                    // for the EW-25's own page (tacScreen_EW1). Our own quads on those rectangles (positions measured from the user's install at build
                    // time; no stock vertices shipped), the CI-22 page laid out per screen as on the EW-25 (outboard = map / radar, inboard = systems):
                    // outer = tac map, inner = power + engine-dial panels, lower centre = attitude panel, the other five dark glass (backing only)
                    var em = EwScreenMesh(ewTac.GetComponent<MeshFilter>().sharedMesh, "cockpit_ew1_tacscreen_tac");
                    foreach (var t in new[] { ewTac, TryFind("cockpit_ew1_tacscreen_int") }.Where(t => t != null))
                    {
                        t.GetComponent<MeshFilter>().sharedMesh = em;
                        var r = t.GetComponent<MeshRenderer>(); r.sharedMaterials = new[] { tacMat, offMat }; r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                    }
                    L($"EW-25 tac screen 1.9.3: {ewScreenLog.Count} screens - {string.Join("; ", ewScreenLog)}");
                }
            }
            if (tacR == null && TryFind("cockpit_screen_deck_mapL") != null) tacR = TryFind("cockpit_screen_deck_mapL").GetComponent<MeshRenderer>();   // 1.9.5 (any tacScreenDisplay renderer works: the page is one render texture)
            if (tacR == null)
            {
                var screen = NewGO("screen_dummy", cp.transform, Find("cockpit_interior").position, Quaternion.identity, 3);
                screen.AddComponent<MeshFilter>().sharedMesh = QuadMesh("screen_dummy", 0.01f, 0.01f);
                var sr = screen.AddComponent<MeshRenderer>(); sr.sharedMaterial = mats["screen"]; sr.enabled = false;
                tacR = sr; L("WARN screens: no mfd_center, hidden dummy screen");
            }
            L($"screens: {live} live tac pages (Cockpit.tacScreenRender = {tacR.name}; deck {string.Join(", ", deckScreenLog.Select(kv => kv.Key.Replace("cockpit_screen_deck_", "") + " " + kv.Value))}; WSO / EWO), {dark} other screens = Touchscreen_off");

            var interior = Find("cockpit_interior").gameObject;
            var ck = CloneComp(TplComp<global::Cockpit>("COIN:cockpit_F_interior"), interior);
            S(ck, "tacScreenRender", tacR); S(ck, "aircraft", aircraft);
            S(ck, "engineSources", EngineNums.Select(n => parts["engine_" + n].gameObject).ToArray());
            SetSeq(ck, "joysticks", new object[0]);
            SetSeq(ck, "throttles", new object[0]);
            if (CockpitAnimators)
            {
                CockpitAnimation(ck, cp);       // contract levers: cockpit_throttle (Cockpit.throttles, grip forward at full: sign-checked)
                var js = new List<object>();
                foreach (var n in new[] { "stick_L", "stick_R" })
                {   // Cockpit.Joystick: localEulerAngles = (pitch x range, 0, -roll x range); pitch > 0 = PUSH = stick top forward (stock CI-22 / SFB-81
                    // sign, the 1.8.12 column lesson); the anchors rest at identity in their parent
                    var t = TryFind(n); if (t == null) continue;
                    var d = DrivenFrame(t);
                    float rg = contract["deck195"] != null && contract["deck195"].Type == Newtonsoft.Json.Linq.JTokenType.Object ? (float)contract["deck195"]["stick_range"] : 12f;
                    var e = NewElem(ck, "joysticks"); S(e, "transform", d); S(e, "range", rg); js.Add(e);
                    cockpitAnimLog.Add($"{n}: Cockpit.joysticks range {rg} (stock {t.GetComponent<MeshFilter>()?.sharedMesh?.name} stick; stock sign: pitch > 0 = push = top forward)");
                }
                SetSeq(ck, "joysticks", js);
                foreach (var s_ in cockpitAnimLog.Where(x => x.StartsWith("stick_"))) L("cockpit anim " + s_);
            }

            // target camera in the EO/IR ball under the forward fuselage, rear view from the tail turret, laser designator (4 targets)
            var nose = parts["fus_nose"];
            var eo = TryFind("eo_ball");
            var eoPos = eo != null && eo.GetComponent<MeshFilter>() != null ? eo.TransformPoint(eo.GetComponent<MeshFilter>().sharedMesh.bounds.center) : root.transform.TransformPoint(new Vector3(0, -0.85f, 5.95f));
            var tcF = NewGO("targetCamForward", parts["fus_cockpit"].transform, eoPos + new Vector3(0, -0.05f, 0.18f), Quaternion.identity, 0);
            var tcR = NewGO("targetCamRear", parts["fus_tail"].transform, root.transform.TransformPoint(new Vector3(0, 0.0f, -15.9f)), Quaternion.LookRotation(Vector3.back), 0);
            var tcL = NewGO("landingCamPoint", nose.transform, root.transform.TransformPoint(new Vector3(0, -1.1f, 5.5f)), Quaternion.LookRotation(new Vector3(0, -0.3f, 1f)), 0);
            var tc = CloneComp(TplComp<TargetCam>("COIN:nose"), nose.gameObject);
            S(tc, "currentMount", tcF.transform); S(tc, "camMountForward", tcF.transform); S(tc, "camMountRear", tcR.transform); S(tc, "camMountLanding", tcL.transform);
            S(tc, "attachedPart", nose); S(tc, "targetScreenRenderer", tacR);
            var ld = CloneComp(TplComp<LaserDesignator>("COIN:nose"), nose.gameObject);
            S(ld, "unitPart", nose); S(ld, "aircraft", aircraft);
            try { S(ld, "maxTargets", LaserDesignatorTargets); } catch (Exception e) { L("note: LaserDesignator.maxTargets " + e.Message); }

            aircraft.cockpitViewPoint = helmetCam;
            aircraft.pilots = crew.ToArray();
            aircraft.targetCam = tc;
            aircraft.weaponManager = weaponManager;
            aircraft.cockpit = cp;
            S(aircraft, "controlsFilter", controlsFilter);
            S(aircraft, "groundEquipment", new GameObject[0]);
        }


        // =================================================================== 1.9.3 tac-page layouts on the cockpit screens
        // The CI-22 page (tacScreen_cricket) in its 1024 x 512 render texture: map u 0.001-0.791 (full height, upright); three panels in the right
        // column, rotated (screen right -> +v, screen up -> -u): power (v 0.718-0.979), engine dials (0.390-0.697), attitude (0.025-0.341). Same
        // regions as TacScreenMesh (the B-25H / GA-25X layout proven in game). One screen = a backing quad (submesh 1, dark glass) + content quads
        // (submesh 0, tacScreenDisplay) 0.6 mm in front, scaled to fit with the page's own aspect (no stretch), centred.
        static readonly (float u0, float u1, float v0, float v1)[] TacPanelUV = { (0.802f, 0.983f, 0.718f, 0.979f), (0.801f, 0.985f, 0.390f, 0.697f), (0.789f, 0.983f, 0.025f, 0.341f) };
        static readonly (float u0, float u1, float v0, float v1) TacMapUV = (0.001f, 0.791f, 0f, 1f);
        static readonly List<string> ewScreenLog = new List<string>();
        static readonly Dictionary<string, string> stationScreenLog = new Dictionary<string, string>();
        static readonly Dictionary<string, string> deckScreenLog = new Dictionary<string, string>();   // 1.9.5 deck MFDs: name -> content
        static int ewScreensFound, ewScreensLive, ewScreensDark; static bool ewLayoutOk;
        class ScreenRect { public Vector3 o, ex, ey, n; public float W, H; public bool flip; public string role, content; }

        // elements of a content kind: (uv rect, rotated, on-screen aspect w / h)
        static List<((float u0, float u1, float v0, float v1) r, bool rot, float aspect)> TacElements(string content)
        {
            var l = new List<((float u0, float u1, float v0, float v1) r, bool rot, float aspect)>();
            float PA((float u0, float u1, float v0, float v1) q) => (q.v1 - q.v0) * 512f / ((q.u1 - q.u0) * 1024f);
            if (content == "map") l.Add((TacMapUV, false, (TacMapUV.u1 - TacMapUV.u0) * 1024f / ((TacMapUV.v1 - TacMapUV.v0) * 512f)));
            if (content == "panels12" || content == "panels") { l.Add((TacPanelUV[0], true, PA(TacPanelUV[0]))); l.Add((TacPanelUV[1], true, PA(TacPanelUV[1]))); }
            if (content == "panel3" || content == "panels") l.Add((TacPanelUV[2], true, PA(TacPanelUV[2])));
            return l;
        }

        // all screens into one two-submesh mesh; `ok` false when a content quad leaves its screen
        static Mesh ScreensMesh(string name, List<ScreenRect> screens, out bool ok)
        {
            ok = true;
            const float lift = 0.0006f, g = 0.004f;
            var v = new List<Vector3>(); var uv = new List<Vector2>(); var t0 = new List<int>(); var t1 = new List<int>();
            foreach (var s in screens)
            {
                Vector3 P(float x, float y, float z) => s.o + s.ex * x + s.ey * y + s.n * z;
                void Quad(List<int> tris, float x0, float y0, float x1, float y1, float z, Vector2 a, Vector2 b, Vector2 c, Vector2 d)
                {
                    int i = v.Count;
                    v.Add(P(x0, y0, z)); v.Add(P(x1, y0, z)); v.Add(P(x1, y1, z)); v.Add(P(x0, y1, z));
                    uv.Add(a); uv.Add(b); uv.Add(c); uv.Add(d);
                    if (s.flip) tris.AddRange(new[] { i, i + 2, i + 1, i, i + 3, i + 2 }); else tris.AddRange(new[] { i, i + 1, i + 2, i, i + 2, i + 3 });
                }
                Quad(t1, 0, 0, s.W, s.H, 0, Vector2.zero, Vector2.right, Vector2.one, Vector2.up);
                var els = TacElements(s.content);
                if (els.Count == 0) continue;
                float sumA = els.Sum(e => e.aspect);
                float h = Mathf.Min(s.H - 2 * g, (s.W - 2 * g - (els.Count - 1) * g) / sumA);
                float x = (s.W - (sumA * h + (els.Count - 1) * g)) / 2, y0 = (s.H - h) / 2;
                foreach (var e in els)
                {
                    float w = e.aspect * h; var r = e.r;
                    if (!e.rot) Quad(t0, x, y0, x + w, y0 + h, lift, new Vector2(r.u0, r.v0), new Vector2(r.u1, r.v0), new Vector2(r.u1, r.v1), new Vector2(r.u0, r.v1));
                    else Quad(t0, x, y0, x + w, y0 + h, lift, new Vector2(r.u1, r.v0), new Vector2(r.u1, r.v1), new Vector2(r.u0, r.v1), new Vector2(r.u0, r.v0));
                    if (x < -1e-5f || x + w > s.W + 1e-5f || y0 < -1e-5f || y0 + h > s.H + 1e-5f || h <= 0f) ok = false;
                    x += w + g;
                }
            }
            var m = new Mesh { name = name };
            m.SetVertices(v); m.SetUVs(0, uv); m.subMeshCount = 2; m.SetTriangles(t0, 0); m.SetTriangles(t1, 1);
            m.RecalculateNormals(); m.RecalculateTangents(); m.RecalculateBounds();
            generatedMeshes.Add(m);
            return m;
        }

        // one of our station screens (contract quad, UV 0..1: +u = screen right, +v = up, the TacScreenMesh frame)
        static Mesh StationScreenMesh(Mesh src, string name, string content)
        {
            var sv = src.vertices; var suv = src.uv;
            int Near(Vector2 q) { int b = 0; for (int i = 1; i < suv.Length; i++) if ((suv[i] - q).sqrMagnitude < (suv[b] - q).sqrMagnitude) b = i; return b; }
            Vector3 o = sv[Near(Vector2.zero)], ex = sv[Near(Vector2.right)] - o, ey = sv[Near(Vector2.up)] - o;
            var st = src.GetTriangles(0);
            var n = Vector3.Cross(sv[st[1]] - sv[st[0]], sv[st[2]] - sv[st[0]]).normalized;
            var s = new ScreenRect { o = o, ex = ex.normalized, ey = ey.normalized, W = ex.magnitude, H = ey.magnitude, n = n, content = content, role = name };
            s.flip = Vector3.Dot(Vector3.Cross(s.ex, s.ey), n) < 0;
            var m = ScreensMesh(name, new List<ScreenRect> { s }, out bool ok);
            if (!ok) throw new Exception("station screen layout outside its screen: " + name);
            return m;
        }

        // the stock EW-25 wide tac screen: its connected pieces are the screen rectangles (UVs affine on each); fit P = o + u A + v B per piece
        // (least squares), take the UV bounding box -> the rectangle, screen up = the in-plane axis with the larger height change, right = +x
        static Mesh EwScreenMesh(Mesh src, string name)
        {
            var sv = src.vertices; var suv = src.uv; var tri = src.GetTriangles(0);
            var par = Enumerable.Range(0, sv.Length).ToArray();
            int F(int i) { while (par[i] != i) { par[i] = par[par[i]]; i = par[i]; } return i; }
            for (int k = 0; k < tri.Length; k += 3) { par[F(tri[k])] = F(tri[k + 1]); par[F(tri[k + 1])] = F(tri[k + 2]); }
            var groups = Enumerable.Range(0, sv.Length).GroupBy(F).ToList();
            var screens = new List<ScreenRect>();
            ewScreenLog.Clear();
            foreach (var gp in groups)
            {
                var idx = gp.ToList();
                // normal equations for the unknowns (o, A, B), rows (1, u, v); Cramer per unknown and coordinate
                double s00 = 0, s01 = 0, s02 = 0, s11 = 0, s12 = 0, s22 = 0; var r0 = Vector3.zero; var r1 = Vector3.zero; var r2 = Vector3.zero;
                foreach (var i in idx) { double u = suv[i].x, w = suv[i].y; s00 += 1; s01 += u; s02 += w; s11 += u * u; s12 += u * w; s22 += w * w; r0 += sv[i]; r1 += sv[i] * (float)u; r2 += sv[i] * (float)w; }
                double[,] M = { { s00, s01, s02 }, { s01, s11, s12 }, { s02, s12, s22 } };
                double D3(double[,] q) => q[0, 0] * (q[1, 1] * q[2, 2] - q[1, 2] * q[2, 1]) - q[0, 1] * (q[1, 0] * q[2, 2] - q[1, 2] * q[2, 0]) + q[0, 2] * (q[1, 0] * q[2, 1] - q[1, 1] * q[2, 0]);
                double det = D3(M);
                if (Math.Abs(det) < 1e-12) throw new Exception("EW screen piece with degenerate UVs (" + idx.Count + " vertices)");
                Vector3 Solve(int col)
                {
                    var res = Vector3.zero;
                    for (int c = 0; c < 3; c++)
                    {
                        double[] b = { r0[c], r1[c], r2[c] };
                        var Mc = (double[,])M.Clone(); for (int rr = 0; rr < 3; rr++) Mc[rr, col] = b[rr];
                        res[c] = (float)(D3(Mc) / det);
                    }
                    return res;
                }
                Vector3 O = Solve(0), A = Solve(1), B = Solve(2);
                float umin = idx.Min(i => suv[i].x), umax = idx.Max(i => suv[i].x), vmin = idx.Min(i => suv[i].y), vmax = idx.Max(i => suv[i].y);
                Vector3 au = A * (umax - umin), bv = B * (vmax - vmin), c0 = O + A * umin + B * vmin, ctr = c0 + au / 2 + bv / 2;
                bool uUp = Mathf.Abs(au.y) > Mathf.Abs(bv.y);
                Vector3 up = uUp ? au : bv, rt = uUp ? bv : au;
                if (up.y < 0) up = -up;
                if (rt.x < 0) rt = -rt;
                int t = -1; for (int k = 0; k < tri.Length; k += 3) if (idx.Contains(tri[k])) { t = k; break; }
                var n = Vector3.Cross(sv[tri[t + 1]] - sv[tri[t]], sv[tri[t + 2]] - sv[tri[t]]).normalized;
                var s = new ScreenRect { ex = rt.normalized, ey = up.normalized, W = rt.magnitude, H = up.magnitude, n = n };
                s.o = ctr - rt / 2 - up / 2;
                s.flip = Vector3.Dot(Vector3.Cross(s.ex, s.ey), n) < 0;
                float ax = Mathf.Abs(ctr.x);
                if (ax < 0.06f) { s.role = "centre top"; s.content = "dark"; }
                else if (s.H > s.W) { s.role = "side portrait"; s.content = "dark"; }
                else if (ctr.y > 0.22f) { s.role = ax > 0.32f ? "outer" : "inner"; s.content = ax > 0.32f ? "map" : "panels12"; }
                else { s.role = ax < 0.30f ? "lower centre" : "lower outer"; s.content = ax < 0.30f ? "panel3" : "dark"; }
                if (ax >= 0.06f) s.role += ctr.x < 0 ? " L" : " R";
                screens.Add(s);
            }
            screens = screens.OrderByDescending(s => s.o.y).ThenBy(s => s.o.x).ToList();
            var m = ScreensMesh(name, screens, out ewLayoutOk);
            ewScreensFound = screens.Count; ewScreensLive = screens.Count(s => s.content != "dark"); ewScreensDark = screens.Count(s => s.content == "dark");
            foreach (var s in screens) ewScreenLog.Add($"{s.role} {s.W:F3} x {s.H:F3} m -> {s.content}");
            return m;
        }
