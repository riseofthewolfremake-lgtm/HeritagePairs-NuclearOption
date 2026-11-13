            // 1.6.1 (in game 1.6.0 the ControlSurface-driven columns / wheels never moved, 07_yoke_*): each wheel rode a Cockpit.joysticks
            // entry at its hub (Cockpit.cs 16-19: localEulerAngles = (pitch x range, 0, -roll x range)): the wheel tilted at the hub and the
            // column never moved. 1.8.9 (offline J; user on 1.8.8: "The WHEEL moves, the stick does not"): ColumnPlugin189 = no joystick entry;
            // the B25H.Instruments B17G branch (B17G.cs ColumnDeg / WheelDeg) pitches cockpit_column_L/R about their floor pivots (local +X =
            // lateral) and turns cockpit_yoke_L/R about their hub axes (local +X = toward the pilot); the wheels stay children of the columns,
            // so the column carries the wheel. A two-joystick hierarchy cannot do it: the stock driver writes pitch AND roll on every entry, so a
            // column entry would also roll the column (and the wheel with it) about the column frame's Z: a stray yaw of the wheel.
            // unity/Editor/ColumnCheck189.cs proves pitch / roll / no-yaw on the built prefab with the plugin's formula.
            {
                var js = new List<object>();
                foreach (var side in new[] { "L", "R" })
                {
                    var y = TryFind("cockpit_yoke_" + side); var col = TryFind("cockpit_column_" + side);
                    if (y == null) continue;
                    foreach (var c in new[] { y, col }) if (c != null) foreach (var cs in c.GetComponents<ControlSurface>()) Object.DestroyImmediate(cs);
                    if (ColumnPlugin189)
                    {
                        cockpitAnimLog.Add($"{y.name}: no Cockpit.joysticks (1.8.9: B25H.Instruments turns it about its hub axis {y.right.ToString("F2")}); {(col != null ? col.name : "-")}: pitched by the plugin about {(col != null ? col.right.ToString("F2") : "-")}");
                        continue;
                    }
                    var fwd = -y.right; var up = Vector3.ProjectOnPlane(root.transform.up, fwd).normalized;
                    var frame = NewGO(y.name + "_jsframe", y.parent, y.position, Quaternion.LookRotation(fwd, up), y.gameObject.layer);
                    var drv = NewGO(y.name + "_jsdrive", frame.transform, y.position, frame.transform.rotation, y.gameObject.layer);
                    y.SetParent(drv.transform, true);
                    var e = NewElem(ck, "joysticks"); S(e, "transform", drv.transform); S(e, "range", YokeJoystickRange); js.Add(e);
                    cockpitAnimLog.Add($"{y.name}: Cockpit.joysticks range {YokeJoystickRange} (column axis {fwd.ToString("F2")})");
                }
                SetSeq(ck, "joysticks", js);
            }
