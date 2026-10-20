#!/usr/bin/env python3
"""Ensure the Mac compatibility overlay preserves search and manual-order sources."""
import argparse
import hashlib
import json
from pathlib import Path

DIRECTORIES = (
    'iphone/Maps/Bookmarks',
    'iphone/CoreApi/CoreApi/Bookmarks',
    'libs/search/bookmarks',
)
FILES = (
    'libs/map/bookmark_manager.cpp',
    'libs/map/bookmark_manager.hpp',
    'libs/map/search_api.cpp',
    'libs/map/search_api.hpp',
    'libs/map/saved_items_search_params.hpp',
    'libs/map/track.cpp',
    'libs/map/track.hpp',
)


def snapshot(source):
    paths = set(FILES)
    for directory in DIRECTORIES:
        folder = source / directory
        if not folder.is_dir():
            raise SystemExit('Missing feature source directory: ' + directory)
        children = [p for p in folder.rglob('*') if p.is_file()]
        if not children:
            raise SystemExit('Empty feature source directory: ' + directory)
        paths.update(str(p.relative_to(source)) for p in children)
    result = {}
    for path in sorted(paths):
        file = source / path
        if not file.is_file() or file.is_symlink():
            raise SystemExit('Missing or symlinked feature source: ' + path)
        result[path] = hashlib.sha256(file.read_bytes()).hexdigest()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('record', 'verify'))
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    args = parser.parse_args()
    current = snapshot(args.source)
    if args.mode == 'record':
        args.manifest.write_text(json.dumps({'sha256': current}, indent=2) + '\n')
        print('Recorded', len(current), 'search and manual-order source files.')
        return
    previous = json.loads(args.manifest.read_text())['sha256']
    changed = sorted(p for p in previous.keys() | current.keys()
                     if previous.get(p) != current.get(p))
    if changed:
        raise SystemExit('Mac overlay altered saved-item feature sources:\n' + '\n'.join(changed))
    print('Mac overlay preserved all', len(current), 'search and manual-order source files.')


if __name__ == '__main__':
    main()
