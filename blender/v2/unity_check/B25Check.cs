using UnityEngine;
using UnityEditor;
public static class B25Check {
    static void P(Transform root, string n) {
        var t = FindDeep(root, n);
        if (t == null) { Debug.Log("B25 MISSING " + n); return; }
        var r = t.GetComponent<Renderer>();
        string b = r ? (" boundsCenter=" + r.bounds.center.ToString("F3") + " size=" + r.bounds.size.ToString("F3")) : "";
        Debug.Log("B25 " + n + " pos=" + t.position.ToString("F3") + " localRot=" + t.localRotation.eulerAngles.ToString("F2") + " fwd=" + t.forward.ToString("F3") + b);
    }
    static Transform FindDeep(Transform t, string n) {
        if (t.name == n) return t;
        foreach (Transform c in t) { var f = FindDeep(c, n); if (f) return f; }
        return null;
    }
    public static void Run() {
        AssetDatabase.Refresh();
        var go = AssetDatabase.LoadAssetAtPath<GameObject>("Assets/b25h_v2.fbx");
        var inst = (GameObject)Object.Instantiate(go);
        Debug.Log("B25 rootname=" + inst.name + " rootRot=" + inst.transform.rotation.eulerAngles + " scale=" + inst.transform.localScale);
        foreach (var n in new[]{"B25H_root","fus_center","muzzle_cannon","muzzle_tail_L","wing_tip_R","fin_R","gear_main_R_wheel","prop_hub_R","prop_R_blade1","cockpit_eye","gear_main_L_strut","aileron_R","bomb_door_R"}) P(inst.transform, n);
        var bb = new Bounds(); bool first = true;
        foreach (var r in inst.GetComponentsInChildren<Renderer>()) { if (first) { bb = r.bounds; first = false; } else bb.Encapsulate(r.bounds); }
        Debug.Log("B25 TOTALBOUNDS center=" + bb.center.ToString("F3") + " size=" + bb.size.ToString("F3"));
        var imp = (ModelImporter)AssetImporter.GetAtPath("Assets/b25h_v2.fbx");
        Debug.Log("B25 importer globalScale=" + imp.globalScale + " fileScale=" + imp.fileScale + " useFileScale=" + imp.useFileScale);
        var mf = FindDeep(inst.transform, "fus_center").GetComponent<MeshFilter>();
        Debug.Log("B25 fus_center uvs: uv0=" + (mf.sharedMesh.uv.Length) + " uv1=" + mf.sharedMesh.uv2.Length + " submeshes=" + mf.sharedMesh.subMeshCount);
    }
}
