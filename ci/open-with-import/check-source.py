import hashlib
import json
from pathlib import Path
import re
import sys

root = Path('ci/open-with-import')
manifest = json.loads((root / 'source-hashes.json').read_text())
patch = (root / 'baseline-tests.patch').read_bytes()
assert hashlib.sha256(patch).hexdigest() == manifest['patchSha256']
paths = set(re.findall(r'^\+\+\+ b/(.+)$', patch.decode(), re.M))
assert paths == set(manifest['files'])
assert re.fullmatch('[0-9a-f]{40}', manifest['upstream'])
assert sys.argv[1] in ('before', 'after')
for name, hashes in manifest['files'].items():
    assert not Path(name).is_absolute() and '..' not in Path(name).parts
    path = Path('comaps') / name
    expected = hashes['baseSha256' if sys.argv[1] == 'before' else 'sha256']
    if expected is None:
        assert not path.exists(), name
    else:
        assert path.is_file() and not path.is_symlink(), name
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, name
Path('results').mkdir(exist_ok=True)
Path('results/open-with-import-source-' + sys.argv[1] + '.json').write_text(
    json.dumps({'verified': True, 'stage': sys.argv[1], 'manifest': manifest}, indent=2) + '\n')
