// A6M2 r7: the build switch for the A6M2 runtime-piece defaults (A6M2Defaults.cs). 1.9.15 (A6M2 released, user approval 2026-11-27): true in
// the repo, so the plain tools/build_instruments.sh build is the handover build the user tested (until 1.9.15 it was false here and
// tools/build_instruments_a6m2.sh wrote true into a scratch copy with HP_A6M2_DEFAULTS_ON=1).
namespace B25H.Instruments
{
    public static class A6M2DefaultsSwitch
    {
        public const bool On = true;
    }
}
