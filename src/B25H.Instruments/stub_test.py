"""Stub test for B25H.Instruments value -> needle-angle mapping (mirrors Plugin.Drive; no game needed).
Run: python -I stub_test.py   Expected: 'ALL PASS'."""
import math

ALT_LONG, ALT_SHORT, VSI, VSI_MAX, FUEL = 0.36, 0.036, 0.028333, 6000.0, 2.7

def repeat(x, n): return x - math.floor(x / n) * n
def drive(alt_m, vy, fuel, euler):
    ft = alt_m * 3.28084
    out = {"alt_long": repeat(ft * ALT_LONG, 360), "alt_short": repeat(ft * ALT_SHORT, 360)}
    fpm = max(-VSI_MAX, min(VSI_MAX, vy * 196.85)); out["vsi"] = fpm * VSI
    out["fuel"] = max(0.0, min(1.0, fuel)) * 100 * FUEL
    ex, ey, ez = euler
    bank = ez - 360 if ez > 180 else ez
    pitch_up = -(ex - 360 if ex > 180 else ex)
    out["att_angle"] = bank; out["att_offset"] = max(-30, min(30, pitch_up)) * -0.0015
    out["heading"] = -ey
    return out

def close(a, b, tol=0.5): return abs(a - b) <= tol
cases = [
    ("1000 ft -> long needle full turn (0), short 36 deg", drive(304.8, 0, 1, (0, 0, 0)), lambda o: close(o["alt_long"], 0, 0.5) or close(o["alt_long"], 360, 0.5)),
    ("500 ft -> long 180", drive(152.4, 0, 1, (0, 0, 0)), lambda o: close(o["alt_long"], 180)),
    ("10000 ft -> short needle full turn", drive(3048, 0, 1, (0, 0, 0)), lambda o: close(o["alt_short"], 0, 0.5) or close(o["alt_short"], 360, 0.5)),
    ("climb 1000 fpm -> +28 deg", drive(0, 5.08, 1, (0, 0, 0)), lambda o: close(o["vsi"], 28.3)),
    ("dive beyond scale clamps to -170", drive(0, -100, 1, (0, 0, 0)), lambda o: close(o["vsi"], -170)),
    ("half fuel -> 135 deg", drive(0, 0, 0.5, (0, 0, 0)), lambda o: close(o["fuel"], 135)),
    ("fuel > 1 clamps", drive(0, 0, 1.4, (0, 0, 0)), lambda o: close(o["fuel"], 270)),
    ("nose up 10 deg (euler x 350) -> card down 15 mm", drive(0, 0, 1, (350, 0, 0)), lambda o: close(o["att_offset"], -0.015, 1e-4)),
    ("bank euler z 20 (left bank) -> card +20 (clockwise as seen by the pilot, ground on the left)", drive(0, 0, 1, (0, 0, 20)), lambda o: close(o["att_angle"], 20)),
    ("bank euler z 340 (right bank) -> card -20 (in game: ground on the right)", drive(0, 0, 1, (0, 0, 340)), lambda o: close(o["att_angle"], -20)),
    ("heading 90 -> card -90", drive(0, 0, 1, (0, 90, 0)), lambda o: close(o["heading"], -90)),
]
fails = 0
for name, o, ok in cases:
    r = ok(o); fails += not r
    print(("PASS " if r else "FAIL ") + name)
print("ALL PASS" if fails == 0 else f"{fails} FAIL")
