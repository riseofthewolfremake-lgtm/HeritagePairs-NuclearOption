// A6M2 1.9.15 (bug 4 of 2026-11-26): the Type 97 No.6 60 kg bomb (A6M2_no6) in BombArmor1915: thin-cased like the Cooper, so a laser or an
// interceptor blast can destroy it (as a stock PAB-125 clone it had fire armour 3.5 / tolerance 0.3 / blast armour 150). The tokko charge is
// Event Content and detonates at once: not listed.
// SHIP GATE: file name starts with A6M2 (make_public_tree leaves it out); called through the partial method declared in BombArmor1915.cs.
using UnityEngine;

namespace B25H.Instruments
{
    public static class A6M2BombArmorMath
    {
        public const string No6Key = "A6M2_no6";
        public const float No6Fire = 1.0f, No6FireTol = 0.2f, No6Blast = 60f;
    }

    public partial class Plugin
    {
        partial void RegisterDevBombArmor1915()
        {
            bombArmor1915[A6M2BombArmorMath.No6Key] = new Vector3(A6M2BombArmorMath.No6Fire, A6M2BombArmorMath.No6FireTol, A6M2BombArmorMath.No6Blast);
        }
    }
}
