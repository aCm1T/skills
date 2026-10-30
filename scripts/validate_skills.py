#!/usr/bin/env python3
"""Validate tracked skill files without executing skills or contacting services."""

import argparse
import ast
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit

from markdown_it import MarkdownIt
import yaml


class UniqueLoader(yaml.SafeLoader):
    """Reject duplicate keys rather than silently using the last value."""


def unique_mapping(loader, node):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node)
        if key in result:
            raise ValueError('duplicate YAML key')
        result[key] = loader.construct_object(value_node)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)
NAME = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*\Z')
RESERVED = {'scripts', 'tests', 'docs'}
ALLOWLIST = '.skill-scan-allowlist.json'
PRIVATE_PATH = re.compile(r'(?:/home/|/Users/|[A-Za-z]:[\\/]Users[\\/])[A-Za-z0-9_.-]+')
SECRET_PATTERNS = {
    'private-key': re.compile(r'-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----'),
    'github-token': re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9]{36,255}|github_pat_[A-Za-z0-9_]{40,255})\b'),
    'aws-key': re.compile(r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b'),
    'credential-literal': re.compile(
        r'''(?i)\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|password|session(?:id|_id)?)\b["']?\s*[:=]\s*["']([A-Za-z0-9_./+=-]{16,})["']'''),
}


@dataclass(frozen=True)
class Issue:
    path: str
    rule: str
    line: int = 0

    def __str__(self):
        # Never include source lines or matched values: they may be credentials.
        return f'{self.path}:{self.line}: {self.rule}'


def links(text):
    """CommonMark inline links, images, and resolved reference-style links."""
    def walk(tokens):
        for token in tokens:
            if token.type == 'link_open':
                yield token.attrGet('href')
            elif token.type == 'image':
                yield token.attrGet('src')
            if token.children:
                yield from walk(token.children)
    return list(walk(MarkdownIt('commonmark').parse(text)))


def local_target(root, source, url):
    """Return repository-relative path, None for remote/anchor-only links."""
    parsed = urlsplit(url)
    if parsed.scheme or parsed.netloc:
        return None
    decoded = unquote(parsed.path)
    if not decoded:
        return None
    if decoded.startswith('/') or '\\' in decoded:
        raise ValueError('absolute or nonportable link')
    target = (root / source).parent.joinpath(decoded).resolve()
    return target.relative_to(root.resolve()).as_posix()


def load_yaml(text):
    return yaml.load(text, Loader=UniqueLoader)


def validate(root, paths):
    root = root.resolve()
    paths = set(paths)
    issues = []
    texts = {}
    def fail(path, rule, line=0):
        issues.append(Issue(path, rule, line))

    # Refuse symlinks before reading any file contents.
    for path in sorted(paths):
        candidate = root / path
        if any(part.is_symlink() for part in [candidate, *candidate.parents] if part != root):
            fail(path, 'symlink-not-allowed')
            continue
        parts = PurePosixPath(path).parts
        base = parts[-1].lower()
        if (base in {'cookies.json', 'session.json', 'sessions.json', 'credentials.json', '.env'}
                or (base.startswith('.env.') and base != '.env.example')
                or base.endswith(('.pem', '.key', '.pyc'))
                or base in {'id_rsa', 'id_ed25519'}
                or any(p in {'.venv', 'venv', '__pycache__', '.cache', 'node_modules'} for p in parts)):
            fail(path, 'runtime-or-credential-file')
        try:
            texts[path] = candidate.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            # Images and other assets need manual privacy/content review.
            continue
        except OSError:
            fail(path, 'tracked-file-unreadable')

    dirs = {p.split('/')[0] for p in paths if '/' in p and not p.startswith('.')}
    skills = sorted(dirs - RESERVED)
    if not skills:
        fail('.', 'no-skills-found')
    for skill in skills:
        entry = skill + '/SKILL.md'
        text = texts.get(entry)
        if not text:
            fail(entry, 'missing-skill-entrypoint')
            continue
        if not NAME.fullmatch(skill) or len(skill) >= 64:
            fail(entry, 'invalid-directory-name')
        lines = text.splitlines()
        try:
            if not lines or lines[0] != '---':
                raise ValueError('missing frontmatter')
            end = lines.index('---', 1)
            metadata = load_yaml('\n'.join(lines[1:end]))
            if not isinstance(metadata, dict):
                raise ValueError('not mapping')
            for field in ('name', 'description'):
                if not isinstance(metadata.get(field), str) or not metadata[field].strip():
                    fail(entry, 'missing-or-invalid-' + field)
            if metadata.get('name') != skill:
                fail(entry, 'name-directory-mismatch')
            if not '\n'.join(lines[end + 1:]).strip():
                fail(entry, 'empty-instructions')
        except (ValueError, TypeError, yaml.YAMLError):
            fail(entry, 'invalid-frontmatter')

        ui_path = skill + '/agents/openai.yaml'
        if ui_path in paths:
            try:
                ui = load_yaml(texts.get(ui_path, ''))
                if not isinstance(ui, dict):
                    raise ValueError('not mapping')
                interface = ui.get('interface', {})
                if not isinstance(interface, dict):
                    raise ValueError('invalid interface')
                for field in ('display_name', 'short_description', 'default_prompt', 'icon_small', 'icon_large', 'brand_color'):
                    value = interface.get(field)
                    if field in interface and (not isinstance(value, str) or not value.strip()):
                        raise ValueError('invalid interface value')
                prompt = interface.get('default_prompt', '')
                if prompt and not re.search(r'\$' + re.escape(skill) + r'(?![a-z0-9-])', prompt):
                    fail(ui_path, 'default-prompt-skill-mismatch')
                for field in ('icon_small', 'icon_large'):
                    if field in interface:
                        target = local_target(root, skill + '/SKILL.md', interface[field])
                        if (not target or not target.startswith(skill + '/') or target not in texts and target not in paths):
                            fail(ui_path, 'missing-or-invalid-icon')
            except (ValueError, TypeError, yaml.YAMLError):
                fail(ui_path, 'invalid-ui-yaml')

    readme_links = set()
    for path, text in sorted(texts.items()):
        if path.endswith('.md'):
            for url in links(text):
                try:
                    target = local_target(root, path, url)
                    if target is None:
                        continue
                    if target not in paths and not any(p.startswith(target.rstrip('/') + '/') for p in paths):
                        fail(path, 'missing-link-target')
                    owner = path.split('/')[0]
                    if owner in skills and target != owner and not target.startswith(owner + '/'):
                        fail(path, 'link-outside-skill')
                    if path == 'README.md':
                        readme_links.add(target)
                except ValueError:
                    fail(path, 'invalid-local-link')
        if path.endswith('.py'):
            try:
                ast.parse(text, filename=path)
            except SyntaxError as exc:
                fail(path, 'python-syntax', exc.lineno or 0)
    if 'README.md' not in texts:
        fail('README.md', 'missing-readme')
    for skill in skills:
        if skill + '/SKILL.md' not in readme_links:
            fail('README.md', 'missing-index-' + skill)

    exceptions = {}
    if ALLOWLIST in paths:
        try:
            entries = json.loads(texts[ALLOWLIST])
            if not isinstance(entries, list):
                raise ValueError('not list')
            for item in entries:
                if not isinstance(item, dict) or set(item) != {'path', 'rule', 'line_sha256', 'reason'}:
                    raise ValueError('invalid fields')
                if not all(isinstance(v, str) and v.strip() for v in item.values()):
                    raise ValueError('invalid values')
                if item['path'] not in paths or item['rule'] not in {*SECRET_PATTERNS, 'private-user-path'}:
                    raise ValueError('unknown path or rule')
                if not re.fullmatch(r'[0-9a-f]{64}', item['line_sha256']):
                    raise ValueError('invalid fingerprint')
                key = (item['path'], item['rule'], item['line_sha256'])
                if key in exceptions:
                    raise ValueError('duplicate exception')
                exceptions[key] = False
        except (ValueError, KeyError, TypeError):
            fail(ALLOWLIST, 'invalid-scan-allowlist')
            exceptions = {}
    for path, text in sorted(texts.items()):
        for number, line in enumerate(text.splitlines(), 1):
            findings = {rule for rule, pattern in SECRET_PATTERNS.items() if pattern.search(line)}
            # Generic examples must use placeholders, not a concrete user's path.
            if PRIVATE_PATH.search(line):
                findings.add('private-user-path')
            for rule in findings:
                key = (path, rule, hashlib.sha256(line.encode('utf-8')).hexdigest())
                if key in exceptions:
                    exceptions[key] = True
                else:
                    fail(path, rule, number)
    for key, used in exceptions.items():
        if not used:
            fail(ALLOWLIST, 'stale-scan-exception')
    return issues, skills


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    try:
        result = subprocess.run(['git', '-C', str(args.root), 'ls-files', '-z'],
                                capture_output=True, check=True)
        paths = [p for p in result.stdout.decode('utf-8').split('\0') if p]
    except (OSError, subprocess.CalledProcessError, UnicodeDecodeError):
        print('Cannot enumerate Git-tracked files; run inside a Git checkout.', file=sys.stderr)
        return 2
    issues, skills = validate(args.root, paths)
    for issue in sorted(issues, key=lambda i: (i.path, i.line, i.rule)):
        print(issue)
    print(f'{len(skills)} skills; {len(paths)} tracked files; {len(issues)} issues. '
          'Scope: structure, file links, Python syntax, and selected privacy patterns; '
          'human review is still required.')
    return 1 if issues else 0


if __name__ == '__main__':
    sys.exit(main())
