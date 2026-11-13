// 1.8.9 (offline J, part 3; docs/damage_model_study.md): check helper for the skin damage HOLE maps of the B-17G, Nimrod Mk I and FD-32.
// The game's AircraftSkin shader discards a skin pixel when the _BasecolorDmg alpha is below 0.52 - 0.02 / D (D = 1 - HitPoints / 100):
// HP 90 -> 0.32, 80 -> 0.42, 50 -> 0.48, 0 -> 0.50. Coverage = fraction of the SKIN texels (alpha != the 0.62 fill outside the UV islands)
// below the threshold, read from the repo PNG (the file the build imports). Bands (stock CI-22 / A-19 / FastBomber1 / EW-25 and our B-25H,
// study section 3): HP 80 5-13 %, HP 50 10-27 %, HP 0 15-30 %. The imported texture must keep an alpha channel (else no hole can open).
using System.IO;
using UnityEngine;

namespace B25HTools
{
    public static class DamageHoles189
    {
        public static readonly float[] Thresh = { 0.42f, 0.48f, 0.50f };          // HP 80 / 50 / 0
        public static readonly float[] Lo = { 0.05f, 0.10f, 0.15f }, Hi = { 0.13f, 0.27f, 0.30f };

        /// -> (ok, detail): skin coverage at HP 80 / 50 / 0 inside the bands, the 1.8.0 flat 0.6 alpha gone, imported texture with alpha
        public static (bool, string) Check(string pngPath, Texture2D imported)
        {
            if (!File.Exists(pngPath)) return (false, "missing " + pngPath);
            var t = new Texture2D(2, 2, TextureFormat.RGBA32, false); t.LoadImage(File.ReadAllBytes(pngPath));
            var px = t.GetPixels32(); Object.DestroyImmediate(t);
            long skin = 0; var below = new long[3]; long whole = px.Length;
            for (int i = 0; i < px.Length; i++)
            {
                int a = px[i].a;
                if (a >= 157 && a <= 159) continue;                  // 0.62 x 255 = 158: outside the UV islands
                skin++;
                float af = a / 255f;
                for (int k = 0; k < 3; k++) if (af < Thresh[k]) below[k]++;
            }
            bool ok = skin > whole / 20;
            var d = $"skin {100.0 * skin / whole:F1} % of the atlas; open at HP 80 / 50 / 0:";
            for (int k = 0; k < 3; k++)
            {
                float c = skin > 0 ? (float)below[k] / skin : 0f;
                ok &= c >= Lo[k] && c <= Hi[k];
                d += $" {100f * c:F1}";
            }
            d += " % of the skin (bands 5-13 / 10-27 / 15-30)";
            bool alpha = imported != null && UnityEngine.Experimental.Rendering.GraphicsFormatUtility.HasAlphaChannel(imported.graphicsFormat);
            d += $", imported {(imported != null ? imported.graphicsFormat.ToString() : "-")}";
            return (ok && alpha, d);
        }
    }
}
