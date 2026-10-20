#!/usr/bin/env python3
"""Ad-hoc sign and package a source-built arm64 Mac Catalyst Local Lab copy."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import stat
import struct
import subprocess
import tempfile
from urllib.parse import urlsplit

BUNDLE = 'com.pvlgrdv.comapslab.local.mac'
DISPLAY_NAME = 'CoMaps Lab Local'
APP_NAME = DISPLAY_NAME + '.app'
ZIP_NAME = 'CoMaps-Lab-Local-Mac-arm64.zip'
SIGNING_FILES = {'_CodeSignature', 'CodeResources', 'embedded.mobileprovision', 'embedded.provisionprofile'}
MACHO_MAGIC = {b'\xcf\xfa\xed\xfe', b'\xfe\xed\xfa\xcf', b'\xce\xfa\xed\xfe',
               b'\xfe\xed\xfa\xce', b'\xca\xfe\xba\xbe', b'\xca\xfe\xba\xbf'}
ENTITLEMENTS = {key: True for key in ('com.apple.security.app-sandbox',
                'com.apple.security.network.client', 'com.apple.security.files.user-selected.read-write',
                'com.apple.security.personal-information.location')}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def command(*args, capture=False):
    return subprocess.run([str(arg) for arg in args], check=True,
                          stdout=subprocess.PIPE if capture else None).stdout


def is_macho(path):
    with path.open('rb') as stream:
        return stream.read(4) in MACHO_MAGIC


def check_catalyst_binary(path):
    """Require the arm64 Mac Catalyst executable format expected from the CI build."""
    data = path.read_bytes()
    require(len(data) >= 32 and data[:4] == b'\xcf\xfa\xed\xfe',
            'Expected a thin arm64 Mach-O executable')
    cpu, _, kind, count, command_bytes = struct.unpack_from('<IIIII', data, 4)
    require(cpu == 0x0100000C and kind == 2, 'Expected an arm64 executable')
    position, end = 32, 32 + command_bytes
    require(end <= len(data) and count <= command_bytes // 8, 'Invalid Mach-O load commands')
    platform = None
    for _ in range(count):
        require(position + 8 <= end, 'Truncated Mach-O load command')
        code, length = struct.unpack_from('<II', data, position)
        require(length >= 8 and position + length <= end, 'Invalid Mach-O load command size')
        if code == 0x32:  # LC_BUILD_VERSION: PLATFORM_MACCATALYST = 6
            require(length >= 24, 'Invalid Mach-O platform command')
            platform = struct.unpack_from('<I', data, position + 8)[0]
        if code in (0x21, 0x2C):
            require(length >= 20 and struct.unpack_from('<I', data, position + 16)[0] == 0,
                    'Encrypted input cannot be packaged')
        position += length
    require(position == end and platform == 6, 'Expected a Mac Catalyst build')


def provenance(commit):
    commit = os.environ.get('GITHUB_SHA') if commit is None else commit
    require(isinstance(commit, str) and re.fullmatch(r'[0-9a-fA-F]{40}', commit),
            'A full source commit is required (--commit or GITHUB_SHA)')
    server, repository, run_id = (os.environ.get(key) for key in
                                  ('GITHUB_SERVER_URL', 'GITHUB_REPOSITORY', 'GITHUB_RUN_ID'))
    run_url = None
    if any(value is not None for value in (server, repository, run_id)):
        parsed = urlsplit(server or '')
        require(parsed.scheme == 'https' and parsed.hostname and not parsed.username and not parsed.password
                and parsed.path in ('', '/') and not parsed.query and not parsed.fragment,
                'Invalid GitHub server URL')
        require(isinstance(repository, str) and re.fullmatch(r'[A-Za-z0-9_-][A-Za-z0-9_.-]*/[A-Za-z0-9_-][A-Za-z0-9_.-]*', repository)
                and isinstance(run_id, str) and re.fullmatch(r'[1-9][0-9]*', run_id),
                'Invalid GitHub repository/run provenance')
        run_url = server.rstrip('/') + '/' + repository + '/actions/runs/' + run_id
    return commit.lower(), run_url


def package(app, output_dir, entitlements, commit=None):
    commit, run_url = provenance(commit)
    entitlements = Path(entitlements).resolve()
    requested = plistlib.loads(entitlements.read_bytes())
    require(isinstance(requested, dict) and requested.keys() == ENTITLEMENTS.keys()
            and all(value is True for value in requested.values()),
            'Mac Local Lab requires the exact sandbox, network, user-selected files and location entitlements')
    app = Path(app).absolute()
    require(app.is_dir() and app.suffix == '.app' and not app.is_symlink(), 'A built .app directory is required')
    app, output_dir = app.resolve(), Path(output_dir).resolve()
    require(output_dir != app and app not in output_dir.parents, 'Output must be outside the source application')
    contents = app / 'Contents'
    require(contents.is_dir() and not contents.is_symlink(), 'Expected a macOS Contents directory')
    require(not (contents / 'Info.plist').is_symlink(), 'Info.plist must not be a symlink')
    info = plistlib.loads((contents / 'Info.plist').read_bytes())
    require(info.get('CFBundleIdentifier') == BUNDLE and info.get('CFBundleDisplayName') == DISPLAY_NAME
            and info.get('CoMapsLabLocalOnly') is True, 'Only explicitly marked CoMaps Lab Local may be packaged')
    require('NSUbiquitousContainers' not in info and not any('icloud' in key.lower() for key in info),
            'Local Lab must not declare iCloud settings')
    executable = info.get('CFBundleExecutable')
    require(isinstance(executable, str) and executable not in ('', '.', '..') and '/' not in executable,
            'Invalid main executable name')
    main = contents / 'MacOS' / executable
    require(main.is_file() and not main.is_symlink() and app in main.resolve().parents
            and main.stat().st_mode & stat.S_IXUSR,
            'The main executable is missing or not executable')
    check_catalyst_binary(main)
    for path in app.rglob('*'):
        require(not path.is_symlink() or app in path.resolve(strict=True).parents,
                'Application symlinks must stay inside the bundle')
        require(path.is_symlink() or path.is_file() or path.is_dir(), 'Special files are not supported')
        require(path.suffix.lower() not in ('.p8', '.p12') and path.name != 'SC_Info',
                'Signing credentials or App Store encryption metadata found in input')
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / ZIP_NAME
    with tempfile.TemporaryDirectory(dir=output_dir) as temporary:
        stage = Path(temporary) / APP_NAME
        shutil.copytree(app, stage, symlinks=True)
        for path in sorted(stage.rglob('*'), key=lambda item: len(item.parts), reverse=True):
            if path.name in SIGNING_FILES or path == stage / 'Contents/PlugIns':
                if path.is_dir() and not path.is_symlink():
                    shutil.rmtree(path)
                else:
                    path.unlink()
        require(not any(path.suffix in ('.appex', '.xpc', '.app') for path in stage.rglob('*')),
                'Unexpected embedded application, extension or XPC service')
        binaries = [path for path in stage.rglob('*') if path.is_file() and not path.is_symlink() and is_macho(path)]
        nested = [path for path in stage.rglob('*') if path.is_dir() and not path.is_symlink()
                  and path.suffix in ('.framework', '.bundle') and any(path in binary.parents for binary in binaries)]
        # Sign nested code inside out, without copying the main app's sandbox entitlements into libraries.
        for target in sorted(binaries + nested, key=lambda item: (-len(item.parts), str(item))):
            command('/usr/bin/codesign', '--force', '--sign', '-', '--timestamp=none', target)
        command('/usr/bin/codesign', '--force', '--sign', '-', '--timestamp=none', '--entitlements', entitlements, stage)
        command('/usr/bin/codesign', '--verify', '--strict', '--deep', stage)
        signed = command('/usr/bin/codesign', '--display', '--entitlements', '-', '--xml', stage, capture=True)
        actual = plistlib.loads(signed)
        require(isinstance(actual, dict) and actual.keys() == requested.keys()
                and all(value is True for value in actual.values()),
                'Signed app entitlements differ from the Local Lab sandbox configuration')
        zipped = Path(temporary) / ZIP_NAME
        command('/usr/bin/ditto', '-c', '-k', '--sequesterRsrc', '--keepParent', stage, zipped)
        manifest = {'file': ZIP_NAME, 'commit': commit, 'run': run_url,
                    'bundle_id': BUNDLE, 'display_name': DISPLAY_NAME, 'architecture': 'arm64',
                    'platform': 'Mac Catalyst', 'version': info.get('CFBundleShortVersionString'),
                    'build': info.get('CFBundleVersion'), 'signing': 'ad-hoc', 'notarized': False,
                    'icloud_available': False, 'extensions_included': False, 'sandbox': True,
                    'entitlements': actual,
                    'bytes': zipped.stat().st_size, 'sha256': hashlib.sha256(zipped.read_bytes()).hexdigest()}
        report = Path(temporary) / 'manifest.json'
        report.write_text(json.dumps(manifest, indent=2) + '\n')
        zipped.replace(destination)
        report.replace(output_dir / 'manifest.json')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--entitlements', type=Path, required=True, help='Generated Mac Local Lab sandbox entitlements')
    parser.add_argument('--commit', help='Full 40-character source commit (defaults to GITHUB_SHA)')
    args = parser.parse_args()
    try:
        print(json.dumps(package(args.app, args.output_dir, args.entitlements, args.commit), indent=2))
    except (ValueError, OSError, plistlib.InvalidFileException, struct.error, subprocess.CalledProcessError) as error:
        raise SystemExit('Mac Lab packaging failed: ' + str(error))
