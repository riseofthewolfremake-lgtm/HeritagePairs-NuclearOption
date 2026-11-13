            var copyNames = new List<string> { "fus_cockpit" };
            copyNames.AddRange(root.GetComponentsInChildren<MeshFilter>(true).Where(m => m.name.StartsWith("cockpit_") || m.name.StartsWith("gauge_")).Select(m => m.name));
