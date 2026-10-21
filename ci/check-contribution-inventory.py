#!/usr/bin/env python3
"""Check the CoMaps contribution study inventory, not product behavior or acceptance."""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    return json.loads((ROOT / path).read_text())


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def main():
    plan = load('proposals/plan.json')
    catalog = load('proposals/catalog.json')['patches']
    candidates = plan['candidates']
    ids = [c['id'] for c in candidates]
    require(len(ids) == len(set(ids)) == 8, 'Expected eight candidate IDs')
    series = [line for line in (ROOT / 'patches/series.txt').read_text().splitlines()
              if line and not line.startswith('#')]
    require([p['patch'] for p in catalog] == series, 'Catalog differs from actual series')
    require(len(series) == 39, 'Unexpected current historical patch count')
    for position, entry in enumerate(catalog, 1):
        data = (ROOT / 'patches' / entry['patch']).read_bytes()
        require(hashlib.sha256(data).hexdigest() == entry['sha256'], 'Patch hash differs')
        paths = set(re.findall(r'^diff --git a/(.*?) b/\1$', data.decode(), re.M))
        require(paths == set(entry['files']), 'Patch paths differ')
        require(entry['position'] == position, 'Patch position differs')
        require(entry['owner'] in ids and set(entry['related']) <= set(ids), 'Unknown owner')
    by_id = {c['id']: c for c in candidates}

    def visit(candidate, stack):
        require(candidate not in stack, 'Dependency cycle')
        require(candidate in by_id, 'Unknown prerequisite')
        for dependency in by_id[candidate]['prerequisites']:
            visit(dependency, stack + [candidate])

    core, search, methods, observed = [], [], [], {}
    features = load('proposals/saved-items/manifest.json')['features']
    for candidate in candidates:
        visit(candidate['id'], [])
        require(not candidate['submitted'], 'Inventory cannot claim an upstream submission')
        refs = [p['patch'] for p in catalog
                if p['owner'] == candidate['id'] or candidate['id'] in p['related']]
        require(candidate['source_patches'] == refs, 'Candidate patch references differ')
        card = ROOT / 'proposals/candidates' / candidate['id']
        require((card / 'README.txt').is_file(), 'Missing candidate card')
        listed = [s for s in (card / 'source-patches.txt').read_text().splitlines()
                  if s and not s.startswith('#')]
        require(listed == refs, 'Card patch references differ')
        if candidate['extracted']:
            standalone = candidate['standalone']
            feature = features[standalone['feature']]
            require(standalone['sha256'] == feature['sha256'], 'Standalone hash differs')
            require(standalone['patch'] == feature['patch'], 'Standalone patch differs')
            require(standalone['required_XCTest'] == sum(t['expectedTests'] for t in feature['ios_tests']),
                    'Standalone XCTest plan differs')
            if candidate['independently_tested']:
                require(standalone.get('verified') is True, 'Missing final independent evidence')
        else:
            require(not candidate['independently_tested'], 'Unextracted feature cannot be independent')
        core += candidate['native_core_tests']
        search += candidate['native_search_tests']
        for test in candidate['xctests']:
            cls = test['className']
            methods.append(cls + '.' + test['name'])
            observed[cls] = observed.get(cls, 0) + 1
            require(test['source'] in candidate['files'], 'Test source missing from topic files')
    require(len(core) == len(set(core)) == 48, 'Core allocation missing or duplicated')
    require(set(core) == set(load('ci/core-tests.json')), 'Core allocation differs from CI')
    require(len(search) == len(set(search)) == 11, 'Search allocation missing or duplicated')
    require(search == load('ci/search-tests.json'), 'Search allocation differs from CI')
    expected = {t['className']: t['expectedTests'] for t in load('ci/ios-tests.json')}
    require(observed == expected, 'XCTest class counts differ from CI')
    require(len(methods) == len(set(methods)) == sum(expected.values()) == 166,
            'XCTest allocation missing or duplicated')
    evidence = load('proposals/evidence/status.json')
    require(evidence['full_candidate_commit'] == plan['candidate'], 'Candidate SHA differs')
    require(evidence['required_full']['base_XCTest'] == len(methods), 'Evidence plan differs')
    print('Inventory consistent: 8 topics, 39 patches, 48 core, 11 search, 166 product XCTest.')
    print('This checks documentation consistency; it does not build apps or approve contributions.')


if __name__ == '__main__':
    main()
