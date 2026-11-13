#!/usr/bin/env bash
# build_instruments.sh <out_dir>: compile src/B25H.Instruments with Unity's Roslyn (no .NET SDK on this PC) against the game's
# Managed DLLs + BepInEx core (read-only references). Writes <out_dir>/B25H.Instruments.dll and prints its sha256.
set -e
OUT=${1:?out dir}
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
U="/c/Program Files/Unity 2022.3.62f2/Editor/Data"
G="/c/Program Files (x86)/Steam/steamapps/common/Nuclear Option"
M="$G/NuclearOption_Data/Managed"
mkdir -p "$OUT"
w() { cygpath -w "$1"; }
REFS=()
for d in mscorlib netstandard System System.Core Assembly-CSharp UnityEngine UnityEngine.CoreModule UnityEngine.PhysicsModule Mirage UniTask; do REFS+=("-r:$(w "$M/$d.dll")"); done
REFS+=("-r:$(w "$G/BepInEx/core/BepInEx.dll")" "-r:$(w "$G/BepInEx/core/0Harmony.dll")")
SRC=(); for f in "$ROOT"/src/B25H.Instruments/*.cs; do SRC+=("$(w "$f")"); done
"$U/NetCoreRuntime/dotnet.exe" "$(w "$U/DotNetSdkRoslyn/csc.dll")" -nologo -noconfig -nostdlib+ -target:library -langversion:latest -optimize+ -deterministic \
  -nowarn:CS0618,CS0649,CS0169,CS0414 "-out:$(w "$OUT/B25H.Instruments.dll")" "${REFS[@]}" "${SRC[@]}"
sha256sum "$OUT/B25H.Instruments.dll"
