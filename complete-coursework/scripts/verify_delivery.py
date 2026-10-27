#!/usr/bin/env python3
"""Audit requested local files and ZIPs; never execute or extract their contents."""

import argparse
import hashlib
import json
import ntpath
from pathlib import Path
import stat
import sys
import zipfile
import zlib


def digest(stream):
    result = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b''):
        result.update(chunk)
    return result.hexdigest()


def local_path(root, value):
    candidate = Path(value)
    if candidate.is_absolute():
        raise ValueError('Use a path relative to --root: ' + value)
    candidate = (root / candidate).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        raise ValueError('Path escapes --root: ' + value) from None
    return candidate


def member_problem(info):
    name = info.filename
    parts = name.rstrip('/').split('/')
    if (not name or name.startswith('/') or '\\' in name
            or ntpath.splitdrive(name)[0]
            or any(part in ('', '.', '..') for part in parts)):
        return 'unsafe archive path: ' + repr(name)
    if stat.S_ISLNK(info.external_attr >> 16):
        return 'symbolic link in archive: ' + repr(name)
    if info.flag_bits & 1:
        return 'encrypted archive entry cannot be verified: ' + repr(name)
    return None


def parse_match(value):
    try:
        left, local = value.rsplit('=', 1)
        archive, member = left.split('::', 1)
    except ValueError:
        raise ValueError('Expected ZIP::MEMBER=LOCAL_FILE: ' + value) from None
    if not archive or not member or not local:
        raise ValueError('Expected ZIP::MEMBER=LOCAL_FILE: ' + value)
    return archive, member, local


def run_checks(root, requested_files, requested_archives, matches):
    files = list(dict.fromkeys(requested_files + requested_archives
                               + [m[0] for m in matches] + [m[2] for m in matches]))
    archives = list(dict.fromkeys(requested_archives + [m[0] for m in matches]))
    report = {'schema_version': 1, 'scope': 'file and archive integrity only',
              'passed': False, 'files': {}, 'archives': {}, 'matches': [], 'errors': []}
    for name in files:
        try:
            path = local_path(root, name)
            if not path.is_file() or path.stat().st_size == 0:
                raise ValueError('Required file is missing, not a file, or empty')
            with path.open('rb') as stream:
                sha = digest(stream)
            report['files'][name] = {'bytes': path.stat().st_size, 'sha256': sha}
        except (OSError, ValueError) as exc:
            report['errors'].append(name + ': ' + str(exc))

    for name in archives:
        if name not in report['files']:
            continue
        try:
            with zipfile.ZipFile(local_path(root, name)) as archive:
                infos = archive.infolist()
                if not infos or not any(not i.is_dir() for i in infos):
                    raise ValueError('Archive has no files')
                seen = set()
                for info in infos:
                    problem = member_problem(info)
                    if problem:
                        raise ValueError(problem)
                    key = info.filename.rstrip('/')
                    if key in seen:
                        raise ValueError('Duplicate archive entry: ' + repr(key))
                    seen.add(key)
                file_names = {i.filename.rstrip('/') for i in infos if not i.is_dir()}
                for info in infos:
                    parts = info.filename.rstrip('/').split('/')
                    if any('/'.join(parts[:i]) in file_names for i in range(1, len(parts))):
                        raise ValueError('File/directory path conflict: ' + repr(info.filename))
                bad_member = archive.testzip()
                if bad_member is not None:
                    raise ValueError('CRC failure: ' + repr(bad_member))
                report['archives'][name] = {
                    'entries': len(infos), 'files': sum(not i.is_dir() for i in infos),
                    'crc_ok': True, 'member_paths_ok': True}
        except (OSError, ValueError, RuntimeError, zipfile.BadZipFile,
                NotImplementedError, zlib.error, EOFError) as exc:
            report['errors'].append(name + ': ' + str(exc))

    for archive_name, member, local in matches:
        if archive_name not in report['archives'] or local not in report['files']:
            report['errors'].append('Cannot compare unverified inputs: '
                                    + archive_name + '::' + member + '=' + local)
            continue
        try:
            with zipfile.ZipFile(local_path(root, archive_name)) as archive:
                info = archive.getinfo(member)
                if info.is_dir():
                    raise ValueError('Expected a file, found a directory')
                with archive.open(info) as stream:
                    archived_sha = digest(stream)
            matched = archived_sha == report['files'][local]['sha256']
            report['matches'].append({'archive': archive_name, 'member': member,
                                      'local_file': local, 'identical': matched})
            if not matched:
                report['errors'].append('Content mismatch: '
                                        + archive_name + '::' + member + '=' + local)
        except (OSError, ValueError, KeyError, RuntimeError, zipfile.BadZipFile,
                zlib.error, EOFError) as exc:
            report['errors'].append(archive_name + '::' + member + ': ' + str(exc))
    report['passed'] = not report['errors']
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default='.', help='Root directory of this assignment')
    parser.add_argument('--file', action='append', default=[], dest='files')
    parser.add_argument('--zip', action='append', default=[], dest='archives')
    parser.add_argument('--match', action='append', default=[], metavar='ZIP::MEMBER=FILE')
    parser.add_argument('--report', help='Optional JSON report path relative to --root')
    args = parser.parse_args(argv)
    if not (args.files or args.archives or args.match):
        parser.error('Specify at least one --file, --zip, or --match')
    root = Path(args.root).resolve()
    if not root.is_dir():
        parser.error('--root must be an existing directory')
    try:
        matches = [parse_match(value) for value in args.match]
        report_path = local_path(root, args.report) if args.report else None
        if report_path:
            protected = args.files + args.archives + [m[0] for m in matches] + [m[2] for m in matches]
            if report_path in {local_path(root, value) for value in protected}:
                raise ValueError('Report must not overwrite an audited file')
            if not report_path.parent.is_dir():
                raise ValueError('Report parent directory must already exist')
    except ValueError as exc:
        parser.error(str(exc))
    report = run_checks(root, args.files, args.archives, matches)
    serialized = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    if report_path:
        try:
            report_path.write_text(serialized, encoding='utf-8')
        except OSError as exc:
            print('Could not write report: ' + str(exc), file=sys.stderr)
            return 1
    print(serialized, end='')
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
