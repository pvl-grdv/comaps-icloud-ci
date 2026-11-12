import hashlib
import json
from pathlib import Path
import plistlib
import sys

app = Path(sys.argv[1])
mode = sys.argv[2]
assert mode in ('simulator', 'release')
info = plistlib.loads((app / 'Info.plist').read_bytes())
root = Path(__file__).resolve().parents[2]
reference = plistlib.loads((root / 'ci/open-with-probe/reference/CoMaps.plist').read_bytes())
assert info['LSSupportsOpeningDocumentsInPlace'] is True
for key in ('CFBundleDocumentTypes', 'UTImportedTypeDeclarations', 'UIFileSharingEnabled'):
    assert info[key] == reference[key], key
expected_id, platform = ('app.comaps.debug', 'iPhoneSimulator') if mode == 'simulator' else ('app.comaps', 'iPhoneOS')
assert info['CFBundleIdentifier'] == expected_id
assert info['CFBundleSupportedPlatforms'] == [platform]
executable = app / info['CFBundleExecutable']
assert executable.is_file() and executable.stat().st_size > 0
record = {'mode': mode, 'bundle_id': expected_id, 'platform': platform,
          'open_in_place': True, 'original_document_declarations_unchanged': True,
          'plist_sha256': hashlib.sha256((app / 'Info.plist').read_bytes()).hexdigest(),
          'executable_sha256': hashlib.sha256(executable.read_bytes()).hexdigest()}
results = root / 'results'
results.mkdir(exist_ok=True)
(results / ('open-with-app-' + mode + '.json')).write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps(record, indent=2))
