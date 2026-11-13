// B25H.Instruments 1.8.9 (offline J, 2026-11-08): ground lateral grip at the CoM + ground yaw damper for the taildraggers (B17G, NIMROD1,
// FD32 only). User on 1.8.8: "very 'floaty' when on the ground ... 'drifting', AKA moving in one direction when pointed another".
//
// Cause: the 1.8.8 castoring mains (MainCastor188: steering, aligningStrength 5, steeringLock 6) turn toward their own ground track
// (LandingGear.cs 602-606) and give no side force inside +-6 deg of slip (627-656), so with the tail wheel light nothing holds the
// aircraft sideways. Gripping mains ahead of the CoM (1.8.7) held it but made the take-off roll directionally unstable once the tail wheel
// unloads (the veer). A force AT THE CoM has no yaw moment: it makes the velocity follow the heading without the destabilising moment.
// Model: tools/flightmodel/taildragger_track.py (table_j / selftest_j, candidate "(c++)"): no-input roll heading 90 % 0.03-0.06 deg,
// take-off drift angle in gusts 0.41-0.70 deg (stock A-19 / CI-22 0.69 / 0.80, 1.8.8 1.77-2.06), taxi-turn slide 3.4-4.6 deg (1.8.8 14-32).
//
// Law (the game's own wheel side law, applied to the CoM velocity; GripMu / GripResp = taildragger_track.COM_GRIP):
//   F_lat = -clamp(slip deg x GripResp x (0.2 + 0.01 |u|), +-1) x GripMu x N   (|u| >= 1 m/s; below: -clamp(3 v, +-1) x GripMu x N)
//   N = the sum of the aircraft's LandingGear loads (compressionForce + dampingForce, the same number each wheel's own friction uses), so
//   it fades to 0 at lift-off and is 0 in the air. Applied with AddForceAtPosition at the aircraft CoM (Unit.GetCenterOfMass, cached in
//   root-local space every 2 s): no moment. Ground-plane lateral axis of the heading; no longitudinal component.
//   Yaw damper: torque -YawDamp x Izz x r about world up, only while a wheel is loaded AND |yaw input| < 0.05 (taxi turns with rudder /
//   brakes are untouched); Izz per aircraft = the model's numbers. No prop / torque / P-factor effect is imitated anywhere.
// Cost: no FindObjectsOfType of its own (registration rides on the existing 2 s ScanExtras pass), per aircraft one cached LandingGear
// array and compiled field getters (no boxing), FixedUpdate does arithmetic + 2 AddForce calls. Only the aircraft we simulate (LocalSim).
// Flag: config [Ground] GroundGrip189 = Auto (build default GroundGripDefault189, OFF until the live probe passes) / On / Off.
// 1.9.7 (DeckRelative197): every velocity in this stack is taken RELATIVE to the surface under the loaded wheels (the contact collider's
// rigidbody at the CoM + AnimatedPhysicsSurface, the wheels' own rule in LandingGear.FixedUpdate). 1.8.9-1.9.6 used the world velocity: on a
// moving carrier deck the CoM grip pushed with up to mu x N toward 'world velocity along the heading' and beat the wheels' own friction.
// On ground without a rigidbody, or on a rigidbody at rest, the surface terms are exactly zero and the castor schedule is the land one: the 1.9.6 behaviour.
using System;
using System.Collections.Generic;
using System.Linq.Expressions;
using System.Reflection;
using UnityEngine;

namespace B25H.Instruments
{
    public static class GroundGripMath
    {
        public const float GripMu = 0.6f, GripResp = 1.0f, YawDamp = 6.0f;
        public static float IzzFor(string key) => key == "B17G" ? 800000f : key == "NIMROD1" ? 4962f * 1714f / 1567f : key == "FD32" ? 6060f * 1830f / 1486f : key == MsbKey ? MsbIzz : 0f;
        public static bool IsGripKey(string key) => key == "B17G" || key == "NIMROD1" || key == "FD32";
        // 1.9.0: the MSB-17/80 (the upgraded B-17G, same gear on the B-17G stations, 34-43 t): Izz = the B-17G's x mass ratio (34 / 28.47) x 1.10
        // (tools/flightmodel/msb1780_ground.py); registered only with [Ground] MsbGround190 on (Plugin.MsbGroundOn)
        public const string MsbKey = "MSB17";   // 1.9.9: was "MSB1780"
        public const float MsbIzz = 1051078f;
        public static bool IsMsbKey(string key) => key == MsbKey;
        /// lateral force (N, + = right) for CoM velocity u (along the heading) / v (right), total wheel load N
        public static float LateralForce(float u, float v, float N) => LateralForce(u, v, N, GripMu);
        /// 1.8.11: the same law with the friction coefficient given (TaxiTurnMath.GripMuK when the taxi-turn piece is on)
        public static float LateralForce(float u, float v, float N, float mu)
        {
            float cap = mu * Mathf.Max(N, 0f);
            if (cap <= 0f) return 0f;
            if (Mathf.Abs(u) < 1f) return Mathf.Clamp(-v * 3f, -1f, 1f) * cap;
            float slip = Mathf.Clamp(Mathf.Atan2(v, Mathf.Abs(u)) * Mathf.Rad2Deg, -10f, 10f);
            return -Mathf.Clamp(slip * GripResp * (0.2f + Mathf.Abs(u) * 0.01f), -1f, 1f) * cap;
        }
        public static float DampTorque(float izz, float yawRate, float yawInput, bool loaded) => DampTorque(izz, yawRate, yawInput, loaded, YawDamp);
        /// 1.9.2: the same law with the gain given (MsbYawDamp for the MSB-17/80; the B-17G / Mk I / FD-32 keep YawDamp)
        public static float DampTorque(float izz, float yawRate, float yawInput, bool loaded, float gain) => loaded && Mathf.Abs(yawInput) < 0.05f ? -gain * izz * yawRate : 0f;
        // 1.9.2 (in game 1.9.0, 41.9 t no-input take-off: steady yaw -0.04..-0.08 deg/s with beta 0 and both castoring mains settled at -0.1 deg,
        // 0.9 deg / 7.7 m at lift-off after 592 m): the damper's steady-state yaw rate is disturbance / (gain x Izz), so 6 -> 24 /s cuts it 4x
        // (0.015 deg/s: ~0.2 deg / ~1.5 m by lift-off, tools/flightmodel/msb1780_ground.py table_192). Explicit step k x dt = 24 x 0.02 = 0.48 < 2
        // (stable; at the 42 t Izz the effective gain is ~19). Only the MSB; it has no rudder input in this law (|yaw input| < 0.05).
        public const float MsbYawDamp = 24f;
        public static float YawDampFor(string key) => key == MsbKey ? MsbYawDamp : YawDamp;
    }

    /// 1.9.7: moving-surface (carrier deck, elevator) helpers; pure functions, mirrored in tools/flightmodel/deck197.py
    public static class DeckMath
    {
        public const float LockV0 = 3f, LockV1 = 6f;   // deck-relative speed: castoring mains fixed straight below V0, the land schedule from V1
        public const float MoveOn = 0.5f, MoveOff = 0.25f, YawOn = 0.002f;   // a surface counts as MOVING above 0.5 m/s (released below 0.25) or 0.002 rad/s of yaw
        /// deck mode = the wheels stand on a rigidbody that is actually moving. A rigidbody at rest (a hangar floor, a parked ship) changes nothing:
        /// its velocity terms are zero and the land castor schedule stays, so every land surface keeps the 1.9.6 behaviour.
        public static bool IsMoving(float surfaceSpeed, float surfaceYawRate, bool was) => surfaceSpeed > (was ? MoveOff : MoveOn) || Mathf.Abs(surfaceYawRate) > YawOn;
        /// load-weighted surface velocity: sum(load_i x v_i) / sum(load_i); legs on static ground carry v = 0
        public static Vector3 SurfaceVelocity(Vector3 weighted, float load) => load > 0f ? weighted / load : Vector3.zero;
        /// castor range on a moving surface: 0 (mains fixed straight = a stock carrier aircraft's mains, full side friction) while parked, on the
        /// elevator and at slow taxi; blends to the land schedule (TaxiTurnMath.CastorLock) between LockV0 and LockV1 of DECK-RELATIVE speed
        public static float CastorLockDeck(float relSpeed, float built)
        {
            float u = Mathf.Abs(relSpeed);
            if (u <= LockV0) return 0f;
            float land = TaxiTurnMath.CastorLock(u, built);
            return u >= LockV1 ? land : Mathf.Lerp(0f, land, (u - LockV0) / (LockV1 - LockV0));
        }
    }

    public partial class Plugin
    {
        const bool GroundGripDefault189 = true;       // 1.8.9 family build: ON (the user flies 1.8.9 themself; cfg "Off" disables)
        BepInEx.Configuration.ConfigEntry<string> groundGripMode;
        bool GroundGripOn
        {
            get
            {
                if (groundGripMode == null) groundGripMode = Config.Bind("Ground", "GroundGrip189", "Auto", "1.8.9: lateral grip at the CoM + ground yaw damper for the B-17G / Mk I / FD-32 (stops the sideways drift on the ground). Auto = build default, On, Off.");
                var m = groundGripMode.Value;
                return m == "On" || (m != "Off" && GroundGripDefault189);
            }
        }

        // 1.9.0: MSB-17/80 in this stack (and TaxiTurn1811, which rides on the same registration). Off by default until the game worker's live
        // probe (the user's no-input full-throttle take-off test) passes; then flip MsbGroundDefault190. Off = the MSB is never registered.
        const bool MsbGroundDefault190 = true;    // 1.9.2: ON by default (as 1.8.12 did for TaxiTurn1811): the 1.9.0 live probe passed at 34 / 38 t with it on, and the 42 t drift is fixed in the damper gain (MsbYawDamp)
        BepInEx.Configuration.ConfigEntry<string> msbGroundMode;
        bool MsbGroundOn
        {
            get
            {
                if (msbGroundMode == null) msbGroundMode = Config.Bind("Ground", "MsbGround190", "Auto", "1.9.0: the MSB-17 on the taildragger ground stack (GroundGrip189 + TaxiTurn1811, as the B-17G). Auto = build default (off until the live probe passes), On, Off.");
                var m = msbGroundMode.Value;
                return m == "On" || (m != "Off" && MsbGroundDefault190);
            }
        }

        // 1.9.7: deck-relative velocities + castor lock on moving surfaces. Off = exactly the 1.9.6 code path (world velocity).
        const bool DeckRelativeDefault197 = true;
        BepInEx.Configuration.ConfigEntry<string> deckRelativeMode;
        bool DeckRelativeOn
        {
            get
            {
                if (deckRelativeMode == null) deckRelativeMode = Config.Bind("Ground", "DeckRelative197", "Auto", "1.9.7: the taildragger ground stack works on the velocity relative to the surface under the wheels (moving carrier decks, elevators) and fixes the castoring mains straight at low deck speed. No effect on land. Auto = build default, On, Off (= 1.9.6).");
                var m = deckRelativeMode.Value;
                return m == "On" || (m != "Off" && DeckRelativeDefault197);
            }
        }
        static Func<LandingGear, Collider> gContact;
        int deckLogs;

        class Grip
        {
            public Aircraft a; public Rigidbody rb; public LandingGear[] gear; public Vector3 comLocal; public float izz, nextCom;
            public float yawDamp = GroundGripMath.YawDamp;   // 1.9.2: per aircraft (MSB 24)
            public bool k; public LandingGear[] castors = new LandingGear[0]; public float[] castorBuilt = new float[0]; public LandingGear tail; public float tailBuilt;   // 1.8.11 (TaxiTurn1811.cs)
            public Collider[] lastCol; public AnimatedPhysicsSurface[] lastAps; public bool deck;   // 1.9.7 (DeckRelative197)
            public bool hold; public Vector3 holdAnchor; public float holdYaw, holdForce;   // 1.9.8 (DeckHold198.cs)
        }
        readonly Dictionary<Aircraft, Grip> grips = new Dictionary<Aircraft, Grip>();
        bool gripBroken, gripLogged;
        static Func<LandingGear, float> gCompression, gDamping;

        static Func<LandingGear, float> Getter(string field)
        {
            var fi = typeof(LandingGear).GetField(field, BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public);
            if (fi == null) return null;
            var p = Expression.Parameter(typeof(LandingGear), "g");
            return Expression.Lambda<Func<LandingGear, float>>(Expression.Field(p, fi), p).Compile();
        }

        // called from the existing 2 s ScanExtras pass for every aircraft (no scan of its own)
        void RegisterGrip(Aircraft a)
        {
            if (gripBroken || a == null || a.definition == null || grips.ContainsKey(a)) return;
            if (!GroundGripMath.IsGripKey(a.definition.jsonKey) && !(GroundGripMath.IsMsbKey(a.definition.jsonKey) && MsbGroundOn)) return;   // 1.9.0: + MSB1780 when MsbGround190 is on
            if (!GroundGripOn) { if (!gripLogged) { gripLogged = true; Logger.LogInfo("1.8.9 ground grip: off (config [Ground] GroundGrip189 = Auto with the build default off, or Off)"); } return; }
            try
            {
                if (gCompression == null) { gCompression = Getter("compressionForce"); gDamping = Getter("dampingForce"); }
                if (gContact == null) gContact = GetterT<Collider>("contactCollider");   // 1.9.7; null = deck mode unavailable (1.9.6 behaviour)
                if (gCompression == null || gDamping == null) { gripBroken = true; Logger.LogWarning("1.8.9 ground grip disabled: LandingGear load fields not found"); return; }
                var gear = new List<LandingGear>(a.GetComponentsInChildren<LandingGear>(true));
                if (a.partLookup != null) foreach (var p in a.partLookup) if (p != null) foreach (var lg in p.GetComponentsInChildren<LandingGear>(true)) if (!gear.Contains(lg)) gear.Add(lg);
                if (a.rb == null || gear.Count == 0) return;                       // not set up yet: next scan
                var g = new Grip { a = a, rb = a.rb, gear = gear.ToArray(), izz = GroundGripMath.IzzFor(a.definition.jsonKey), yawDamp = GroundGripMath.YawDampFor(a.definition.jsonKey) };
                g.comLocal = a.rb.transform.InverseTransformPoint(a.GetCenterOfMass());
                g.lastCol = new Collider[g.gear.Length]; g.lastAps = new AnimatedPhysicsSurface[g.gear.Length];
                grips[a] = g;
                SetupTaxiTurn(g);                                                  // 1.8.11: off -> exactly the 1.8.10 behaviour
                Logger.LogInfo($"1.8.9 ground grip on {a.name} ({a.definition.jsonKey}): {g.gear.Length} gear legs, Izz {g.izz:F0}, mu {GroundGripMath.GripMu}, damper {g.yawDamp}/s");
            }
            catch (Exception e) { gripBroken = true; Logger.LogWarning("1.8.9 ground grip disabled: " + e.Message); }
        }

        void FixedUpdate()
        {
            if (gripBroken || grips.Count == 0) return;
            List<Aircraft> dead = null;
            try
            {
                foreach (var kv in grips)
                {
                    var g = kv.Value; var a = g.a;
                    if (a == null || g.rb == null) { (dead = dead ?? new List<Aircraft>()).Add(kv.Key); continue; }
                    if (a.disabled || !a.LocalSim || g.rb.isKinematic) continue;
                    float N = 0f;
                    foreach (var lg in g.gear)
                        if (lg != null && lg.isActiveAndEnabled) N += Mathf.Max(gCompression(lg) + gDamping(lg), 0f);
                    if (N <= 0f) continue;                                           // no wheel loaded: nothing (air)
                    if (Time.time >= g.nextCom) { g.nextCom = Time.time + 2f; g.comLocal = g.rb.transform.InverseTransformPoint(a.GetCenterOfMass()); }
                    var com = g.rb.transform.TransformPoint(g.comLocal);
                    var fwd = Vector3.ProjectOnPlane(a.transform.forward, Vector3.up);
                    if (fwd.sqrMagnitude < 1e-4f) continue;
                    fwd.Normalize();
                    var right = Vector3.Cross(Vector3.up, fwd);
                    // 1.9.7: the surface under the loaded wheels (contact collider's rigidbody + AnimatedPhysicsSurface, the wheels' own rule)
                    var vSurf = Vector3.zero; float yawSurf = 0f; bool deck = false, onBody = false;
                    if (gContact != null && DeckRelativeOn)
                    {
                        var wv = Vector3.zero; float wy = 0f;
                        for (int i = 0; i < g.gear.Length; i++)
                        {
                            var lg = g.gear[i];
                            if (lg == null || !lg.isActiveAndEnabled) continue;
                            float load = Mathf.Max(gCompression(lg) + gDamping(lg), 0f);
                            if (load <= 0f) continue;
                            var c = gContact(lg);
                            if (c == null) continue;
                            var grb = c.attachedRigidbody;
                            if (grb == null) continue;                               // static ground: v = 0
                            if (!ReferenceEquals(c, g.lastCol[i])) { g.lastCol[i] = c; g.lastAps[i] = c.GetComponent<AnimatedPhysicsSurface>(); }
                            onBody = true;
                            var pv = grb.GetPointVelocity(com);
                            if (g.lastAps[i] != null) pv += g.lastAps[i].GetVelocity();
                            wv += pv * load; wy += grb.angularVelocity.y * load;
                        }
                        if (onBody) { vSurf = DeckMath.SurfaceVelocity(wv, N); yawSurf = wy / N; deck = DeckMath.IsMoving(vSurf.magnitude, yawSurf, g.deck); }
                    }
                    if (deck != g.deck)
                    {
                        g.deck = deck;
                        if (deckLogs < 20) { deckLogs++; Logger.LogInfo($"1.9.7 deck mode {(deck ? "ON" : "off")} on {a.name}: surface velocity {vSurf.magnitude:F1} m/s"); }
                    }
                    // 1.8.11 (TaxiTurn1811): the sideways velocity of the ROOT body's CoM (the fuselage) with mu 1.0, and the scheduled castor / tail locks
                    var vel = (g.k ? g.rb.velocity : g.rb.GetPointVelocity(com)) - vSurf;
                    float f = GroundGripMath.LateralForce(Vector3.Dot(vel, fwd), Vector3.Dot(vel, right), N, g.k ? TaxiTurnMath.GripMuK : GroundGripMath.GripMu);
                    if (g.k) DriveTaxiTurn(g, fwd, vSurf, deck);
                    if (f != 0f) g.rb.AddForceAtPosition(right * f, com);
                    var ci = a.GetInputs();
                    float tq = GroundGripMath.DampTorque(g.izz, g.rb.angularVelocity.y - yawSurf, ci != null ? ci.yaw : 0f, true, g.yawDamp);
                    if (tq != 0f) g.rb.AddTorque(Vector3.up * tq);
                    if (deck || g.hold) DriveDeckHold(g, com, g.rb.GetPointVelocity(com) - vSurf, vSurf, yawSurf, deck, N, ci != null ? ci.throttle : 0f);   // 1.9.8: never called on land
                }
            }
            catch (Exception e) { gripBroken = true; Logger.LogWarning("1.8.9 ground grip disabled: " + e.Message); }
            if (dead != null) foreach (var k in dead) grips.Remove(k);
        }
    }
}
