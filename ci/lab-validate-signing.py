#!/usr/bin/env python3
"""Fail closed on mismatched App Store profiles before a Lab upload.

Inputs are local decoded profiles. Never print their contents or certificate names.
No Apple account mutation or network access occurs here.
"""

import argparse
import datetime
import fnmatch
import hashlib
import json
from pathlib import Path
import plistlib
import re


class ValidationError(ValueError):
    """An error whose message contains configuration labels, never private values."""


def require(condition, message):
    if not condition:
        raise ValidationError(message)


def permits(allowed, requested):
    # Provisioning profiles may authorize a trailing wildcard, e.g. PREFIX.*.
    return (isinstance(allowed, str) and isinstance(requested, str)
            and not any(c in allowed for c in '?[')
            and ('*' not in allowed or allowed.endswith('*') and allowed.count('*') == 1)
            and fnmatch.fnmatchcase(requested, allowed))


def validate_profile(profile, team, bundle, certificate_sha1, now=None):
    now = now or datetime.datetime.now(datetime.timezone.utc)
    require(isinstance(profile, dict), 'Invalid provisioning profile')
    require(profile.get('TeamIdentifier') == [team], 'Profile belongs to a different developer team')
    ent = profile.get('Entitlements', {})
    require(ent.get('com.apple.developer.team-identifier') == team, 'Profile team entitlement does not match')
    prefixes = profile.get('ApplicationIdentifierPrefix', [])
    require(len(prefixes) == 1 and re.fullmatch(r'[A-Z0-9]{10}', prefixes[0]), 'Invalid App Identifier Prefix')
    prefix = prefixes[0]
    require(ent.get('application-identifier') == prefix + '.' + bundle, 'Profile App ID does not match Lab target')
    require('iOS' in profile.get('Platform', []), 'An iOS distribution profile is required')
    expires = profile.get('ExpirationDate')
    require(isinstance(expires, datetime.datetime), 'Profile expiration date is missing')
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=datetime.timezone.utc)
    require(expires > now, 'Provisioning profile has expired')
    require(not ent.get('get-task-allow', False), 'A development/Personal Team profile cannot upload to TestFlight')
    require('ProvisionedDevices' not in profile and not profile.get('ProvisionsAllDevices', False),
            'Use App Store Connect profiles, not Ad Hoc or enterprise profiles')
    require(ent.get('beta-reports-active') is True, 'An App Store Connect distribution profile is required')
    certificates = profile.get('DeveloperCertificates', [])
    require(any(isinstance(c, bytes) and hashlib.sha1(c).hexdigest().upper() == certificate_sha1 for c in certificates),
            'Signing certificate is not authorized by this provisioning profile')
    uuid = profile.get('UUID', '')
    require(isinstance(uuid, str) and re.fullmatch(r'[0-9A-Fa-f]{8}(?:-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}', uuid),
            'Invalid provisioning profile UUID')
    return {'uuid': uuid, 'prefix': prefix, 'entitlements': ent}


def validate_cloud(ent, authorized, prefix, bundle, container):
    require(ent.get('com.apple.developer.icloud-container-identifiers') == [container],
            'Lab must use exactly its own iCloud container')
    require(ent.get('com.apple.developer.ubiquity-container-identifiers') == [container],
            'Lab must use exactly its own iCloud Documents container')
    require(ent.get('com.apple.developer.icloud-services') == ['CloudDocuments'],
            'Lab requests only iCloud Documents')
    expected_store = prefix + '.' + bundle
    store = ent.get('com.apple.developer.ubiquity-kvstore-identifier', '')
    store = store.replace('$(TeamIdentifierPrefix)', prefix + '.').replace('$(CFBundleIdentifier)', bundle)
    require(store == expected_store, 'Lab KVS identifier does not match its App Identifier Prefix and bundle')
    for key in ('com.apple.developer.icloud-container-identifiers',
                'com.apple.developer.ubiquity-container-identifiers', 'com.apple.developer.icloud-services'):
        allowed = authorized.get(key, [])
        require(isinstance(allowed, list) and all(any(permits(a, v) for a in allowed) for v in ent[key]),
                'Provisioning profile does not authorize the requested iCloud service/container')
    require(permits(authorized.get('com.apple.developer.ubiquity-kvstore-identifier'), expected_store),
            'Provisioning profile does not authorize the requested iCloud KVS store')
    blocked = ('aps-environment', 'com.apple.developer.carplay-maps',
               'com.apple.developer.navigation-app', 'com.apple.developer.associated-domains')
    require(not any(k in ent for k in blocked), 'Lab still requests an official CoMaps service or managed capability')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app-profile', required=True, type=Path)
    parser.add_argument('--widget-profile', required=True, type=Path)
    parser.add_argument('--entitlements', required=True, type=Path)
    parser.add_argument('--team', required=True)
    parser.add_argument('--bundle', required=True)
    parser.add_argument('--container', required=True)
    parser.add_argument('--certificate-sha1', required=True)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--archive-info', type=Path)
    parser.add_argument('--widget-info', type=Path)
    parser.add_argument('--widget-entitlements', type=Path)
    args = parser.parse_args()
    require(re.fullmatch(r'[A-Z0-9]{10}', args.team), 'LAB_TEAM_ID must have 10 uppercase letters/digits')
    require(re.fullmatch(r'[A-F0-9]{40}', args.certificate_sha1), 'Invalid signing certificate fingerprint')
    app = validate_profile(plistlib.loads(args.app_profile.read_bytes()), args.team, args.bundle, args.certificate_sha1)
    widget = validate_profile(plistlib.loads(args.widget_profile.read_bytes()), args.team,
                              args.bundle + '.widgetextension', args.certificate_sha1)
    require(widget['prefix'] == app['prefix'], 'App and widget profiles must share the same App Identifier Prefix')
    ent = plistlib.loads(args.entitlements.read_bytes())
    validate_cloud(ent, app['entitlements'], app['prefix'], args.bundle, args.container)
    if args.archive_info or args.widget_info:
        require(args.archive_info and args.widget_info and args.widget_entitlements,
                'Both archive Info.plist paths and widget entitlements are required')
        app_info = plistlib.loads(args.archive_info.read_bytes())
        widget_info = plistlib.loads(args.widget_info.read_bytes())
        require(app_info.get('CFBundleIdentifier') == args.bundle, 'Archived app is not CoMaps Lab')
        require(widget_info.get('CFBundleIdentifier') == args.bundle + '.widgetextension', 'Archived widget is not CoMaps Lab')
        require(app_info.get('CFBundleVersion') == widget_info.get('CFBundleVersion'), 'App/widget build numbers differ')
        for actual, profile in [(ent, app), (plistlib.loads(args.widget_entitlements.read_bytes()), widget)]:
            require(actual.get('application-identifier') == profile['entitlements']['application-identifier'],
                    'Archived target App ID does not match its provisioning profile')
            require(actual.get('com.apple.developer.team-identifier') == args.team,
                    'Archived target team entitlement does not match')
            require(not actual.get('get-task-allow', False), 'Archived target is still signed for development')
    args.output.write_text(json.dumps({'app_uuid': app['uuid'], 'widget_uuid': widget['uuid']}) + '\n')
    print('Lab signing profiles and isolated iCloud entitlements validated.')


if __name__ == '__main__':
    try:
        main()
    except ValidationError as error:
        raise SystemExit('Lab signing validation failed: ' + str(error))
    except (ValueError, KeyError, TypeError, OSError, plistlib.InvalidFileException):
        # Deliberately do not dump private provisioning data or certificate details.
        raise SystemExit('Lab signing validation failed. Check the team, App Store profiles, certificate, expiration and Lab iCloud permissions locally.')
