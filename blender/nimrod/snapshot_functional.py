"""Snapshot of the functional geometry of a Nimrod .blend: the own-mesh bounds of every Unity part (they set the part
collider, its centre of mass and the lift point in NimrodBuild.cs), the gear/wheel bounds and the contract numbers.
check_nimrod_model.py compares a new build against the 1.2.3 snapshot (assets/model_nimrod/nimrod_functional_123.json).

  blender --background <nimrod.blend> --python blender/nimrod/snapshot_functional.py -- --out <json>
"""
import bpy, sys, json
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
OUT = argv[argv.index('--out') + 1]
PARTS = ['fus_center', 'fus_engine', 'fus_rear', 'wing_upper_C', 'wing_upper_L', 'wing_upper_R', 'wing_lower_L', 'wing_lower_R', 'aileron_L', 'aileron_R',
         'stab_L', 'stab_R', 'elevator_L', 'elevator_R', 'fin', 'rudder', 'gear_main_L_wheel', 'gear_main_R_wheel', 'gear_tail_wheel']
out = {}
for n in PARTS:
    o = bpy.data.objects[n]
    vs = [o.matrix_world @ v.co for v in o.data.vertices]
    out[n] = dict(lo=[round(min(v[i] for v in vs), 4) for i in range(3)], hi=[round(max(v[i] for v in vs), 4) for i in range(3)])
EMPT = ['NIMROD1_root', 'prop', 'tailhook', 'hp_tailhook', 'muzzle_gun_L', 'muzzle_gun_R', 'hp_bomb_L', 'hp_bomb_R', 'navlight_L', 'navlight_R',
        'gear_main_L_strut', 'gear_main_R_strut', 'gear_tail_strut', 'exhaust_point', 'cockpit_rudderbar', 'cockpit_stick', 'cockpit_throttle', 'aileron_L', 'aileron_R',
        'elevator_L', 'elevator_R', 'rudder', 'flash_gun_L', 'flash_gun_R']
out['_pivots'] = {n: [round(c, 4) for c in bpy.data.objects[n].matrix_world.translation] for n in EMPT if n in bpy.data.objects}
out['_rot'] = {n: [round(c, 4) for c in bpy.data.objects[n].matrix_world.to_quaternion()] for n in EMPT if n in bpy.data.objects}
json.dump(out, open(OUT, 'w'), indent=1)
print('[snap] wrote', OUT)
