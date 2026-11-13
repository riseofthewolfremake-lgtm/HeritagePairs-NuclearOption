#!/usr/bin/env bash
# B-25H cockpit props: fal concept (already generated) -> tripo3d image-to-3D -> tripo remesh (game-ready, own baked textures)
UM="/c/Users/User/.claude/plugins/cache/universal-modder/universal-modder/6a8865ae171b/bin/um"
C="/c/Users/User/Nuclear Option B-25/assets/textures_v2/fal_raw_cockpit_b25h"
O="$(cd "$(dirname "$0")" && pwd)"
one() {
  n=$1; faces=$2
  "$UM" fal model3d "$C/concept_$n.png" --engine tripo --texture 2048 --out "$O/raw" --name "$n" > "$O/log_$n.txt" 2>&1 || { echo "FAIL model3d $n"; return; }
  ( cd "$O/raw" && "$UM" fal run tripo3d/tripo/remesh "mesh_url=@$n.glb" "face_limit:=$faces" --out "$O" --name "${n}_remesh" >> "$O/log_$n.txt" 2>&1 ) || { echo "FAIL remesh $n"; return; }
  echo "DONE $n"
}
one yoke 3000 & one column 2000 & one throttle 1200 & one mixture 1000 &
one trimwheel 1500 & one pedal 1500 & one seat 3000 & one proplever 1000 &
wait
