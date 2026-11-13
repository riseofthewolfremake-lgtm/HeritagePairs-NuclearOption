        static void ControlSurfaces()
        {
            foreach (var side in new[] { "L", "R" })
            {
                float sgn = side == "L" ? -1f : 1f;
                CS("aileron_" + side, "CAS1:aileron_" + side, 0, 18f * sgn, 0, 50f);
                CS("elevator_" + side, "CAS1:elevator_" + side, -ElevatorUp, 0, 0, 35f);
            }
            CS("rudder", "CAS1:rudder_L", 0, 0, -22f, 40f);
        }

        static void CS(string part, string template, float pitch, float roll, float yaw, float servo)
        {
            var c = CloneComp(TplComp<ControlSurface>(template), parts[part].gameObject);
            S(c, "pitchRange", pitch); S(c, "rollRange", roll); S(c, "yawRange", yaw); S(c, "brakeRange", 0f);
            S(c, "attachedSurface", parts[part]);
            S(c, "visibleMesh", liftNormals[part].gameObject);
            S(c, "flap", false); S(c, "servoSpeed", servo);
            S(c, "splitDrag", 0f); S(c, "maxSplit", 0f); S(c, "yawSplitFactor", 0f);
            S(c, "splitUpper", null); S(c, "splitLower", null); S(c, "splitSound", null);
        }

        // flaps: speed-scheduled HighLiftDevice on each flap part (B-25H method), split-flap travel 40 deg, down below 140 mph
        // 1.6.3 (in-game take-off test of 1.6.2): with the wing curve a 35 deg flap sat post-stall (flap AoA ~42 deg: CD 0.79, CL 0.95):
        // 27 kN of drag at 50 m/s for almost no lift, so the roll stalled at 51 m/s. Now airfoil 3 (B17G_flap), 28 deg, more area.
        const float FlapDeg = 28f, FlapAreaInner = 3.6f, FlapAreaOuter = 3.9f, FlapLiftForward = 1.6f;
        static void Flaps()
        {
            foreach (var f in new[] { "flap_inner_L", "flap_inner_R", "flap_outer_L", "flap_outer_R" })
            {
                var h = CloneComp(TplComp<HighLiftDevice>("COIN:flap_L"), parts[f].gameObject);
                S(h, "aeroPart", parts[f]); S(h, "swingWingController", null);
                S(h, "speedDeployed", 52f); S(h, "speedRetracted", 63f);
                S(h, "alphaMin", 0f); S(h, "alphaFactor", 0f);
                S(h, "deployedArea", f.Contains("inner") ? FlapAreaInner : FlapAreaOuter);
                var mp = NewElem(h, "movingParts");
                S(mp, "move", false); S(mp, "rotate", true); S(mp, "transform", liftNormals[f]);
                S(mp, "positionRetracted", Vector3.zero); S(mp, "positionDeployed", Vector3.zero);
                S(mp, "anglesRetracted", Vector3.zero); S(mp, "anglesDeployed", new Vector3(-FlapDeg, 0, 0));
                SetSeq(h, "movingParts", new[] { mp });
            }
        }

        // ------------------------------------------------------------------ landing gear (forward-retracting mains, retracting tailwheel)
        // Model: gear_main_L/R (leg, pivot = trunnion) > wheel_main_L/R (round tyre, pivot = axle); gear_tail > wheel_tail (round tyre) + fork_tail.
        // LandingGear spins every transform in `wheels` about its local X (LandingGear.cs 556-558) and steers `unsprung` about its local Y
        // (LandingGear.cs 718-724): the wheel transform carries the tyre ONLY; the tail fork rides on unsprung (steers, never spins).
        // Round 3 (user: whole tail assembly spun, no steering): the fal tail wheel was one mesh (wheel + fork) under wheel_tail; the tail
        // lock was +35 (B-25H nose-wheel sign; a wheel behind the CG steers the other way: Nimrod / FD-32 use -30, verified live) and its
        // frictionCoef 0.1 (stock CAS1 gear_F 0.8, CAS1.prefab:8697): no side grip to turn 25 t.
        // LandingGear folds gearHinge about its local X by foldDegrees (LandingGear.cs OnSetGear). Blender forward-up +90 about +X is
        // Unity -90 (handedness flip, export_b17g.py rule); the check verifies the stowed wheel moves FORWARD and UP.
        // Springs sized for 25 t: static load per main ~11 t -> k 1.6 MN/m gives ~6.9 cm static sag; damping ~0.35 critical.
        class GearSpec { public string leg, wheel, part, fork; public float fold, travel, k, c, maxComp, mass, drag, r; public bool steer, brake; public float diff; }
        const float MainK = 1.6e6f, MainC = 1.3e5f, MainMaxComp = 0.45f, TailK = 3.5e5f, TailC = 3.0e4f;
        // 1.6.1 ground handling (in game 1.6.0: no steering, 1.74 m/s2 braking, nose-over on grass at 119 km/h):
        // - BrakeFriction 0.29 (was 0.20): braking ~2.6 m/s2, holds ~62 kN (0.6 throttle ~53 kN); nose-over margin kept >= 3 deg by the
        //   10.4 deg forward leg rake (b17g_spec.MAIN_RAKE 0.25 m: tail-up CoM angle ~19.4 deg vs atan 0.29 = 16.2 deg);
        // - MainContactArea 0.09 m2 (was CAS1's 0.04): LandingGear.cs 334-342 sinks a wheel into soft ground by pressure
        //   (load / (contactArea x 1e4)) and drags it with 2.5 depth^2 |v| pressure^2: at 115 kN per main and 33 m/s that is ~200 kN per
        //   wheel with 0.04 (the grass nose-over) and ~9 kN with 0.09 (a 56 in tyre's real patch is ~0.2 m2);
        // - MainRolling 0.02 (CAS1 0.05; AB-4 0.01): concrete rolling resistance of big low-pressure tyres;
        // - DiffBrake 2.0 (was 1): LandingGear.cs 551-553 adds Clamp01(yaw x 0.3 x factor) brake on the inside main between 3 and 30 m/s.
        // 1.7.3: 0.29 -> 0.22. In game (1.7.2) a full-brake stop from a 68 m/s tail-up touchdown nosed over (pitch -36 deg at 7 m/s,
        // tail gun and rudder broke off on the fall back); margin now atan 0.22 = 12.4 deg vs the 19.4 deg tail-up CoM angle.
        // 1.7.12 (in game 1.7.10 P6: 1 of 3 landed AI B-17Gs circled its exit-taxi point at 9 m/s, r ~50 m, for 10+ min): the mains' side grip is
        // frictionCoef x load = 0.22 g (the 1.7.3 brake nose-over value), so at 9 m/s no turn tighter than v^2 / (0.22 g) ~ 38 m is possible and
        // the exit point (arrival < 20 m, AIPilotTaxiState) stays inside the circle. Brake friction stays (nose-over); instead the inner-wheel
        // differential brake (LandingGear: + Clamp01(yaw x 0.3 x factor) between 3 and 30 m/s) 2 -> 3.5 slows it in hard taxi turns
        // (yaw 0.6: 0.36 -> 0.63 brake on the inner main) and the tail-wheel lock -30 -> -45 tightens the steered radius.
        // 1.8.0 (user on 1.7.13: "keep spinning out on runways"): split main wheel (GripGear.cs, groundcom.py): the braked LandingGear and an
        // unbraked grip LandingGear on the same contact, both frictionCoef MainFriction 0.8 (stock); the braked one carries MainBrakeShare of the
        // spring, so braking stays BrakeFriction 0.22 x load (= 0.8 x 0.275, the 1.7.3 nose-over value) and the side grip is 0.8 x load (the
        // 1.7.10 exit-taxi circle: a 9 m/s turn now needs ~10 m instead of ~38 m).
        const float MainFriction = 0.8f, MainBrakeShare = 0.275f;
        const bool SplitMainGear = true;
        // 1.8.8 (user on 1.8.7: line up, full throttle, no input -> veers left or right after ~100 m, onto the grass): castoring mains
        // (GripGear.Castor; tools/flightmodel/taildragger_track.py). The 1.8.3 take-off log: the tail wheel's load falls with V^2 (32.8 kN at rest,
        // 0 from 30.8 m/s ~110 m) and the heading starts to move right then (yaw rate x2.5 per second); from there only the mains, 1.4 m AHEAD of
        // the CoM, grip, and a gripping wheel ahead of the CoM is directionally unstable (LandingGear side force, 627-656). Stock tricycles keep
        // their gripping wheels behind the CoM and castor the one in front (aligningStrength 5); this is that arrangement mirrored: the mains
        // castor within +-MainCastorRange, the tail wheel stays locked (TailAligning 0). Model, no input: 90 % heading change 9.8 -> 0.09 deg,
        // lateral 32.6 -> 0.34 m (stock A-19 0.08 deg / 0.61 m); taxi 7 m/s 6 s 164 -> 156 deg. false = the 1.8.7 behaviour.
        const bool MainCastor188 = true;
        const bool ColumnPlugin189 = true;
        const bool ANM2Guns = true;             // 1.8.13 (offline L): our own AN/M2 on every gun slot (ANM2Gun.cs); false = the stock door-gun barrel      // 1.8.9 (offline J): the columns / wheels are moved by B25H.Instruments (b17g_joystick.cs), no Cockpit.joysticks
        const float MainCastorRange = 6f, MainCastorAlign = 5f;
        const float BrakeFriction = 0.22f, MainContactArea = 0.09f, MainRolling = 0.02f, DiffBrake = 3.5f, MainFoldDeg = 79.7f;
        // tail wheel behind the CG: negative lock (rudder right -> wheel left -> tail swings left -> nose right). aligningStrength 0: no
        // castering (LandingGear.cs 602-606 turns the wheel toward the ground track), so the wheel stays at yaw x lock and resists a swing
        // like the B-17's locked tailwheel; full lock radius about the main-gear centre = wheelbase 11.8 m / tan 30 = 20 m.
        const float TailSteeringLock = -45f, TailSteeringSpeed = 60f, TailAligning = 0f, TailFriction = 0.8f;   // 1.7.12: -30 -> -45 (exit-taxi circle)
        static readonly Dictionary<LandingGear, Transform> gearWheelVisual = new Dictionary<LandingGear, Transform>();

        static List<LandingGear> Gear()
        {
            gearWheelVisual.Clear();
            var list = new List<LandingGear>();
            foreach (var s in new[] { "L", "R" })
                list.Add(MakeGear(new GearSpec { leg = "gear_main_" + s, wheel = "wheel_main_" + s, part = "wing_inner_" + s, fold = -MainFoldDeg, travel = 0.711f + 0.35f, k = MainK, c = MainC,
                    maxComp = MainMaxComp, mass = 450f, drag = MainGearDrag, r = 0.711f, steer = false, brake = true, diff = s == "L" ? -DiffBrake : DiffBrake }, "CAS1:gear_" + s + "_sprung", "COIN:wheel_" + s));
            list.Add(MakeGear(new GearSpec { leg = "gear_tail", wheel = "wheel_tail", part = "fus_tail", fold = 27f, travel = 0.33f + 0.20f, k = TailK, c = TailC,
                maxComp = 0.30f, mass = 80f, drag = TailGearDrag, r = 0.33f, steer = true, brake = false, diff = 0f, fork = "fork_tail" }, "CAS1:gear_F_sprung", "COIN:wheel_F"));
            return list;
        }

        static LandingGear MakeGear(GearSpec g, string tplGear, string tplWheel)
        {
            var leg = Find(g.leg); var wheel = Find(g.wheel); var part = parts[g.part];
            float r = g.r;
            Vector3 axle = wheel.position;
            var hinge = NewGO(g.leg + "_hinge", part.transform, leg.position, part.transform.rotation);
            leg.SetParent(hinge.transform, true);
            var sprung = NewGO(g.leg + "_sprung", hinge.transform, leg.position, part.transform.rotation);
            var unsprung = NewGO(g.leg + "_unsprung", sprung.transform, axle, part.transform.rotation);
            wheel.SetParent(unsprung.transform, true);
            if (!string.IsNullOrEmpty(g.fork)) Find(g.fork).SetParent(unsprung.transform, true);      // steers with the wheel, does not spin
            var bump = NewGO(g.leg + "_bumpstop", sprung.transform, axle + Vector3.up * (g.travel - r), part.transform.rotation);
            var dust = CopyParticle(TplFind(tplWheel).GetComponent<ParticleSystem>(), unsprung.transform, axle - Vector3.up * r, g.leg + "_dust");
            var tw = TplFind(tplWheel).GetComponents<AudioSource>();
            var a0 = CloneComp(tw[0], wheel.gameObject); var a1 = CloneComp(tw[1], wheel.gameObject);
            var box = sprung.AddComponent<BoxCollider>();
            var lmf = leg.GetComponent<MeshFilter>();
            var sb = lmf != null ? lmf.sharedMesh.bounds : new Bounds(Vector3.zero, Vector3.one * 0.1f);
            box.center = sprung.transform.InverseTransformPoint(leg.TransformPoint(sb.center)); box.size = sb.size; box.enabled = false;
            var lg = CloneComp(TplComp<LandingGear>(tplGear), sprung);
            S(lg, "attachedPart", part); S(lg, "aircraft", aircraft);
            S(lg, "extendedDrag", g.drag);
            S(lg, "bumpStop", bump); S(lg, "unsprung", unsprung);
            S(lg, "suspensionTravel", g.travel); S(lg, "springRate", g.k); S(lg, "dampingRate", g.c);
            S(lg, "castPoint", bump.transform); S(lg, "wheelRadius", r);
            S(lg, "wheels", new[] { wheel }); S(lg, "axle", unsprung.transform);
            SetSeq(lg, "joints", new object[0]);
            S(lg, "tireNoiseSound", a0); S(lg, "tireSkidSound", a1);
            S(lg, "maxCompression", g.maxComp); S(lg, "mass", g.mass); S(lg, "gearCollider", box);
            S(lg, "gearHinge", hinge.transform); S(lg, "hingeFoldMotion", Vector3.zero);
            S(lg, "foldDegrees", g.fold); S(lg, "foldSpeed", 12f);
            S(lg, "strutRotationTransform", null); S(lg, "strutRotation", 0f);
            SetSeq(lg, "movingParts", new object[0]);
            S(lg, "steering", g.steer); S(lg, "braked", g.brake);
            S(lg, "steeringLock", g.steer ? TailSteeringLock : 0f); S(lg, "steeringSpeed", g.steer ? TailSteeringSpeed : 0f); S(lg, "aligningStrength", g.steer ? TailAligning : 0f);
            S(lg, "differentialBrakeFactor", g.diff);
            S(lg, "frictionCoef", g.brake ? (SplitMainGear ? MainFriction : BrakeFriction) : TailFriction);
            if (g.brake) { S(lg, "contactArea", MainContactArea); S(lg, "rollingResistance", MainRolling); }
            S(lg, "dust", dust);
            S(lg, "gearDoors", new List<LandingGear.GearDoor>());
            gearWheelVisual[lg] = wheel;
            L($"gear {g.leg}: r={r:F3} axle={axle.ToString("F3")} travel={g.travel} k={g.k} c={g.c} fold={g.fold}");
            if (g.brake && SplitMainGear) GripGear.Add(lg, MainBrakeShare, MainFriction, L);
            if (g.brake && MainCastor188) GripGear.Castor(lg, MainCastorRange, MainCastorAlign, L);     // after the split: the grip leg copies `axle`, not `steering`
            return lg;
        }

