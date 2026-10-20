#!/usr/bin/env python3
"""Package only CoMaps Lab Local for subsequent user-controlled re-signing.

This never signs, installs or uploads an app and never changes the source archive.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import stat
import struct
import tempfile
import zipfile
from urllib.parse import urlsplit

BUNDLE = 'com.pvlgrdv.comapslab.local'
DISPLAY_NAME = 'CoMaps Lab Local'
IPA_NAME = 'CoMaps-Lab-Local-unsigned.ipa'
SIGNING_FILES = {'_CodeSignature', 'CodeResources', 'embedded.mobileprovision'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check_device_binary(path):
    """Read Mach-O load commands; reject simulator or FairPlay-encrypted input."""
    data = path.read_bytes()

    def thin(offset, size):
        require(size >= 32 and offset + size <= len(data), 'Truncated executable')
        magic = data[offset:offset + 4]
        require(magic in (b'\xcf\xfa\xed\xfe', b'\xfe\xed\xfa\xcf'), 'Expected a 64-bit Mach-O executable')
        endian = '<' if magic == b'\xcf\xfa\xed\xfe' else '>'
        cpu, _, _, count, command_bytes = struct.unpack_from(endian + 'IIIII', data, offset + 4)
        require(cpu == 0x0100000C, 'Expected an arm64 iOS device executable')
        position = offset + 32
        end = position + command_bytes
        require(end <= offset + size and count <= command_bytes // 8, 'Invalid executable load commands')
        ios = False
        for _ in range(count):
            require(position + 8 <= end, 'Truncated load command')
            command, length = struct.unpack_from(endian + 'II', data, position)
            require(length >= 8 and position + length <= end, 'Invalid load command size')
            if command in (0x21, 0x2C):  # LC_ENCRYPTION_INFO / LC_ENCRYPTION_INFO_64
                require(length >= 20 and struct.unpack_from(endian + 'I', data, position + 16)[0] == 0,
                        'FairPlay-encrypted applications cannot be packaged')
            if command == 0x32:  # LC_BUILD_VERSION
                require(length >= 24, 'Invalid platform command')
                ios = struct.unpack_from(endian + 'I', data, position + 8)[0] == 2
            elif command == 0x25:  # LC_VERSION_MIN_IPHONEOS
                ios = True
            position += length
        require(position == end and ios, 'Expected an iOS device build, not a simulator or Mac build')

    if data[:4] in (b'\xca\xfe\xba\xbe', b'\xca\xfe\xba\xbf'):
        require(len(data) >= 8, 'Truncated universal executable')
        count = struct.unpack_from('>I', data, 4)[0]
        arch_size = 32 if data[:4] == b'\xca\xfe\xba\xbf' else 20
        require(0 < count <= 16 and 8 + count * arch_size <= len(data), 'Invalid universal executable')
        for i in range(count):
            entry = 8 + i * arch_size
            offset, size = struct.unpack_from('>QQ' if arch_size == 32 else '>II', data, entry + 8)
            thin(offset, size)
    else:
        thin(0, len(data))


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
                'GitHub repository/run provenance is incomplete or invalid')
        run_url = server.rstrip('/') + '/' + repository + '/actions/runs/' + run_id
    return commit.lower(), run_url


def package(archive, output_dir, commit=None):
    commit, run_url = provenance(commit)
    archive, output_dir = Path(archive).resolve(), Path(output_dir).resolve()
    require(archive.is_dir() and archive.suffix == '.xcarchive', 'An Xcode source-build .xcarchive is required')
    require(output_dir != archive and archive not in output_dir.parents, 'Output must be outside the source archive')
    app = archive / 'Products/Applications/CoMaps.app'
    require(app.is_dir() and not app.is_symlink(), 'Expected Products/Applications/CoMaps.app')
    require(archive in app.resolve().parents and not (app / 'Info.plist').is_symlink(),
            'Archive application paths must not escape through symlinks')
    info = plistlib.loads((app / 'Info.plist').read_bytes())
    require(info.get('CFBundleIdentifier') == BUNDLE, 'Refusing to package a non-local application')
    require(info.get('CFBundleDisplayName') == DISPLAY_NAME, 'Expected the CoMaps Lab Local display name')
    require(info.get('CoMapsLabLocalOnly') is True, 'The explicit local-only build marker is missing')
    require('NSUbiquitousContainers' not in info, 'Local Lab must not declare iCloud containers')
    require(not any('icloud' in key.lower() for key in info), 'Local Lab still declares an iCloud setting')
    executable = info.get('CFBundleExecutable')
    require(isinstance(executable, str) and executable not in ('', '.', '..') and '/' not in executable,
            'Invalid main executable name')
    require(not (app / executable).is_symlink(), 'Executable symlinks are not supported')
    require((app / executable).stat().st_mode & stat.S_IXUSR, 'Main executable is not executable')
    check_device_binary(app / executable)
    files = []
    for path in sorted(app.rglob('*')):
        relative = path.relative_to(app)
        if relative.parts[0] == 'PlugIns' or any(p in SIGNING_FILES for p in relative.parts):
            continue
        require(not path.is_symlink(), 'Symlinks are not supported in Local Lab packages')
        require('SC_Info' not in relative.parts and path.suffix.lower() not in ('.sinf', '.p12', '.p8', '.mobileprovision'),
                'App Store encryption metadata or signing credentials found in input')
        if path.is_file():
            files.append((path, relative))
        else:
            require(path.is_dir(), 'Special files are not supported')
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / IPA_NAME
    with tempfile.TemporaryDirectory(dir=output_dir) as staging:
        temporary = Path(staging) / IPA_NAME
        with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as zipped:
            for path, relative in files:
                entry = zipfile.ZipInfo('Payload/CoMaps.app/' + relative.as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
                entry.create_system = 3
                entry.external_attr = (stat.S_IFREG | stat.S_IMODE(path.stat().st_mode)) << 16
                entry.compress_type = zipfile.ZIP_DEFLATED
                zipped.writestr(entry, path.read_bytes())
        temporary.replace(destination)
    manifest = {'file': IPA_NAME, 'commit': commit, 'run': run_url,
                'bundle_id': BUNDLE, 'display_name': DISPLAY_NAME,
                'version': info.get('CFBundleShortVersionString'), 'build': info.get('CFBundleVersion'),
                'unsigned': True, 'requires_resigning': True, 'icloud_available': False,
                'scope': 'Local-only search and sorting; no live iCloud synchronization.',
                'excluded': ['PlugIns', '_CodeSignature', 'CodeResources', 'embedded.mobileprovision'],
                'bytes': destination.stat().st_size,
                'sha256': hashlib.sha256(destination.read_bytes()).hexdigest()}
    with tempfile.TemporaryDirectory(dir=output_dir) as staging:
        temporary = Path(staging) / 'manifest.json'
        temporary.write_text(json.dumps(manifest, indent=2) + '\n')
        temporary.replace(output_dir / 'manifest.json')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--commit', help='Full 40-character source commit (defaults to GITHUB_SHA)')
    args = parser.parse_args()
    try:
        print(json.dumps(package(args.archive, args.output_dir, args.commit), indent=2))
    except (ValueError, OSError, plistlib.InvalidFileException, struct.error) as error:
        raise SystemExit('Local IPA packaging failed: ' + str(error))
