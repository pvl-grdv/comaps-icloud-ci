#!/usr/bin/env bash
# Run from the experiment repository after prepare-upstream.sh and the Mac overlay.
# The existing workspace builds its C++ libraries and UIKit frameworks directly;
# a separate CMake desktop/Qt build would produce the wrong platform here.
set -euo pipefail

experiment_dir=$(pwd)
upstream_dir="$experiment_dir/comaps"
results_dir="$experiment_dir/results/mac-lab"
derived_data="${RUNNER_TEMP:?RUNNER_TEMP is required}/comaps-mac-derived-data"
jobs="${MAC_BUILD_JOBS:-3}"
phase=preflight
mkdir -p "$results_dir"

finish() {
  local status=$?
  if [ "$status" -ne 0 ]; then
    printf 'CoMaps Lab Mac failed during %s (exit %s). See results/mac-lab.\n' "$phase" "$status" >&2
    if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
      printf 'CoMaps Lab Mac: failed during %s (exit %s). No successful build or launch is claimed.\n' \
        "$phase" "$status" >> "$GITHUB_STEP_SUMMARY"
    fi
  fi
}
trap finish EXIT

test "$(uname -s)" = Darwin || { printf '%s\n' 'Mac Catalyst requires a macOS Xcode runner.' >&2; exit 1; }
test "$(uname -m)" = arm64 || { printf '%s\n' 'This probe targets an Apple silicon Mac (arm64).' >&2; exit 1; }
case "$jobs" in ''|*[!0-9]*|0) printf '%s\n' 'MAC_BUILD_JOBS must be a positive integer.' >&2; exit 1 ;; esac
test -d "$upstream_dir/xcode/CoMaps.xcworkspace"
test -d "$upstream_dir/3party/boost"
xcodebuild -version
xcrun --sdk macosx --show-sdk-path

cd "$upstream_dir"
build_args=(
  -workspace xcode/CoMaps.xcworkspace
  -scheme CoMaps
  -configuration Release
  -sdk macosx
  -destination 'platform=macOS,variant=Mac Catalyst,arch=arm64'
  -derivedDataPath "$derived_data"
  -jobs "$jobs"
  SUPPORTS_MACCATALYST=YES
  ARCHS=arm64
  ONLY_ACTIVE_ARCH=YES
  CODE_SIGNING_REQUIRED=NO
  CODE_SIGNING_ALLOWED=NO
  COMPILER_INDEX_STORE_ENABLE=NO
)

phase=build-settings
xcodebuild "${build_args[@]}" -showBuildSettings -json \
  > "$results_dir/build-settings.json" 2> "$results_dir/build-settings.log"
app_path=$(python3 - "$results_dir/build-settings.json" <<'PY'
import json
import shlex
import sys
from pathlib import Path

settings = json.loads(Path(sys.argv[1]).read_text())
apps = [item["buildSettings"] for item in settings
        if item["buildSettings"].get("PRODUCT_TYPE") == "com.apple.product-type.application"]
if len(apps) != 1:
    raise SystemExit(f"Expected one application in the CoMaps build, found {len(apps)}")
app = apps[0]
if app.get("EFFECTIVE_PLATFORM_NAME") != "-maccatalyst":
    raise SystemExit("Xcode did not select Mac Catalyst; refusing a desktop Qt/iOS substitute")
if app.get("SUPPORTS_MACCATALYST") != "YES" or app.get("ARCHS") != "arm64":
    raise SystemExit("Expected an arm64 Mac Catalyst application")
link_flags = app.get("OTHER_LDFLAGS", "")
if isinstance(link_flags, str):
    link_flags = shlex.split(link_flags)
if any("Qt" in flag or flag in ("OpenGL", "OpenGLES") for flag in link_flags):
    raise SystemExit("Catalyst build settings still link desktop Qt or OpenGL frameworks")
print(Path(app["TARGET_BUILD_DIR"]) / app["FULL_PRODUCT_NAME"])
PY
)

phase=compile-and-link
xcodebuild "${build_args[@]}" build 2>&1 | tee "$results_dir/xcodebuild.log"

phase=verify-built-platform
test -d "$app_path/Contents/MacOS"
python3 - "$app_path" "$results_dir" <<'PY'
import json
import plistlib
import subprocess
import sys
from pathlib import Path

app, results = map(Path, sys.argv[1:])
with (app / "Contents/Info.plist").open("rb") as stream:
    info = plistlib.load(stream)
if info.get("CoMapsLabLocalOnly") is not True or info.get("NSUbiquitousContainers"):
    raise SystemExit("Expected the local-only Lab overlay without iCloud containers")
executable = app / "Contents/MacOS" / info["CFBundleExecutable"]
architectures = subprocess.check_output(["xcrun", "lipo", "-archs", str(executable)], text=True).strip()
if architectures != "arm64":
    raise SystemExit(f"Unexpected application architectures: {architectures}")
platform = subprocess.check_output(["xcrun", "vtool", "-show-build", str(executable)], text=True)
(results / "mach-o-platform.txt").write_text(platform)
if not any(line.split() == ["platform", "MACCATALYST"] for line in platform.splitlines()):
    raise SystemExit("Linked application does not declare the Mac Catalyst Mach-O platform")
(results / "build.json").write_text(json.dumps({
    "app_path": str(app),
    "bundle_id": info["CFBundleIdentifier"],
    "executable": str(executable),
    "architecture": architectures,
    "platform": "Mac Catalyst",
    "configuration": "Release",
    "build_passed": True,
    "signed_for_distribution": False,
    "launched": False,
    "live_icloud_tested": False,
}, indent=2) + "\n")
PY

if [ -n "${GITHUB_OUTPUT:-}" ]; then
  printf 'app_path=%s\n' "$app_path" >> "$GITHUB_OUTPUT"
fi
if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
  printf '%s\n' \
    'CoMaps Lab Mac: arm64 Mac Catalyst Release build and linked Mach-O platform verified.' \
    'The existing Xcode workspace built the C++ libraries and UIKit application; no Qt/CMake desktop substitution.' \
    'This step does not prove launch, UI behavior, Gatekeeper acceptance, or live iCloud.' \
    >> "$GITHUB_STEP_SUMMARY"
fi
