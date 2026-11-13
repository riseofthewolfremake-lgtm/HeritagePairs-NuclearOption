// Heritage Pairs 1.8.0: split main wheel (side grip without more braking), shared by NimrodBuild, FD32Build and B17GBuild.
//
// User report on 1.7.13: the Nimrod Mk I, FD-32 and B-17G "keep spinning out on runways"; their mains ran frictionCoef 0.20 / 0.22
// (the nose-over fix), the stock 0.8 tips them over under brakes. LandingGear (0.34.6) has ONE friction for everything: side force and
// braking are both capped by load x frictionCoef (LandingGear.cs 627-656). An UNBRAKED LandingGear never brakes (braked = false,
// differentialBrakeFactor 0 -> brakeStrength stays 0; its < 1 m/s contact patch holds forward with only 0.05 of its friction).
// So each main wheel gets a second, unbraked LandingGear on the same contact point ("grip"): both run the stock frictionCoef 0.8; the
// braked one carries brakeShare of the spring (and so of the load), the grip one the rest. Braking / brake hold = 0.8 x brakeShare x load
// (unchanged from 1.7.13), side grip = 0.8 x load (stock). Suspension: the two springs act at the same cast point, so their sum is the
// original spring. Grass: drag ~ (load / contactArea)^4 per gear, so contactArea x share^0.75 keeps each gear's drag / spring ratio and the
// total drag the same (tools/flightmodel/groundcom.py).
// The grip gear has its own dummy hinge / unsprung / wheel (nothing visible), muted tyre sounds, no fold / latch / break sounds; the visible
// wheel, leg, dust and fold stay on the braked gear. If the grip gear breaks it throws away only its own dummy hinge.
//
// Heritage Pairs 1.8.8: castoring mains (Castor / VerifyCastor below). User on 1.8.7: line up, full throttle, no input -> the B-17G /
// Mk I / FD-32 veer left or right after ~100 m; the stock CI-22 / A-19 and our B-25H / GA-25X do not. Cause (tools/flightmodel/
// taildragger_track.py): LandingGear's side force (627-656) on a gripping wheel AHEAD of the CoM turns yaw into more yaw; stock tricycles
// keep their gripping mains BEHIND the CoM and let the light wheel in front castor (steering + aligningStrength 5, LandingGear 602-606).
// Ours have the mains ahead of the CoM, and once the tail wheel's load is gone (aerodynamic pitch-down moment: B-17G 0 kN from 30.8 m/s)
// nothing behind the CoM holds them. Fix = the stock arrangement mirrored: the braked main LandingGear castors (steering true,
// aligningStrength 5, steeringSpeed 0, |steeringLock| = the castoring range), the tail wheel stays locked. LandingGear turns `unsprung`
// (= our `axle`) by its steeringAngle and every slip / side-force term reads `axle`; the grip partner copies the same `axle` reference
// (CopySerialized), so both legs of a wheel follow the one castor. steeringSpeed must be 0: any self-centring servo snaps the castor back
// for slips below speed x dt per step and the wheel grips again (B-17G no-input 90 % heading 0.09 -> 1.27 deg with 2 deg/s in the model).
using System;
using System.Collections.Generic;
using System.Reflection;
using UnityEditor;
using UnityEngine;

namespace B25HTools
{
    public static class GripGear
    {
        static FieldInfo Fld(Type t, string n)
        {
            for (var tt = t; tt != null; tt = tt.BaseType)
            {
                var f = tt.GetField(n, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
                if (f != null) return f;
            }
            throw new Exception("GripGear: no field " + n + " on " + t.Name);
        }
        static void S(object o, string n, object v) => Fld(o.GetType(), n).SetValue(o, v);
        static object G(object o, string n) => Fld(o.GetType(), n).GetValue(o);

        public const string Suffix = "_grip";

        /// <summary>Split a braked main LandingGear: frictionCoef on both, brakeShare of spring / damping / (area^0.75) on the braked one.</summary>
        public static LandingGear Add(LandingGear main, float brakeShare, float friction, Action<string> log) => Add(main, brakeShare, friction, friction, -1f, -1f, log);

        /// <summary>1.8.1: separate frictions and rolling resistances. gripFriction = the unbraked leg's frictionCoef (side grip only);
        /// brakedRolling / gripRolling &lt; 0 keep the template value. The braked leg's rolling resistance is absorbed under its own friction
        /// cap when braking (sum clamped to N x frictionCoef), the grip leg's is not: 1.8.0's 0.05 on the grip legs added 0.0375 x load of
        /// deceleration to full braking and the Mk I flipped (tools/flightmodel/taildragger_ground.py).</summary>
        public static LandingGear Add(LandingGear main, float brakeShare, float friction, float gripFriction, float brakedRolling, float gripRolling, Action<string> log)
        {
            var go = main.gameObject;
            var part = (Component)G(main, "attachedPart");
            // on the part, not under the leg: if the visible leg breaks off and is destroyed 20 s later nothing of the grip gear goes with it
            var gripGO = new GameObject(go.name + Suffix);
            gripGO.layer = go.layer;
            gripGO.transform.SetParent(part.transform, false);
            gripGO.transform.SetPositionAndRotation(go.transform.position, go.transform.rotation);
            var hinge = new GameObject(go.name + Suffix + "_hinge"); hinge.layer = go.layer; hinge.transform.SetParent(gripGO.transform, false);
            var uns = new GameObject(go.name + Suffix + "_unsprung"); uns.layer = go.layer; uns.transform.SetParent(hinge.transform, false);
            var whl = new GameObject(go.name + Suffix + "_wheel"); whl.layer = go.layer; whl.transform.SetParent(uns.transform, false);
            var box = hinge.AddComponent<BoxCollider>(); box.size = Vector3.one * 0.05f; box.isTrigger = true; box.enabled = false;

            var grip = gripGO.AddComponent<LandingGear>();
            EditorUtility.CopySerialized(main, grip);
            AudioSource Mute(AudioSource src)
            {
                var a = gripGO.AddComponent<AudioSource>();
                if (src != null) EditorUtility.CopySerialized(src, a);
                a.mute = true; a.playOnAwake = false;
                return a;
            }
            S(grip, "tireNoiseSound", Mute((AudioSource)G(main, "tireNoiseSound")));
            S(grip, "tireSkidSound", Mute((AudioSource)G(main, "tireSkidSound")));
            var mcast = (Transform)G(main, "castPoint");
            if (mcast == null) mcast = ((GameObject)G(main, "bumpStop")).transform;
            // same contact point as the braked gear (extended); fixed to the part (it only casts while its own dummy hinge is unfolded)
            var castGO = new GameObject(go.name + Suffix + "_cast"); castGO.layer = go.layer; castGO.transform.SetParent(gripGO.transform, false);
            castGO.transform.SetPositionAndRotation(mcast.position, mcast.rotation);
            var cast = castGO.transform;
            S(grip, "castPoint", cast);
            S(grip, "unsprung", uns);
            S(grip, "wheels", new[] { whl.transform });
            S(grip, "gearHinge", hinge.transform);
            S(grip, "hingeFoldMotion", Vector3.zero);
            S(grip, "strutRotationTransform", null); S(grip, "strutRotation", 0f);
            S(grip, "gearCollider", box);
            S(grip, "joints", Array.CreateInstance(Fld(typeof(LandingGear), "joints").FieldType.GetElementType(), 0));
            S(grip, "movingParts", Array.CreateInstance(Fld(typeof(LandingGear), "movingParts").FieldType.GetElementType(), 0));
            S(grip, "gearDoors", new List<LandingGear.GearDoor>());
            S(grip, "foldSound", null); S(grip, "latchSound", null); S(grip, "breakSound", null);
            S(grip, "braked", false); S(grip, "steering", false); S(grip, "steeringLock", 0f); S(grip, "differentialBrakeFactor", 0f);
            S(grip, "mass", 1f);

            float k = (float)G(main, "springRate"), c = (float)G(main, "dampingRate"), area = (float)G(main, "contactArea");
            float sb = brakeShare, sg = 1f - brakeShare;
            S(main, "springRate", k * sb); S(main, "dampingRate", c * sb); S(main, "contactArea", area * Mathf.Pow(sb, 0.75f));
            S(grip, "springRate", k * sg); S(grip, "dampingRate", c * sg); S(grip, "contactArea", area * Mathf.Pow(sg, 0.75f));
            S(main, "frictionCoef", friction); S(grip, "frictionCoef", gripFriction);
            S(main, "response", 1f); S(grip, "response", 1f);
            if (brakedRolling >= 0f) S(main, "rollingResistance", brakedRolling);
            if (gripRolling >= 0f) S(grip, "rollingResistance", gripRolling);
            log?.Invoke($"grip gear {gripGO.name}: friction braked {friction} / grip {gripFriction}, braked share {sb} (braking {friction * sb:F3} x load, side {friction * sb + gripFriction * sg:F2} x load), rolling {G(main, "rollingResistance")} / {G(grip, "rollingResistance")}, " +
                $"k {k} -> {k * sb} + {k * sg}, c {c} -> {c * sb} + {c * sg}, contactArea {area} -> {area * Mathf.Pow(sb, 0.75f):F4} + {area * Mathf.Pow(sg, 0.75f):F4}, cast {cast.name}");
            return grip;
        }

        /// <summary>1.8.8: make a braked main LandingGear castor (see the header): steering, aligningStrength align, steeringSpeed 0,
        /// steeringLock +range (the sign only matters with a servo; + = the sense of a wheel ahead of the CoM). Its unsprung must sit at the
        /// identity local rotation (LandingGear writes unsprung.localEulerAngles = (0, steeringAngle, 0) every step).</summary>
        public static void Castor(LandingGear main, float range, float align, Action<string> log)
        {
            if (!(bool)G(main, "braked")) throw new Exception("GripGear.Castor: " + main.name + " is not a braked main");
            var uns = (GameObject)G(main, "unsprung");
            if (Quaternion.Angle(uns.transform.localRotation, Quaternion.identity) > 0.01f) throw new Exception("GripGear.Castor: " + main.name + " unsprung local rotation is not identity");
            S(main, "steering", true); S(main, "steeringLock", Mathf.Abs(range)); S(main, "steeringSpeed", 0f); S(main, "aligningStrength", align);
            log?.Invoke($"castor {main.name}: steering, aligningStrength {align}, steeringSpeed 0, range +-{Mathf.Abs(range)} deg (axle {((Transform)G(main, "axle")).name})");
        }

        /// <summary>1.8.8 check row helper: both braked mains castor with the agreed numbers on an identity-rotated unsprung that IS their axle,
        /// the grip partners read that axle and do not steer, and the only other steering gear is a locked-sense tail wheel (lock &lt; 0).</summary>
        public static bool VerifyCastor(GameObject inst, float range, float align, out string detail)
        {
            var lgs = inst.GetComponentsInChildren<LandingGear>(true);
            var parts = new List<string>(); bool ok = true; int n = 0;
            foreach (var m in lgs)
            {
                if (!(bool)G(m, "braked")) continue;
                n++;
                var uns = ((GameObject)G(m, "unsprung")).transform; var ax = (Transform)G(m, "axle");
                LandingGear g = null;
                foreach (var x in lgs) if (x.gameObject.name == m.gameObject.name + Suffix) g = x;
                bool row = (bool)G(m, "steering") && Mathf.Abs((float)G(m, "steeringLock") - Mathf.Abs(range)) < 1e-4f && (float)G(m, "steeringSpeed") == 0f
                    && Mathf.Abs((float)G(m, "aligningStrength") - align) < 1e-4f && ax == uns && Quaternion.Angle(uns.localRotation, Quaternion.identity) < 0.01f
                    && (g == null || ((Transform)G(g, "axle") == ax && !(bool)G(g, "steering")));
                ok &= row;
                parts.Add($"{m.name}: steering {G(m, "steering")} lock {G(m, "steeringLock")} speed {G(m, "steeringSpeed")} align {G(m, "aligningStrength")} axle {(ax == uns ? "= unsprung" : "OTHER")}{(g != null ? $", grip partner {(((Transform)G(g, "axle")) == ax ? "same axle" : "OTHER axle")} steering {G(g, "steering")}" : "")} {(row ? "ok" : "BAD")}");
            }
            var others = new List<LandingGear>();
            foreach (var x in lgs) if ((bool)G(x, "steering") && !(bool)G(x, "braked")) others.Add(x);
            bool tailOk = others.Count == 1 && (float)G(others[0], "steeringLock") < 0f;
            detail = $"{n} braked mains; " + string.Join("; ", parts) + $"; other steering gear: {string.Join(", ", others.ConvertAll(o => o.name + " lock " + G(o, "steeringLock")))}";
            return ok && n == 2 && tailOk;
        }

        /// <summary>Check row helper: every braked main has exactly one unbraked grip partner on the same cast point with the agreed numbers.</summary>
        public static bool Verify(GameObject inst, float brakeShare, float friction, float springK, out string detail) => Verify(inst, brakeShare, friction, friction, -1f, -1f, springK, out detail);

        public static bool Verify(GameObject inst, float brakeShare, float friction, float gripFriction, float brakedRolling, float gripRolling, float springK, out string detail)
        {
            var lgs = inst.GetComponentsInChildren<LandingGear>(true);
            var parts = new List<string>(); bool ok = true; int n = 0;
            foreach (var m in lgs)
            {
                if (!(bool)G(m, "braked")) continue;
                n++;
                LandingGear g = null;
                foreach (var x in lgs) if (x.gameObject.name == m.gameObject.name + Suffix) g = x;
                if (g == null) { ok = false; parts.Add(m.name + ": no grip gear"); continue; }
                float km = (float)G(m, "springRate"), kg = (float)G(g, "springRate");
                bool row = !(bool)G(g, "braked") && !(bool)G(g, "steering") && (float)G(g, "differentialBrakeFactor") == 0f
                    && Mathf.Abs((float)G(m, "frictionCoef") - friction) < 1e-4f && Mathf.Abs((float)G(g, "frictionCoef") - gripFriction) < 1e-4f
                    && (brakedRolling < 0f || Mathf.Abs((float)G(m, "rollingResistance") - brakedRolling) < 1e-4f) && (gripRolling < 0f || Mathf.Abs((float)G(g, "rollingResistance") - gripRolling) < 1e-4f)
                    && Mathf.Abs(km + kg - springK) < 1f && Mathf.Abs(km / springK - brakeShare) < 1e-3f
                    && Vector3.Distance(((Transform)G(g, "castPoint")).position, ((Transform)G(m, "castPoint") ?? ((GameObject)G(m, "bumpStop")).transform).position) < 1e-4f
                    && Vector3.Angle(((Transform)G(g, "castPoint")).up, ((Transform)G(m, "castPoint") ?? ((GameObject)G(m, "bumpStop")).transform).up) < 0.01f
                    && (Component)G(g, "attachedPart") == (Component)G(m, "attachedPart") && g.transform.parent == ((Component)G(m, "attachedPart")).transform
                    && (Transform)G(g, "axle") == (Transform)G(m, "axle")
                    && Mathf.Abs((float)G(g, "maxCompression") - (float)G(m, "maxCompression")) < 1e-5f
                    && ((AudioSource)G(g, "tireNoiseSound")).mute && ((AudioSource)G(g, "tireSkidSound")).mute
                    && (Transform)G(g, "gearHinge") != (Transform)G(m, "gearHinge") && (GameObject)G(g, "unsprung") != (GameObject)G(m, "unsprung");
                ok &= row;
                parts.Add($"{m.name}: friction {G(m, "frictionCoef")}/{G(g, "frictionCoef")} rolling {G(m, "rollingResistance")}/{G(g, "rollingResistance")} k {km}+{kg} braking {(float)G(m, "frictionCoef") * km / springK:F3} {(row ? "ok" : "BAD")}");
            }
            detail = $"{n} braked mains; " + string.Join("; ", parts);
            return ok && n == 2;
        }
    }
}
