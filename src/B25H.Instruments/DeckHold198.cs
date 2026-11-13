// 1.9.8 DeckHold198: parking hold on a MOVING surface (carrier deck, lift) for the aircraft on the taildragger ground stack.
//
// Measured in game on 1.9.7 (study\ingame_197, MODLOG 2026-11-13): parked with no input on a 15 m/s carrier the FD-32 rolls straight backwards
// along its own axis at 0.29 m/s and the Mk I 0.37 m/s on the lift spot, while a stock CI-22 moves 0.01 m. The stock parking brake IS set
// (LandingGear.brakeStrength reads 1.00 on our mains and on the CI-22's), the castors read 0.0 deg, the throttle 0.00, and the FD-32 creeps the
// same with our grip switched off. What differs: the ship carries the aircraft through still air at 15 m/s, a tail-down biplane makes lift
// and drag in that airflow (wheel loads sum to 57 % of the weight on the FD-32, 76 % on the Mk I), and only the "_leg" half of each of our
// main legs is braked: it carries 25 % of the main load (the "_grip" half 75 %, brake 0, friction 0.20). The braked share cannot hold the drag.
//
// Fix (deck mode only, so land is untouched): while the throttle is under the stock parking-brake threshold (0.1) and the aircraft moves
// slower than 2 m/s over the deck, hold it where it stands: a spring-damper at the CoM towards an anchor that rides with the surface
// (advanced every step by the surface velocity DeckRelative197 already computes), capped at the friction an all-wheels-braked aircraft
// would have (HoldMu x the wheel load), plus the same for the heading. Throttle >= 0.1 releases it at once, like the stock brake.
// Config [Ground] DeckHold198 (Auto = on). Any exception switches this piece off and leaves the rest of the stack running.
// Pure laws in DeckHoldMath (mirrored in tools/flightmodel/deckhold198.py).
using System;
using UnityEngine;

namespace B25H.Instruments
{
    public static class DeckHoldMath
    {
        public const float ThrottleMax = 0.1f;   // the stock parking-brake threshold (LandingGear: throttle < 0.1)
        public const float EngageSpeed = 2f;     // stock: speed < 1 m/s. Here 2 m/s over the deck: the stock brake is off during a lift ride (its speed test sees the lift moving) and the FD-32 rolled at 1.5-1.9 m/s there
        public const float BreakDist = 1.5f;     // pushed further than this from the anchor: let go and re-anchor (a collision, a tow)
        public const float Omega = 6f;           // rad/s, position spring (critically damped)
        public const float OmegaYaw = 3f;        // rad/s, heading spring
        public const float HoldMu = 0.8f;        // cap = HoldMu x wheel load: every wheel braked on a dry deck (stock tyre friction 0.8-0.85)
        public const float YawArm = 2f;          // m, cap of the heading torque = HoldMu x load x YawArm

        public static bool Engage(bool deck, float throttle, float relSpeed) => deck && throttle < ThrottleMax && relSpeed < EngageSpeed;
        public static bool Release(bool deck, float throttle, float dist) => !deck || throttle >= ThrottleMax || dist > BreakDist;
        /// horizontal hold force (N) for an offset d (m, anchor -> aircraft) and a deck-relative velocity v (m/s); mass = load / g
        public static Vector3 Force(Vector3 d, Vector3 v, float load)
        {
            float m = load / 9.81f;
            var f = -(Omega * Omega * d + 2f * Omega * v) * m;
            f.y = 0f;
            return Vector3.ClampMagnitude(f, HoldMu * load);
        }
        /// heading hold torque (N m) for a heading error (rad) and a relative yaw rate (rad/s)
        public static float Torque(float izz, float err, float rate, float load)
        {
            float cap = HoldMu * load * YawArm;
            return Mathf.Clamp(-(OmegaYaw * OmegaYaw * err + 2f * OmegaYaw * rate) * izz, -cap, cap);
        }
    }

    public partial class Plugin
    {
        const bool DeckHoldDefault198 = true;
        BepInEx.Configuration.ConfigEntry<string> deckHoldMode;
        bool deckHoldBroken; int deckHoldLogs;
        bool DeckHoldOn
        {
            get
            {
                if (deckHoldMode == null) deckHoldMode = Config.Bind("Ground", "DeckHold198", "Auto", "1.9.8: on a moving carrier deck or lift, hold the parked Mk I / FD-32 / B-17G / MSB in place while the throttle is at idle (the airflow over the moving deck pushed them backwards at 0.3 m/s); throttle up releases it like the stock parking brake. No effect on land. Auto = build default (on), On, Off.");
                var m = deckHoldMode.Value;
                return m == "On" || (m != "Off" && DeckHoldDefault198);
            }
        }

        /// one call per FixedUpdate per registered aircraft, from the ground stack, after the grip / damper. relVel = CoM velocity minus the surface's.
        void DriveDeckHold(Grip g, Vector3 com, Vector3 relVel, Vector3 vSurf, float yawSurf, bool deck, float load, float throttle)
        {
            if (deckHoldBroken) return;
            try
            {
                if (!g.hold)
                {
                    if (!deck || !DeckHoldOn) return;
                    relVel.y = 0f;
                    if (!DeckHoldMath.Engage(deck, throttle, relVel.magnitude)) return;
                    g.hold = true; g.holdAnchor = com; g.holdYaw = g.rb.rotation.eulerAngles.y;
                    if (deckHoldLogs < 20) { deckHoldLogs++; Logger.LogInfo($"1.9.8 deck hold ON on {g.a.name}: {relVel.magnitude:F2} m/s over the deck, wheel load {load:F0} N"); }
                    return;
                }
                // the anchor rides with the surface
                var vs = vSurf; vs.y = 0f;
                g.holdAnchor += vs * Time.fixedDeltaTime;
                g.holdYaw += yawSurf * Mathf.Rad2Deg * Time.fixedDeltaTime;
                var d = com - g.holdAnchor; d.y = 0f;
                if (DeckHoldMath.Release(deck, throttle, d.magnitude) || !DeckHoldOn)
                {
                    g.hold = false;
                    if (deckHoldLogs < 20) { deckHoldLogs++; Logger.LogInfo($"1.9.8 deck hold off on {g.a.name}: throttle {throttle:F2}, offset {d.magnitude:F2} m, deck {deck}"); }
                    return;
                }
                relVel.y = 0f;
                var f = DeckHoldMath.Force(d, relVel, load);
                if (f.sqrMagnitude > 0f) g.rb.AddForceAtPosition(f, com);
                float err = Mathf.DeltaAngle(g.holdYaw, g.rb.rotation.eulerAngles.y) * Mathf.Deg2Rad;
                float tq = DeckHoldMath.Torque(g.izz, err, g.rb.angularVelocity.y - yawSurf, load);
                if (tq != 0f) g.rb.AddTorque(Vector3.up * tq);
                g.holdForce = f.magnitude;
            }
            catch (Exception e) { deckHoldBroken = true; g.hold = false; Logger.LogWarning("1.9.8 deck hold disabled: " + e.Message); }
        }
    }
}
