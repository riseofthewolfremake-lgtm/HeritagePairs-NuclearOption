// B25H.Instruments 1.5.3: FD-32 tac-page panel sources (jsonKey FD32 only). NIMROD1 / GA25X / B25H paths are not touched.
//
// Why (docs/fd32_design.md 20, in-game 1.5.2 test): the FD-32 cockpit shows the stock CI-22 tac page (Cockpit.tacScreenUIPrefab =
// tacScreen_cricket). Its side panels find their data source by GameObject NAME among the aircraft's parts: PropGauge.sourceName
// "propHub" (tacScreen_cricket.prefab:3357), EngineTelemetry.engineName "COIN" (:3986) and "propHub" (:4914). The FD-32's prop part is
// "prop" and its TurbineEngine sits on "fus_engine", so no source is found: PropGauge.Refresh returns early (static "96% 2.5° 1.2mw")
// and EngineTelemetry.Update disables itself (static 46 / 46 / 46 / 46).
// Fix: every 2 s, for the FD-32 only, give each unbound panel its FD-32 source by reflection on the panels' own fields:
//   PropGauge.source                     <- the FD-32's ConstantSpeedProp
//   EngineTelemetry ("COIN")  .engineInterface <- the FD-32's TurbineEngine (NOT the boost Turbojet on the same part)
//   EngineTelemetry ("propHub").engineInterface <- the FD-32's ConstantSpeedProp
//   + displayPower / displayPitch as EngineTelemetry.Start sets them, and the component re-enabled.
// Bound panels and other aircraft are left alone. Any exception disables this for the session (the panels stay static, nothing else changes).
using System.Collections.Generic;
using System.Reflection;
using UnityEngine;

namespace B25H.Instruments
{
    public partial class Plugin
    {
        public const string TacKeyFD32 = "FD32";
        public static bool IsTacFixKey(string k) => k == TacKeyFD32 || k == BoostJsonKey;   // 1.8.4: + GA25X (prop_L / engine_L: the same unbound panels, "96% 2.5 deg 1.2mw")
        // 1.9.0: the MSB-17/80's stock tac pages carry the same unbound engine / power panels (parts engine_n / prop_n): bound to engine 1 and
        // its front prop row, gas-generator speed on the turbine panel (Dials184 Ng). [Dials] MsbTac190, off by default until the live probe.
        public const string MsbTacKey = "MSB17";   // 1.9.9: was "MSB1780"
        const bool MsbTacDefault190 = true;      // 1.9.2: ON by default (the 1.9.0 live log showed the binding working, on engine_2: now engine 1)
        BepInEx.Configuration.ConfigEntry<string> msbTacMode;
        bool MsbTacOn
        {
            get
            {
                if (msbTacMode == null) msbTacMode = Config.Bind("Dials", "MsbTac190", "Auto", "1.9.0: bind the MSB-17 tac-page engine / power panels to engine 1 (gas-generator speed). Auto = build default (off until the live probe passes), On, Off.");
                var m = msbTacMode.Value;
                return m == "On" || (m != "Off" && MsbTacDefault190);
            }
        }
        public static string EngineRoleFor(string engineName) => engineName == "COIN" ? "turbine" : engineName == "propHub" ? "prop" : null;

        bool fd32TacBroken;
        readonly HashSet<Object> fd32TacBound = new HashSet<Object>();

        // 1.9.2: the MSB's engine 1 / its FRONT prop row by part name (GetComponentInChildren found engine_2 first: wing_inner_L comes before
        // wing_mid_L in the hierarchy); the component on the named object itself (the aft row lives on a child), else the first found
        public static string MsbPanelPart(string role) => role == "turbine" ? "engine_1" : role == "prop" ? "prop_1" : null;
        static T MsbEngine1<T>(Aircraft a, string part) where T : Component
        {
            if (a.partLookup != null)
                foreach (var p in a.partLookup)
                    if (p != null && p.name == part) { var c = p.GetComponent<T>(); if (c != null) return c; }
            return FindOnAircraft<T>(a);
        }

        static Aircraft FieldAircraft(object o) => o.GetType().GetField("aircraft", BFI)?.GetValue(o) as Aircraft;

        static T FindOnAircraft<T>(Aircraft a) where T : Component
        {
            var c = a.GetComponentInChildren<T>(true);
            if (c != null) return c;
            if (a.partLookup != null)
                foreach (var p in a.partLookup)
                    if (p != null && (c = p.GetComponentInChildren<T>(true)) != null) return c;
            return null;
        }

        void FD32TacPanels()
        {
            if (fd32TacBroken) return;
            try
            {
                fd32TacBound.RemoveWhere(o => o == null);
                foreach (var g in PropGauges())
                {
                    if (g == null || fd32TacBound.Contains(g)) continue;
                    var a = FieldAircraft(g);
                    if (a == null || a.definition == null) continue;               // not initialised yet: retry next scan
                    fd32TacBound.Add(g);
                    if (!IsTacFixKey(a.definition.jsonKey) && !(a.definition.jsonKey == MsbTacKey && MsbTacOn)) continue;
                    var f = typeof(PropGauge).GetField("source", BFI);
                    if (f == null || f.GetValue(g) as Object != null) continue;    // already bound (stock name matched)
                    var prop = a.definition.jsonKey == MsbTacKey ? MsbEngine1<ConstantSpeedProp>(a, "prop_1") : FindOnAircraft<ConstantSpeedProp>(a);
                    if (prop == null) continue;
                    f.SetValue(g, prop);
                    Logger.LogInfo($"{a.definition.jsonKey} tac page: power panel (PropGauge) bound to {prop.name}");
                }
                foreach (var t in Telemetries())
                {
                    if (t == null || fd32TacBound.Contains(t)) continue;
                    var a = FieldAircraft(t);
                    if (a == null || a.definition == null) continue;
                    fd32TacBound.Add(t);
                    if (!IsTacFixKey(a.definition.jsonKey) && !(a.definition.jsonKey == MsbTacKey && MsbTacOn)) continue;
                    var ty = typeof(EngineTelemetry);
                    var fe = ty.GetField("engineInterface", BFI);
                    if (fe == null || fe.GetValue(t) as Object != null) continue;
                    var role = EngineRoleFor(ty.GetField("engineName", BFI)?.GetValue(t) as string);
                    bool msb = a.definition.jsonKey == MsbTacKey;
                    IEngine eng = role == "turbine" ? (IEngine)(msb ? MsbEngine1<TurbineEngine>(a, "engine_1") : FindOnAircraft<TurbineEngine>(a)) : role == "prop" ? (msb ? MsbEngine1<ConstantSpeedProp>(a, "prop_1") : FindOnAircraft<ConstantSpeedProp>(a)) : null;
                    if (eng == null) continue;
                    fe.SetValue(t, eng);
                    ty.GetField("displayPower", BFI)?.SetValue(t, eng is IPowerSource);
                    ty.GetField("displayPitch", BFI)?.SetValue(t, eng is IPitchTelemetry);
                    if (ty.GetField("controlInputs", BFI)?.GetValue(t) == null) ty.GetField("controlInputs", BFI)?.SetValue(t, a.GetInputs());
                    t.enabled = true;
                    Logger.LogInfo($"{a.definition.jsonKey} tac page: engine panel ({role}) bound to {(eng as Component)?.name}");
                    if (role == "turbine" && (IsNgKey(a.definition.jsonKey) || a.definition.jsonKey == MsbTacKey)) RegisterNg(t, eng as TurbineEngine, a);   // 1.8.4 (+ MSB1780 1.9.0, only reached with MsbTac190 on)
                }
            }
            catch (System.Exception e) { fd32TacBroken = true; Logger.LogWarning("FD-32 tac panels disabled: " + e.Message); }
        }
    }
}
