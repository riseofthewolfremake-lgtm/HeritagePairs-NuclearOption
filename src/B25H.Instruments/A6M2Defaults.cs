// A6M2 r7 (offline worker, 2026-11-18): one switch for the build defaults of the four A6M2 runtime pieces, and the cfg migration for the
// handover build.
//
// Pieces: [A6M2] Dials (A6M2Cockpit.cs), KamikazeFuze (A6M2KamikazeFuze.cs), EventRowHide (A6M2EventRowHide.cs), AiTaxiCap (A6M2AiTaxi.cs).
// Each reads "Auto" as its build default (the project's pattern since 1.8.x: Auto = build default, On, Off; flipping the default turns Auto
// users on - MODLOG 3663, AirBrake1912.cs). The default follows A6M2DefaultsSwitch.On: true in the repo since the 1.9.15 release (until then
// false, and tools/build_instruments_a6m2.sh compiled a scratch copy with it set to true for the handover build). The shared
// tools/build_instruments.sh stays define-free and deterministic (stub rows 1.9.0 / 1.9.9).
//
// Migration (DEFAULTS_ON builds, so 1.9.15 and later): a cfg written while these pieces were being probed can hold an explicit "Off" (test
// restores), and an explicit Off beats the build default. The A6M2 never shipped before 1.9.15, so no player chose Off before it: for a
// player the migration only writes DefaultsVersion (the four keys are new and read Auto). On the first launch of a
// DEFAULTS_ON build the plugin reads [A6M2] DefaultsVersion (missing = 0); if it is below Version, every one of the four keys that holds "Off"
// is reset to "Auto" (= On in this build), and DefaultsVersion is written as Version, so a later deliberate Off is respected. The decision is
// taken once per session (the dials key binds later, on the first scan).
// Only A6M2 files use it. (Until 1.9.15 the A6M2* files were ship-gated out of the public tree; they are public since 1.9.15.)
using BepInEx.Configuration;

namespace B25H.Instruments
{
    public static class A6M2DefaultsMath
    {
        public const bool On = A6M2DefaultsSwitch.On;     // true in the repo since 1.9.15 (A6M2DefaultsSwitch.cs)
        public const int Version = 7;

        /// r7b: the cfg comment follows the build's real default (the r7 handover cfg still said "Auto = build default (off)")
        public const string AutoText = On ? "Auto = build default (ON in this build), On, Off." : "Auto = build default (off in this build), On, Off.";

        /// the value a stale key is migrated to: only an explicit Off in a cfg older than Version, in a DEFAULTS_ON build, becomes Auto
        public static string Migrate(bool defaultsOn, bool staleCfg, string value) => defaultsOn && staleCfg && value == "Off" ? "Auto" : value;
    }

    public partial class Plugin
    {
        static bool a6m2StaleKnown, a6m2StaleCfg;

        /// call right after binding one of the four A6M2 keys
        void A6M2MigrateKey(ConfigEntry<string> e)
        {
            if (e == null) return;
            if (!A6M2DefaultsMath.On) { Config.Save(); return; }   // r7b: default-off build: the comments say "off in this build" too
            if (!a6m2StaleKnown)
            {
                var ver = Config.Bind("A6M2", "DefaultsVersion", 0, "A6M2: version of the A6M2 build defaults this cfg was migrated to (do not edit).");
                a6m2StaleCfg = ver.Value < A6M2DefaultsMath.Version;
                a6m2StaleKnown = true;
                if (a6m2StaleCfg) ver.Value = A6M2DefaultsMath.Version;
            }
            var v = A6M2DefaultsMath.Migrate(true, a6m2StaleCfg, e.Value);
            if (v != e.Value) { Logger.LogInfo($"A6M2 defaults: [{e.Definition.Section}] {e.Definition.Key} Off -> Auto (handover build, cfg older than defaults version {A6M2DefaultsMath.Version})"); e.Value = v; }
            Config.Save();      // r7b: rewrite the cfg so every [A6M2] comment shows this build's default (BepInEx writes descriptions only on a save)
        }
    }
}
