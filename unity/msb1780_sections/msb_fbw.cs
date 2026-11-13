        static void FlyByWire(LandingGear noseGear)
        {
            // design 0.3: FBW gLimitPositive 4.5 (the stock law holds pitch rate = gLimit x g / V: HUD ~gLimit + 1 = ~5.5 g, the sheet's +5.5);
            // corner 150, roll 50 deg/s; the B-17G take-off logic (takeoffSpeed 15: holds the 3-point attitude), pitch P / D as the B-17G;
            // yaw: AB-4 weathervaning 0.05 + yawTightness 3 (engine-out: proportional to sideslip; the rudder is sized for the moment)
            var so = new SerializedObject(controlsFilter);
            void F(string p, float v) { var sp = so.FindProperty("flyByWire." + p); if (sp == null) throw new Exception("no flyByWire." + p); sp.floatValue = v; }
            F("gLimitPositive", 4.5f); F("cornerSpeed", 150f); F("postStallManeuverSpeed", 0f); F("maxRollSpeed", 50f);
            F("takeoffSpeed", FbwTakeoffSpeed); F("rollTrimLimit", FbwRollTrimLimit); F("rollTrimRate", FbwRollTrimRate); F("pFactorFast", FbwPitchP); F("dFactorFast", FbwPitchD); F("pidTransitionSpeed", 120f); F("alphaLimiter", AlphaLimiter);
            F("yawWeathervaning", FbwYawWeathervaning); F("yawTightness", FbwYawTightness);
            so.FindProperty("flyByWire.noseGear").objectReferenceValue = noseGear;     // taildragger: a main gear stands in for weight-on-wheels (B-17G)
            so.ApplyModifiedPropertiesWithoutUndo();
            var ap = parts["fus_cockpit"].GetComponent<AutopilotPlane>();
            var so2 = new SerializedObject(ap);
            var rs = so2.FindProperty("forwardFlightController.referenceAirspeed"); if (rs != null) rs.floatValue = 140f;
            if (BomberAITuning) { var pi = so2.FindProperty("preventInvertedFlight"); if (pi != null) pi.boolValue = true; }
            {
                var sp = so2.FindProperty("forwardFlightController.rollFlightPID.PID"); if (sp == null) throw new Exception("no rollFlightPID");
                sp.vector3Value = AiRollPID;
            }
            so2.ApplyModifiedPropertiesWithoutUndo();
            L($"FBW: g 4.5, corner 150, roll 50, alpha limiter {AlphaLimiter} + incidence {WingIncidence} = CLmax angle {WingCLmaxDeg}; roll trim {FbwRollTrimLimit}/{FbwRollTrimRate}; yaw weathervaning {FbwYawWeathervaning}, tightness {FbwYawTightness}; AI roll PID {AiRollPID}");
        }

