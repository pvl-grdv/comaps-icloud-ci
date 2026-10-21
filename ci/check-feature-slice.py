import argparse
import hashlib
import json
import re
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('feature', choices=('search', 'folder-order', 'item-order'))
    parser.add_argument('--source', type=Path)
    args = parser.parse_args()
    manifest_path = Path('proposals/saved-items/manifest.json')
    manifest = json.loads(manifest_path.read_text())
    assert re.fullmatch('[0-9a-f]{40}', manifest['upstream_revision'])
    feature = manifest['features'][args.feature]
    patch = Path(feature['patch'])
    assert patch == manifest_path.parent / (args.feature + '.patch')
    data = patch.read_bytes()
    assert hashlib.sha256(data).hexdigest() == feature['sha256']
    text = data.decode('utf-8')
    paths = set(re.findall(r'^\+\+\+ b/(.+)$', text, re.M))
    assert paths and paths == set(feature['files']), paths
    assert all(not Path(p).is_absolute() and '..' not in Path(p).parts for p in paths)
    assert not any('/iCloud/' in p or 'CoMaps-Lab' in p for p in paths)
    assert not any(p.startswith(('ci/', '.github/', 'xcode/')) for p in paths)
    for suite in ('map', 'search'):
        expected = feature.get('native_' + suite + '_tests', [])
        plan_path = manifest_path.parent / f'{args.feature}-{suite}-tests.json'
        if not expected:
            assert suite == 'search' and args.feature != 'search'
            assert not plan_path.exists()
            continue
        assert len(expected) == len(set(expected))
        assert json.loads(plan_path.read_text()) == expected
    assert 'bookmarks_test.cpp::Bookmarks_Sorting' in feature['native_map_tests']
    ios_plan = json.loads((manifest_path.parent / f'{args.feature}-ios-tests.json').read_text())
    assert ios_plan == feature['ios_tests'] and ios_plan
    assert len({item['className'] for item in ios_plan}) == len(ios_plan)
    assert all(item['expectedTests'] > 0 for item in ios_plan)
    if args.source:
        assert set(feature['source_sha256']) == paths
        for relative, expected_hash in feature['source_sha256'].items():
            source_file = args.source / relative
            assert source_file.is_file() and not source_file.is_symlink(), relative
            assert hashlib.sha256(source_file.read_bytes()).hexdigest() == expected_hash, relative
        for item in ios_plan:
            source = (args.source / feature['test_sources'][item['className']]).read_text()
            classes = list(re.finditer(
                r'^(?:(?:private|fileprivate|internal|public|final)\s+)*class\s+(\w+)\b', source, re.M))
            matches = [(index, match) for index, match in enumerate(classes)
                       if match.group(1) == item['className']]
            assert len(matches) == 1, item['className']
            index, match = matches[0]
            end = classes[index + 1].start() if index + 1 < len(classes) else len(source)
            count = len(re.findall(r'^\s*func test\w+\s*\(', source[match.end():end], re.M))
            assert count == item['expectedTests'], (item['className'], count)
    print(json.dumps({'feature': args.feature, 'patch_sha256': feature['sha256'],
                      'source_files': len(paths), 'native_map': len(feature['native_map_tests']),
                      'native_search': len(feature.get('native_search_tests', [])),
                      'XCTest': sum(item['expectedTests'] for item in ios_plan),
                      'source_verified': bool(args.source), 'passed': True}, indent=2))


if __name__ == '__main__':
    main()
