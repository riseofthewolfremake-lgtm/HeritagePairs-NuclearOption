        static readonly string[] SkinMaps = { "b", "n", "m", "ao", "dmg_b", "dmg_n" };
        static readonly (string file, string label, string faction)[] BaseLiveries = new (string, string, string)[0];
        // b17g_liveries.json (blender/b17g/textures/build_textures_b17g.py): faction BOTH = offered to both factions (the two historical
        // USAAF schemes, user decision 2026-11-03), BDF / PALA = that faction only.
        static readonly List<(string file, string label, string faction, bool both)> Liveries = new List<(string, string, string, bool)>();

        static void LoadLiveryTable()
        {
            Liveries.Clear();
            var path = Path.Combine(RepoTextures, "b17g_liveries.json");
            if (!File.Exists(path)) throw new Exception("no b17g_liveries.json");
            var jo = Newtonsoft.Json.Linq.JObject.Parse(File.ReadAllText(path));
            int bothCount = 0;
            foreach (var kv in jo)
            {
                if (!(kv.Value is Newtonsoft.Json.Linq.JObject e)) continue;
                var file = Path.GetFileNameWithoutExtension((string)e["texture"]);
                var fac = ((string)e["faction"] ?? "").ToUpperInvariant();
                bool both = fac == "BOTH";
                if (both) fac = (bothCount++ % 2 == 0) ? "BDF" : "PALA";     // ordering only (each faction's own first)
                Liveries.Add((file, (string)e["name"] ?? kv.Key, fac, both));
                L($"livery table: {file} '{(string)e["name"]}' ({(both ? "both factions" : fac + " only")})");
            }
        }
        static readonly Dictionary<string, Color32> LiveryFallback = new Dictionary<string, Color32>();
        static readonly string[] Tiles = { "b17g_tile_structure_b", "b17g_tile_interior_b", "b17g_tile_well_b", "b17g_tile_gear_b", "b17g_tile_tyre_b", "b17g_tile_cowl_b",
            "b17g_tile_turret_b", "b17g_tile_ck_panel_b", "b17g_tile_ck_wall_b", "b17g_tile_ck_od_b", "b17g_tile_ck_floor_b", "b17g_tile_ck_black_b", "b17g_tile_ck_bezel_b" };
        static readonly List<string> PrTextures = new List<string>();
        static readonly Dictionary<string, Texture2D> tex = new Dictionary<string, Texture2D>();

        static void ImportTextures()
        {
            tex.Clear(); PrTextures.Clear();
            LoadLiveryTable();
            foreach (var f in Directory.GetFiles(RepoTextures, "b17g_pr_*_b.png")) PrTextures.Add(Path.GetFileNameWithoutExtension(f));
            var want = SkinMaps.Select(m => "b17g_skin_" + m).Concat(Liveries.Select(l => l.file)).Concat(new[] { "b17g_gauges" }).Concat(Tiles).Concat(PrTextures).ToList();
            foreach (var n in want)
            {
                var src = Path.Combine(RepoTextures, n + ".png");
                if (n == "b17g_skin_m" && !File.Exists(src)) src = Path.Combine(RepoTextures, "b17g_skin_m_usaaf_od.png");   // per-livery metal maps: the default livery's
                var dst = $"{Folder}/Textures/{n}.png";
                bool real = File.Exists(src);
                if (real) File.Copy(src, dst, true);
                else File.WriteAllBytes(dst, FallbackTexture(n).EncodeToPNG());
                AssetDatabase.ImportAsset(dst, ImportAssetOptions.ForceUpdate);
                var ti = (TextureImporter)AssetImporter.GetAtPath(dst);
                bool normal = n.EndsWith("_n");
                bool linear = n.EndsWith("_m") || n.EndsWith("_ao") || normal;
                ti.textureType = normal ? TextureImporterType.NormalMap : TextureImporterType.Default;
                ti.sRGBTexture = !linear; ti.mipmapEnabled = true; ti.maxTextureSize = 4096;
                ti.textureCompression = TextureImporterCompression.Compressed;
                ti.SaveAndReimport();
                tex[n] = AssetDatabase.LoadAssetAtPath<Texture2D>(dst);
                L($"texture {n}: {(real ? "from repo" : "generated flat fallback")}");
            }
        }

