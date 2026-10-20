#!/usr/bin/env python3
"""Validate the experimental contribution inventory without building the app."""
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
    plan = load('upstream/plan.json')
    catalog = load('upstream/catalog.json')['patches']
    candidates = plan['candidates']
    ids = [c['id'] for c in candidates]
    require(len(ids) == len(set(ids)) == 8, 'Expected eight distinct candidate IDs')
    series = [line.strip() for line in (ROOT / 'patches/series.txt').read_text().splitlines()
              if line.strip() and not line.startswith('#')]
    require([c['patch'] for c in catalog] == series, 'Catalog differs from historical series')
    require(len(series) == 37, 'Unexpected historical patch count')
    for index, entry in enumerate(catalog, 1):
        data = (ROOT / 'patches' / entry['patch']).read_bytes()
        require(hashlib.sha256(data).hexdigest() == entry['sha256'], 'Patch hash changed')
        paths = set(re.findall(r'^\+\+\+ b/(.+)$', data.decode(), re.M))
        paths.update(re.findall(r'^--- a/(.+)$', data.decode(), re.M))
        require(paths == set(entry['files']), 'Patch paths differ')
        require(entry['position'] == index, 'Patch position differs')
        require(entry['owner'] in ids and set(entry['related']) <= set(ids), 'Unknown owner')
    by_id = {c['id']: c for c in candidates}

    def visit(candidate, stack):
        require(candidate not in stack, 'Dependency cycle')
        require(candidate in by_id, 'Unknown prerequisite')
        for dependency in by_id[candidate]['prerequisites']:
            visit(dependency, stack + [candidate])

    core, search, methods = [], [], []
    expected_methods = {c['className']: c['expectedTests'] for c in load('ci/ios-tests.json')}
    observed_methods = {}
    for c in candidates:
        visit(c['id'], [])
        require(not any(c[k] for k in ('extracted', 'independently_tested', 'submitted')),
                'Do not promote readiness without new independent evidence')
        refs = [p['patch'] for p in catalog if p['owner'] == c['id'] or c['id'] in p['related']]
        require(c['source_patches'] == refs, 'Candidate patch references differ')
        card = ROOT / 'upstream/candidates' / c['id']
        require((card / 'README.txt').is_file(), 'Missing candidate card')
        listed = [s for s in (card / 'source-patches.txt').read_text().splitlines()
                  if s and not s.startswith('#')]
        require(listed == refs, 'Card patch references differ')
        core += c['native_core_tests']
        search += c['native_search_tests']
        for test in c['xctests']:
            cls = test['className']
            methods.append(cls + '.' + test['name'])
            observed_methods[cls] = observed_methods.get(cls, 0) + 1
            require(test['source'] in c['files'], 'Test source is absent from candidate references')
    require(len(core) == len(set(core)) == 48, 'Core tests missing or multiply allocated')
    require(set(core) == set(load('ci/core-tests.json')), 'Core allocation differs from CI')
    require(len(search) == len(set(search)) == 11, 'Search tests missing or duplicated')
    require(search == load('ci/search-tests.json'), 'Search allocation differs from CI')
    require(observed_methods == expected_methods, 'XCTest class counts differ from CI')
    require(len(methods) == len(set(methods)) == 163, 'XCTest methods missing or duplicated')
    verification = load('upstream/verification.json')
    require(verification['candidate'] == plan['candidate'], 'Verification SHA differs')
    require(verification['xctest'] == len(methods), 'Verification test count differs')
    print('Inventory consistent: 8 candidates, 37 unchanged patches, 48 core, 11 search, 163 XCTest.')
    print('This checks documentation consistency; it does not build isolated proposals.')


if __name__ == '__main__':
    main()
