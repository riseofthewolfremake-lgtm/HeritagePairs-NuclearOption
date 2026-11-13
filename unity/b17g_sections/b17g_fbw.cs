        static void FlyByWire(LandingGear noseGear)
        {
            var so = new SerializedObject(controlsFilter);
            void F(string p, float v) { var sp = so.FindProperty("flyByWire." + p); if (sp == null) throw new Exception("no flyByWire." + p); sp.floatValue = v; }
            F("gLimitPositive", 3.0f); F("cornerSpeed", 95f); F("postStallManeuverSpeed", 0f); F("maxRollSpeed", 35f);
            F("takeoffSpeed", FbwTakeoffSpeed); F("rollTrimLimit", FbwRollTrimLimit); F("rollTrimRate", FbwRollTrimRate); F("pFactorFast", FbwPitchP); F("dFactorFast", FbwPitchD); F("pidTransitionSpeed", 90f); F("alphaLimiter", AlphaLimiter);
            so.FindProperty("flyByWire.noseGear").objectReferenceValue = noseGear;     // taildragger: a main gear stands in for weight-on-wheels (Nimrod)
            so.ApplyModifiedPropertiesWithoutUndo();
            var ap = parts["fus_cockpit"].GetComponent<AutopilotPlane>();
            var so2 = new SerializedObject(ap);
            var rs = so2.FindProperty("forwardFlightController.referenceAirspeed"); if (rs != null) rs.floatValue = 85f;
            if (BomberAITuning) { var pi = so2.FindProperty("preventInvertedFlight"); if (pi != null) pi.boolValue = true; }
            {   // 1.7.8 AI roll PID (b17g_head.cs AiRollPID: the weave)
                var sp = so2.FindProperty("forwardFlightController.rollFlightPID.PID"); if (sp == null) throw new Exception("no rollFlightPID");
                sp.vector3Value = AiRollPID;
            }
            so2.ApplyModifiedPropertiesWithoutUndo();
            L($"FBW: g 3.0, corner 95, roll 35, alpha limiter {AlphaLimiter} + incidence {WingIncidence} = CLmax angle {WingCLmaxDeg}; roll trim {FbwRollTrimLimit}/{FbwRollTrimRate}; AI roll PID {AiRollPID}");
        }

