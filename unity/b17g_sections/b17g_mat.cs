        static void BuildMaterials()
        {
            var skin = Asset<Shader>("Shader/Shader Graphs_AircraftSkin_PLACEHOLDER.shader");
            var paint = new Material(skin) { name = "B17G_paint" };
            paint.SetTexture("_Basecolor", tex["b17g_skin_b"]);
            paint.SetTexture("_Normal", tex["b17g_skin_n"]);
            paint.SetTexture("_Metallic", tex["b17g_skin_m"]);
            paint.SetTexture("_AO", tex["b17g_skin_ao"]);
            paint.SetTexture("_BasecolorDmg", tex["b17g_skin_dmg_b"]);
            paint.SetTexture("_NormalDmg", tex["b17g_skin_dmg_n"]);
            paint.SetTexture("_Livery", tex["b17g_skin_b"]);
            paint.SetFloat("_Glossiness", 0.2f);
            paint.SetFloat("_HitPoints", 100f);
            Save(paint, "paint");

            var lit = Shader.Find("Universal Render Pipeline/Lit");
            if (lit == null) throw new Exception("URP Lit shader not found");
            // tiled materials (detail UV moved to UV0 by CopyMesh), colours baked into the fal tiles
            foreach (var (key, tile, metal, smooth) in new[] {
                ("structure", "b17g_tile_structure_b", 0.5f, 0.35f), ("interior", "b17g_tile_interior_b", 0.1f, 0.25f), ("well", "b17g_tile_well_b", 0.2f, 0.3f),
                ("gear", "b17g_tile_gear_b", 0.6f, 0.45f), ("tyre", "b17g_tile_tyre_b", 0.0f, 0.1f), ("cowl", "b17g_tile_cowl_b", 0.4f, 0.4f),
                ("turret", "b17g_tile_turret_b", 0.2f, 0.3f), ("ck_panel", "b17g_tile_ck_panel_b", 0.1f, 0.35f), ("ck_wall", "b17g_tile_ck_wall_b", 0.1f, 0.3f),
                ("ck_od", "b17g_tile_ck_od_b", 0.1f, 0.3f), ("ck_floor", "b17g_tile_ck_floor_b", 0.1f, 0.2f), ("ck_black", "b17g_tile_ck_black_b", 0.1f, 0.3f),
                ("ck_bezel", "b17g_tile_ck_bezel_b", 0.6f, 0.5f) })
            {
                var m = Tiled(LitMat(lit, "B17G_" + key, Color.white, metal, smooth), tile);
                if (key.StartsWith("ck_")) { m.SetTextureScale("_BaseMap", new Vector2(2f, 2f)); }
                Save(m, key);
            }
            Save(LitMat(lit, "B17G_cove", new Color(0.05f, 0.05f, 0.05f), 0f, 0.1f), "cove");
            Save(LitMat(lit, "B17G_chrome", new Color(0.85f, 0.86f, 0.88f), 1f, 0.85f), "chrome");
            Save(LitMat(lit, "B17G_metal_dark", new Color(0.06f, 0.06f, 0.065f), 0.7f, 0.6f), "metal_dark");
            Save(LitMat(lit, "B17G_exhaust", new Color(0.13f, 0.075f, 0.05f), 0.4f, 0.35f), "exhaust");       // 1.8.3: heat-rusted turbo / exhaust (reference)
            Save(LitMat(lit, "B17G_turbo", new Color(0.26f, 0.13f, 0.06f), 0.15f, 0.30f), "turbo");          // 1.8.5 offline E (F2): turbo housing + volute, lighter rust than the pipes (faces down into shade)
            Save(LitMat(lit, "B17G_cowl_ring", new Color(0.24f, 0.25f, 0.15f), 0.1f, 0.35f), "cowl_ring");  // 1.8.3: olive-drab anti-glare cowl lip
            Save(LitMat(lit, "B17G_prop", new Color(0.03f, 0.03f, 0.03f), 0.2f, 0.5f), "prop");
            Save(LitMat(lit, "B17G_engine", new Color(0.3f, 0.3f, 0.3f), 0.8f, 0.6f), "engine");
            Save(LitMat(lit, "B17G_needle", new Color(0.92f, 0.92f, 0.88f), 0f, 0.5f), "needle");
            var gauges = LitMat(lit, "B17G_gauges", Color.white, 0f, 0.55f);
            gauges.SetTexture("_BaseMap", tex["b17g_gauges"]); gauges.SetTexture("_MainTex", tex["b17g_gauges"]);
            Save(gauges, "gauges");
            Save(LitMat(lit, "B17G_navlight", new Color(0.3f, 0.3f, 0.3f), 0f, 0.8f), "navlight");
            Save(LitMat(lit, "B17G_screen", Color.black, 0f, 0.5f), "screen");
            foreach (var t in PrTextures)      // fal props: their own base colour on the generated UV (CopyMesh keeps UV0 for pr_*)
            {
                var key = t.Replace("b17g_", "").Replace("_b", "");
                if (t.EndsWith("_b")) key = t.Substring("b17g_".Length, t.Length - "b17g_".Length - 2);
                var m = LitMat(lit, "B17G_" + key, key == "pr_r1820" ? new Color(0.46f, 0.46f, 0.47f) : Color.white, key == "pr_r1820" ? 0.6f : 0.2f, 0.35f);   // 1.8.3: R-1820 face steel-dark as the reference
                m.SetTexture("_BaseMap", tex[t]); m.SetTexture("_MainTex", tex[t]);
                Save(m, key);
            }
            var glass = new Material(Asset<Material>("Material/COIN_glass_PLACEHOLDER.mat")) { name = "B17G_glass" };
            Save(glass, "glass");
            // FD-32 lesson (canopy_int darkened the whole view): the cockpit-layer glass copies use a faint transparent URP Lit
            // (a copy of the stock prop-disc material: transparent queue), not COIN_glass_int
            var glassCk = new Material(Asset<Material>("Material/COIN_propdisc1_PLACEHOLDER.mat")) { name = "B17G_glass_ck" };
            glassCk.SetTexture("_BaseMap", null); glassCk.SetTexture("_MainTex", null);
            glassCk.SetColor("_BaseColor", new Color(0.86f, 0.92f, 0.97f, 0.06f)); glassCk.SetColor("_Color", new Color(0.86f, 0.92f, 0.97f, 0.06f));
            glassCk.SetFloat("_Smoothness", 0.95f); glassCk.SetFloat("_Cull", 0f);
            Save(glassCk, "glass_int");
            var disc = new Material(Asset<Material>("Material/COIN_propdisc1_PLACEHOLDER.mat")) { name = "B17G_propdisc" };
            var blur = PropBlurTexture();
            disc.SetTexture("_BaseMap", blur); disc.SetTexture("_MainTex", blur);
            disc.SetTexture("_OcclusionMap", null); disc.DisableKeyword("_OCCLUSIONMAP");
            disc.SetColor("_BaseColor", Color.white); disc.SetColor("_Color", Color.white);
            disc.SetFloat("_Smoothness", 0.63f); disc.SetFloat("_Cull", 0f);
            Save(disc, "propdisc");
            L("materials: " + string.Join(", ", mats.Keys) + $" (glass shader {glass.shader.name}, disc shader {disc.shader.name})");
        }

