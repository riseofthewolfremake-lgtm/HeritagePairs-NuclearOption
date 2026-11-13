                    float range = (float)drv["range"];
                    var d = DrivenFrame(t);
                    // FD-32 lesson: the lever's grip must move FORWARD at full throttle; flip the sign if it does not
                    var grip = t.GetComponentsInChildren<MeshFilter>(true).FirstOrDefault();
                    if (grip != null)
                    {
                        var top = grip.transform.TransformPoint(grip.sharedMesh.bounds.center + Vector3.up * grip.sharedMesh.bounds.extents.y);
                        var r0 = d.localRotation; d.localEulerAngles = new Vector3(range, 0, 0);
                        var top1 = grip.transform.TransformPoint(grip.sharedMesh.bounds.center + Vector3.up * grip.sharedMesh.bounds.extents.y);
                        d.localRotation = r0;
                        if (top1.z < top.z) { range = -range; cockpitAnimLog.Add($"{name}: range sign flipped so the grip moves forward at full throttle"); }
                        throttleForward[name] = Mathf.Abs(top1.z - top.z);
                    }
