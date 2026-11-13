// Heritage Pairs 1.8.3 (offline worker B): prefab dumps of the Mk I / FD-32 after the 1.8.3 build and the PhysX ground replica, for the
// "ground values unchanged" comparison with 1.8.2 (dump_*_after182.txt, ground_physx.txt of 1.8.2 copied aside first).
//   unity.sh - <log> -executeMethod B25HTools.R183Offline.DumpAndGround
using System.IO;
using UnityEngine;

namespace B25HTools
{
    public static class R183Offline
    {
        const string Logs = @"C:\Users\User\nuclearoption-ref\unitylogs";

        public static void DumpAndGround()
        {
            foreach (var n in new[] { "nimrod", "fd32" })
                FamilyBuild.Dump(FamilyBuild.FamilyRoot + "/" + n, Path.Combine(Logs, $"dump_{n}_after183b.txt"));
            var gp = Path.Combine(Logs, "ground_physx.txt");
            var keep = Path.Combine(Logs, "ground_physx_182.txt");
            if (File.Exists(gp) && !File.Exists(keep)) File.Copy(gp, keep);
            GroundPhysX.All();
            if (File.Exists(gp)) File.Copy(gp, Path.Combine(Logs, "ground_physx_183b.txt"), true);
            Debug.Log("[R183] dumps + ground replica written");
        }
    }
}
