#!/usr/bin/env bash
# B-25H cockpit pass 2 (v3) props: fal concept (v3 folder) -> tripo3d image-to-3D -> tripo remesh (own baked textures)
C="/c/Users/User/Nuclear Option B-25/assets/textures_v2/fal_raw_cockpit_b25h/v3"
O="$(cd "$(dirname "$0")" && pwd)"
one() {
  n=$1; faces=$2
  um fal model3d "$C/concept_$n.png" --engine tripo --texture 2048 --out "$O/raw" --name "$n" > "$O/log_$n.txt" 2>&1 || { echo "FAIL model3d $n"; return; }
  ( cd "$O/raw" && um fal run tripo3d/tripo/remesh "mesh_url=@$n.glb" "face_limit:=$faces" --out "$O" --name "${n}_remesh" >> "$O/log_$n.txt" 2>&1 ) || { echo "FAIL remesh $n"; return; }
  echo "DONE $n"
}
one boot 1500 & one footrest 2000 & one loom 1500 &
wait
