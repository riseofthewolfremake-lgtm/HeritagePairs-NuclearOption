// B25H.Instruments 1.8.11 (offline K, 2026-11-09): taxi turns without the skid, B17G / NIMROD1 / FD32 only.
//
// In game 1.8.10 (study\ingame_1810\ref turn_*_wlog.csv, full rudder, speed held): Mk I 51 / 50 deg/s with 15 / 30 deg of crab at 5 / 10 m/s,
// FD-32 48 / 51 with 15 / 29, B-17G 27 / 44 with 4 / 13 (stock CI-22 46 / 46 with 2 / 2). tools/flightmodel/taildragger_track.py (selftest_k)
// reproduces those within 6 deg/s and 3 deg once the wheels steer on the raw yaw input (LandingGear.controlInputs = aircraft.GetInputs()):
//   * 5 m/s: no tyre saturates; the tail wheel rolls at its full -40 deg lock and the castoring mains sit on their +6 deg lock, so the aircraft
//     pivots about a point ahead of the root body -> crab at the root is geometry;
//   * 10 m/s: the turn the full tail-wheel lock commands needs ~0.9 g; the mains (Mk I / FD-32: 0.8 x 25 % + 0.2 x 75 % of their load) and
//     the 0.6 x N CoM grip saturate -> the aircraft slides;
//   * the 1.8.9 CoM grip acts at the CoM on the CoM velocity: it can not decide where the aircraft pivots.
// 1.8.11, three runtime pieces (taildragger_track.k_kw; constants below = the model's), under config [Ground] TaxiTurn1811:
//   1 the ground grip (GroundGrip189.cs) opposes the sideways velocity of the ROOT body's centre of mass (the fuselage, where the helper's
//     crab is measured) instead of the aircraft CoM's, still applied AT the aircraft CoM (no moment), with GripMuK 1.0 instead of 0.6;
//   2 the castoring mains' range (LandingGear.steeringLock of the legs with steering, steeringSpeed 0, aligningStrength > 0) is speed-
//     scheduled: 25 deg up to 12 m/s, back to the built 6 deg at 20 m/s (before the tail wheel unloads: 22 m/s Mk I / FD-32, 31 m/s B-17G);
//   3 the tail wheel's steering lock (the steering leg with steeringSpeed > 0) = sign x min(built lock, atan(0.9 x L / u)), L = root body CoM
//     -> tail wheel along the heading: the angle that rolls without slip in a 0.9 rad/s turn about the root point.
// Model: crab 2.3 / 3.7 (Mk I), 2.2 / 3.7 (FD-32), 1.0 / 3.1 (B-17G) deg at 5 / 10 m/s with 39-47 deg/s (B-17G 27 / 47); the no-input
// full-throttle roll stays at 0.04-0.11 deg heading / 0.07-0.26 m lateral (90 %), gust heading 1.3-1.7 deg, braking roll-outs < 0.5 deg.
// Writes through compiled setters (no reflection per frame), restores the built locks if the flag is switched off or the aircraft leaves.
using System;
using System.Linq.Expressions;
using System.Reflection;
using UnityEngine;

namespace B25H.Instruments
{
    public static class TaxiTurnMath
    {
        public const float GripMuK = 1.0f, TurnRate = 0.9f;
        public static readonly float[] CastorV = { 0f, 12f, 20f }, CastorDeg = { 25f, 25f, 6f };
        public static float CastorLock(float speed, float built)
        {
            float u = Mathf.Abs(speed);
            float d = u <= CastorV[1] ? CastorDeg[1] : u >= CastorV[2] ? CastorDeg[2] : Mathf.Lerp(CastorDeg[1], CastorDeg[2], (u - CastorV[1]) / (CastorV[2] - CastorV[1]));
            return Mathf.Max(d, Mathf.Abs(built));          // never below the built range
        }
        /// tail-wheel lock (signed like the built lock): the angle that rolls without slip at TurnRate about the root point, capped by the built lock
        public static float TailLock(float speed, float built, float rootToTail)
        {
            float u = Mathf.Max(Mathf.Abs(speed), 0.1f);
            float a = Mathf.Atan(TurnRate * Mathf.Max(rootToTail, 0f) / u) * Mathf.Rad2Deg;
            return Mathf.Sign(built) * Mathf.Min(Mathf.Abs(built), a);
        }
    }

    public partial class Plugin
    {
        const bool TaxiTurnDefault1811 = true;       // 1.8.12: ON (user flew 1.8.11 with it On: taxi, take-off, landing, no veer, no drift)
        BepInEx.Configuration.ConfigEntry<string> taxiTurnMode;
        bool TaxiTurnOn
        {
            get
            {
                if (taxiTurnMode == null) taxiTurnMode = Config.Bind("Ground", "TaxiTurn1811", "Auto", "1.8.11: taxi turns without the skid on the B-17G / Mk I / FD-32 (grip on the fuselage velocity, speed-scheduled main castor and tail-wheel lock). Needs GroundGrip189. Auto = build default, On, Off.");
                var m = taxiTurnMode.Value;
                return m == "On" || (m != "Off" && TaxiTurnDefault1811);
            }
        }

        static Func<LandingGear, float> gLock, gSteerSpeed, gAlign;
        static Func<LandingGear, bool> gSteering;
        static Action<LandingGear, float> sLock;

        static Func<LandingGear, T> GetterT<T>(string field)
        {
            var fi = typeof(LandingGear).GetField(field, BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public);
            if (fi == null || fi.FieldType != typeof(T)) return null;
            var p = Expression.Parameter(typeof(LandingGear), "g");
            return Expression.Lambda<Func<LandingGear, T>>(Expression.Field(p, fi), p).Compile();
        }

        static Action<LandingGear, float> SetterF(string field)
        {
            var fi = typeof(LandingGear).GetField(field, BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public);
            if (fi == null || fi.FieldType != typeof(float)) return null;
            var p = Expression.Parameter(typeof(LandingGear), "g"); var v = Expression.Parameter(typeof(float), "v");
            return Expression.Lambda<Action<LandingGear, float>>(Expression.Assign(Expression.Field(p, fi), v), p, v).Compile();
        }

        /// at RegisterGrip: find the castoring mains and the steered tail wheel, remember their built locks. false = not available (1.8.10 behaviour)
        bool SetupTaxiTurn(Grip g)
        {
            if (!TaxiTurnOn) return false;
            if (gLock == null)
            {
                gLock = GetterT<float>("steeringLock"); gSteerSpeed = GetterT<float>("steeringSpeed"); gAlign = GetterT<float>("aligningStrength");
                gSteering = GetterT<bool>("steering"); sLock = SetterF("steeringLock");
            }
            if (gLock == null || gSteerSpeed == null || gAlign == null || gSteering == null || sLock == null) { Logger.LogWarning("1.8.11 taxi turn disabled: LandingGear steering fields not found"); return false; }
            var castors = new System.Collections.Generic.List<LandingGear>(); var locks = new System.Collections.Generic.List<float>();
            LandingGear tail = null; float tailLock = 0f;
            foreach (var lg in g.gear)
            {
                if (lg == null || !gSteering(lg)) continue;
                if (gSteerSpeed(lg) == 0f && gAlign(lg) > 0f) { castors.Add(lg); locks.Add(gLock(lg)); }
                else if (gSteerSpeed(lg) > 0f && tail == null) { tail = lg; tailLock = gLock(lg); }
            }
            g.castors = castors.ToArray(); g.castorBuilt = locks.ToArray(); g.tail = tail; g.tailBuilt = tailLock; g.k = true;
            Logger.LogInfo($"1.8.11 taxi turn on {g.a.name}: {g.castors.Length} castoring mains (built lock {(locks.Count > 0 ? locks[0] : 0f):F1}), tail wheel {(tail != null ? tail.name + " lock " + tailLock.ToString("F1") : "none")}, grip mu {TaxiTurnMath.GripMuK} on the root-body velocity");
            return true;
        }

        /// per FixedUpdate (from GroundGrip189.FixedUpdate) while the aircraft is on its wheels: write the scheduled locks
        static void DriveTaxiTurn(Grip g, Vector3 fwd, Vector3 vSurf, bool deck)
        {
            float u = Vector3.Dot(g.rb.velocity - vSurf, fwd);   // 1.9.7: relative to the surface under the wheels (vSurf = 0 on land)
            for (int i = 0; i < g.castors.Length; i++)
                if (g.castors[i] != null) sLock(g.castors[i], deck ? DeckMath.CastorLockDeck(u, g.castorBuilt[i]) : TaxiTurnMath.CastorLock(u, g.castorBuilt[i]));
            if (g.tail != null)
            {
                float L = Vector3.Dot(g.rb.worldCenterOfMass - g.tail.transform.position, fwd);
                sLock(g.tail, TaxiTurnMath.TailLock(u, g.tailBuilt, L));
            }
        }

        static void RestoreTaxiTurn(Grip g)
        {
            if (g == null || !g.k || sLock == null) return;
            for (int i = 0; i < g.castors.Length; i++) if (g.castors[i] != null) sLock(g.castors[i], g.castorBuilt[i]);
            if (g.tail != null) sLock(g.tail, g.tailBuilt);
        }
    }
}
