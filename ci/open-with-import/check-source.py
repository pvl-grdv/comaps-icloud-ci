import hashlib
import json
from pathlib import Path
import re
import sys

variant = sys.argv[2]
assert variant in ('baseline', 'candidate')
root = Path('ci/open-with-import' if variant == 'baseline' else 'proposals/open-with')
manifest = json.loads((root / 'source-hashes.json').read_text())
patch = (root / ('baseline-tests.patch' if variant == 'baseline' else 'open-with.patch')).read_bytes()
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
for name, expected in manifest.get('unchangedTestFiles', {}).items():
    assert not Path(name).is_absolute() and '..' not in Path(name).parts
    path = Path('comaps') / name
    assert path.is_file() and not path.is_symlink(), name
    assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, name
if sys.argv[1] == 'after':
    plan = json.loads((root / 'ios-tests.json').read_text())
    assert plan and len({item['className'] for item in plan}) == len(plan)
    methods = []
    for item in plan:
        name = item['className']
        assert re.fullmatch('[A-Za-z_][A-Za-z0-9_]*', name)
        source = (Path('comaps/iphone/Maps/Tests/Core/DeepLink') / (name + '.swift')).read_text()
        found = re.findall(r'^\s*func (test\w+)\s*\(', source, re.M)
        assert len(found) == item['expectedTests'] > 0, (name, found)
        methods.extend(name + '/' + method for method in found)
    if variant == 'candidate':
        assert sorted(methods) == sorted(json.loads((root / 'expected-methods.json').read_text()))
Path('results').mkdir(exist_ok=True)
Path('results/open-with-import-source-' + sys.argv[1] + '.json').write_text(
    json.dumps({'verified': True, 'variant': variant, 'stage': sys.argv[1], 'manifest': manifest}, indent=2) + '\n')
