#!/usr/bin/env bash
set +x
set -euo pipefail
umask 077

# This path is intentionally unavailable to a free Personal Team. Keep all
# credentials scoped to the protected environment and this one explicit step.
required=(LAB_TEAM_ID LAB_CERTIFICATE_P12_BASE64 LAB_CERTIFICATE_PASSWORD
          LAB_APP_PROFILE_BASE64 LAB_WIDGET_PROFILE_BASE64
          ASC_KEY_ID ASC_ISSUER_ID ASC_PRIVATE_KEY_P8_BASE64)
for name in "${required[@]}"; do
  if [ -z "${!name:-}" ]; then
    printf '%s\n' 'TestFlight signing requires an active paid Apple Developer Program membership and the configured comaps-lab environment credentials.' >&2
    printf 'Missing configuration: %s\n' "$name" >&2
    exit 1
  fi
done
if [ "${1:-}" = '--check-environment' ]; then
  printf '%s\n' 'Signing configuration names are present; profile and certificate validation runs before upload.'
  exit 0
fi
test "$#" -eq 0
test "${GITHUB_EVENT_NAME:-}" = workflow_dispatch
test "${GITHUB_REF:-}" = refs/heads/comaps-lab
test "${RUNNER_OS:-}" = macOS
test "${LAB_UPLOAD_AUTHORIZED:-}" = true

experiment_dir=$(pwd)
source_dir="$experiment_dir/comaps"
test -f "$source_dir/iphone/Maps/CoMaps-Release.entitlements"
private_dir=$(mktemp -d "${RUNNER_TEMP:?}/comaps-lab-sign.XXXXXX")
keychain="$private_dir/lab-signing.keychain-db"
installed_profiles=()
original_keychains=()
keychain_list_changed=false
cleanup() {
  local exit_code=$?
  set +e
  if [ "$keychain_list_changed" = true ]; then
    if [ "${#original_keychains[@]}" -gt 0 ]; then
      security list-keychains -d user -s "${original_keychains[@]}" >/dev/null 2>&1
    else
      security list-keychains -d user -s >/dev/null 2>&1
    fi
  fi
  security delete-keychain "$keychain" >/dev/null 2>&1
  if [ "${#installed_profiles[@]}" -gt 0 ]; then
    for path in "${installed_profiles[@]}"; do rm -f "$path"; done
  fi
  rm -rf "$private_dir"
  exit "$exit_code"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

export LAB_PRIVATE_DIR="$private_dir"
python3 - <<'PY'
import base64, json, os, re
from pathlib import Path
p = Path(os.environ['LAB_PRIVATE_DIR'])
checks = {'LAB_TEAM_ID': r'[A-Z0-9]{10}', 'ASC_KEY_ID': r'[A-Z0-9]{10}',
          'ASC_ISSUER_ID': r'[0-9A-Fa-f]{8}(?:-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}'}
for name, pattern in checks.items():
    if not re.fullmatch(pattern, os.environ[name]):
        raise SystemExit('Invalid signing configuration identifier: ' + name)
for name, filename in [('LAB_CERTIFICATE_P12_BASE64', 'certificate.p12'),
                       ('LAB_APP_PROFILE_BASE64', 'app.mobileprovision'),
                       ('LAB_WIDGET_PROFILE_BASE64', 'widget.mobileprovision'),
                       ('ASC_PRIVATE_KEY_P8_BASE64', 'AuthKey.p8')]:
    try:
        value = base64.b64decode(''.join(os.environ[name].split()), validate=True)
        if not value: raise ValueError()
    except (ValueError, TypeError):
        raise SystemExit('Invalid encoded signing credential: ' + name)
    (p / filename).write_bytes(value)
PY
openssl pkey -in "$private_dir/AuthKey.p8" -check -noout >/dev/null 2>&1
security cms -D -i "$private_dir/app.mobileprovision" > "$private_dir/app.plist"
security cms -D -i "$private_dir/widget.mobileprovision" > "$private_dir/widget.plist"

while IFS= read -r -d '' path; do original_keychains+=("$path"); done < <(
  security list-keychains -d user | python3 -c 'import shlex,sys; sys.stdout.buffer.write(b"".join(p.encode()+b"\0" for p in shlex.split(sys.stdin.read())))'
)
keychain_password=$(openssl rand -hex 32)
security create-keychain -p "$keychain_password" "$keychain"
security set-keychain-settings -lut 21600 "$keychain"
security unlock-keychain -p "$keychain_password" "$keychain"
if ! security import "$private_dir/certificate.p12" -k "$keychain" \
    -P "$LAB_CERTIFICATE_PASSWORD" -T /usr/bin/codesign -T /usr/bin/security >/dev/null 2>&1; then
  printf '%s\n' 'Could not import signing certificate/private key. Check the P12 and its password.' >&2
  exit 1
fi
unset LAB_CERTIFICATE_P12_BASE64 LAB_CERTIFICATE_PASSWORD LAB_APP_PROFILE_BASE64 LAB_WIDGET_PROFILE_BASE64 ASC_PRIVATE_KEY_P8_BASE64
security set-key-partition-list -S apple-tool:,apple:,codesign: -s -k "$keychain_password" "$keychain" >/dev/null 2>&1
keychain_search=("$keychain")
if [ "${#original_keychains[@]}" -gt 0 ]; then
  keychain_search+=("${original_keychains[@]}")
fi
security list-keychains -d user -s "${keychain_search[@]}"
keychain_list_changed=true
certificate_sha1=$(security find-identity -v -p codesigning "$keychain" | python3 -c '
import re,sys
identities=re.findall(r"\b([A-F0-9]{40})\s+\"Apple Distribution:",sys.stdin.read())
if len(identities)!=1: raise SystemExit("Exactly one valid Apple Distribution signing identity is required in the Lab P12.")
print(identities[0])')

bundle_id=$(python3 -c 'import json; print(json.load(open("ci/lab-config.json"))["bundle_id"])')
container_id=$(python3 -c 'import json; print(json.load(open("ci/lab-config.json"))["icloud_container"])')
validation_args=(--app-profile "$private_dir/app.plist" --widget-profile "$private_dir/widget.plist"
  --entitlements "$source_dir/iphone/Maps/CoMaps-Release.entitlements"
  --team "$LAB_TEAM_ID" --bundle "$bundle_id" --container "$container_id"
  --certificate-sha1 "$certificate_sha1" --output "$private_dir/profiles.json")
python3 ci/lab-validate-signing.py "${validation_args[@]}"
app_profile=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["app_uuid"])' "$private_dir/profiles.json")
widget_profile=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["widget_uuid"])' "$private_dir/profiles.json")

# Xcode 16+ and previous versions use different profile search directories.
for profile_dir in "$HOME/Library/Developer/Xcode/UserData/Provisioning Profiles" "$HOME/Library/MobileDevice/Provisioning Profiles"; do
  mkdir -p "$profile_dir"
  for pair in "app:$app_profile" "widget:$widget_profile"; do
    name=${pair%%:*}; uuid=${pair#*:}; target="$profile_dir/$uuid.mobileprovision"
    if [ -e "$target" ]; then
      cmp "$private_dir/$name.mobileprovision" "$target"
    else
      cp "$private_dir/$name.mobileprovision" "$target"
      installed_profiles+=("$target")
    fi
  done
done

build_number="${GITHUB_RUN_NUMBER:?}.${GITHUB_RUN_ATTEMPT:?}"
[[ "$build_number" =~ ^[1-9][0-9]*\.[1-9][0-9]*$ ]]
xcodebuild archive \
  -workspace "$source_dir/xcode/CoMaps.xcworkspace" -scheme CoMaps \
  -configuration Release -destination 'generic/platform=iOS' \
  -derivedDataPath "$RUNNER_TEMP/comaps-lab-signed-derived-data" \
  -archivePath "$private_dir/CoMaps-Lab.xcarchive" \
  DEVELOPMENT_TEAM="$LAB_TEAM_ID" CODE_SIGN_STYLE=Manual \
  CODE_SIGN_IDENTITY="$certificate_sha1" \
  LAB_APP_PROFILE="$app_profile" LAB_WIDGET_PROFILE="$widget_profile" \
  CURRENT_PROJECT_VERSION="$build_number" COMPILER_INDEX_STORE_ENABLE=NO

archive_app="$private_dir/CoMaps-Lab.xcarchive/Products/Applications/CoMaps.app"
test -d "$archive_app"
widget_app="$archive_app/PlugIns/CoMapsWidgetExtension.appex"
test -d "$widget_app"
codesign --verify --deep --strict "$archive_app"
codesign -d --entitlements :- "$archive_app" > "$private_dir/signed-entitlements.plist" 2>/dev/null
codesign -d --entitlements :- "$widget_app" > "$private_dir/widget-entitlements.plist" 2>/dev/null
python3 ci/lab-validate-signing.py "${validation_args[@]}" \
  --entitlements "$private_dir/signed-entitlements.plist" \
  --archive-info "$archive_app/Info.plist" --widget-info "$widget_app/Info.plist" \
  --widget-entitlements "$private_dir/widget-entitlements.plist"

export LAB_SIGNING_SHA1="$certificate_sha1" LAB_BUNDLE_ID="$bundle_id"
python3 - <<'PY'
import json, os, plistlib
from pathlib import Path
p=Path(os.environ['LAB_PRIVATE_DIR'])
profiles=json.loads((p/'profiles.json').read_text())
bundle=os.environ['LAB_BUNDLE_ID']
options={'method':'app-store-connect', 'destination':'upload', 'signingStyle':'manual',
         'teamID':os.environ['LAB_TEAM_ID'], 'signingCertificate':os.environ['LAB_SIGNING_SHA1'],
         'provisioningProfiles':{bundle:profiles['app_uuid'],bundle+'.widgetextension':profiles['widget_uuid']},
         'iCloudContainerEnvironment':'Production', 'manageAppVersionAndBuildNumber':False,
         'testFlightInternalTestingOnly':True, 'uploadSymbols':True}
(p/'ExportOptions.plist').write_bytes(plistlib.dumps(options))
PY

# This is the only publishing command. The explicit workflow input, protected
# environment approval and validated App Store profiles precede it. No public
# artifact receives IPA, profiles, certificates or API keys.
xcodebuild -exportArchive \
  -archivePath "$private_dir/CoMaps-Lab.xcarchive" \
  -exportPath "$private_dir/export" -exportOptionsPlist "$private_dir/ExportOptions.plist" \
  -authenticationKeyPath "$private_dir/AuthKey.p8" \
  -authenticationKeyID "$ASC_KEY_ID" -authenticationKeyIssuerID "$ASC_ISSUER_ID"
printf '%s\n' 'CoMaps Lab uploaded for internal TestFlight processing. This does not release an App Store version.'
