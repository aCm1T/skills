"""Synthetic repository fixtures; no service accounts or private source files."""

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('validate_skills', ROOT / 'scripts/validate_skills.py')
validator = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = validator
spec.loader.exec_module(validator)


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.files = {
            'README.md': '[Demo](demo/SKILL.md)\n',
            'demo/SKILL.md': '---\nname: demo\ndescription: Test synthetic files.\n---\n# Demo\n\nFollow the request.\n',
        }

    def run_check(self):
        for name, text in self.files.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding='utf-8')
        return validator.validate(self.root, self.files)[0]

    def rules(self):
        return {i.rule for i in self.run_check()}

    def test_valid_minimal_skill(self):
        self.assertEqual(self.run_check(), [])

    def test_renamed_skill_rejected(self):
        self.files['demo/SKILL.md'] = self.files['demo/SKILL.md'].replace('name: demo', 'name: other')
        self.assertIn('name-directory-mismatch', self.rules())

    def test_yaml_duplicate_key_rejected(self):
        self.files['demo/SKILL.md'] = self.files['demo/SKILL.md'].replace('name: demo', 'name: demo\nname: other')
        self.assertIn('invalid-frontmatter', self.rules())

    def test_missing_description_rejected(self):
        self.files['demo/SKILL.md'] = self.files['demo/SKILL.md'].replace('description: Test synthetic files.', 'description: []')
        self.assertIn('missing-or-invalid-description', self.rules())

    def test_empty_body_rejected(self):
        self.files['demo/SKILL.md'] = '---\nname: demo\ndescription: Demo\n---\n'
        self.assertIn('empty-instructions', self.rules())

    def test_unindexed_skill_rejected(self):
        self.files['README.md'] = '# Index\n'
        self.assertIn('missing-index-demo', self.rules())

    def test_missing_entrypoint_rejected(self):
        self.files['orphan/references/info.md'] = 'Example\n'
        self.assertIn('missing-skill-entrypoint', self.rules())

    def test_commonmark_links_images_and_references(self):
        self.files['demo/SKILL.md'] += '\n[Guide][ref]\n\n[ref]: <references/a%20b.md> "Guide"\n\n![Image](assets/icon.svg)\n'
        self.files['demo/references/a b.md'] = '# Guide\n'
        self.files['demo/assets/icon.svg'] = '<svg/>\n'
        self.assertEqual(self.run_check(), [])
        del self.files['demo/references/a b.md']
        self.assertIn('missing-link-target', self.rules())

    def test_broken_link_inside_code_is_not_a_link(self):
        self.files['demo/SKILL.md'] += '\n```md\n[Example](missing.md)\n```\n'
        self.assertEqual(self.run_check(), [])

    def test_untracked_target_rejected(self):
        self.files['demo/SKILL.md'] += '\n[Guide](guide.md)\n'
        (self.root / 'demo').mkdir()
        (self.root / 'demo/guide.md').write_text('Not staged', encoding='utf-8')
        self.assertIn('missing-link-target', self.rules())

    def test_links_cannot_escape_skill_or_repository(self):
        self.files['demo/SKILL.md'] += '\n[Other](../README.md)\n[Escape](../../outside.md)\n'
        self.assertTrue({'link-outside-skill', 'invalid-local-link'} <= self.rules())

    def test_public_address_and_generic_session_code_allowed(self):
        self.files['demo/SKILL.md'] += '\nhttps://bb.cuhk.edu.cn\n`cookies.json`; `session = get_session()`\n'
        self.assertEqual(self.run_check(), [])

    def test_sensitive_filename_rejected(self):
        self.files['demo/cookies.json'] = '{}\n'
        self.assertIn('runtime-or-credential-file', self.rules())

    def test_runtime_and_example_env(self):
        self.files['.env.example'] = 'BB_BASE_URL=https://bb.cuhk.edu.cn\n'
        self.assertEqual(self.run_check(), [])
        self.files['demo/.venv/info.txt'] = 'Runtime\n'
        self.assertIn('runtime-or-credential-file', self.rules())

    def test_known_token_is_detected_without_disclosing_value(self):
        fake = 'gh' + 'p_' + 'X' * 36
        self.files['demo/leak.txt'] = fake
        issues = self.run_check()
        self.assertIn('github-token', {i.rule for i in issues})
        self.assertNotIn(fake, '\n'.join(map(str, issues)))

    def test_private_path_and_literal_detected(self):
        self.files['demo/leak.txt'] = '/home/' + 'example-person/private\n' + 'api_key = "' + 'A' * 24 + '"\n'
        self.assertTrue({'private-user-path', 'credential-literal'} <= self.rules())

    def test_exact_exception_and_stale_detection(self):
        line = 'gh' + 'p_' + 'X' * 36
        self.files['demo/example.txt'] = line + '\n'
        self.files[validator.ALLOWLIST] = json.dumps([{
            'path': 'demo/example.txt', 'rule': 'github-token',
            'line_sha256': hashlib.sha256(line.encode()).hexdigest(),
            'reason': 'Synthetic unusable test value reviewed by a maintainer.',
        }])
        self.assertEqual(self.run_check(), [])
        self.files['demo/example.txt'] = 'Changed\n'
        self.assertIn('stale-scan-exception', self.rules())

    def test_broad_exception_rejected(self):
        self.files[validator.ALLOWLIST] = '[{"path": "*"}]'
        self.assertIn('invalid-scan-allowlist', self.rules())

    def test_ui_prompt_and_icon(self):
        self.files['demo/agents/openai.yaml'] = 'interface:\n  default_prompt: "Use $demo to help."\n  icon_small: "./assets/icon.svg"\n'
        self.files['demo/assets/icon.svg'] = '<svg/>\n'
        self.assertEqual(self.run_check(), [])
        self.files['demo/agents/openai.yaml'] = 'interface:\n  default_prompt: "Use $demo-other."\n  icon_small: "https://example.com/icon.svg"\n'
        self.assertTrue({'default-prompt-skill-mismatch', 'missing-or-invalid-icon'} <= self.rules())

    def test_python_syntax_error(self):
        self.files['demo/scripts/helper.py'] = 'def broken(\n'
        self.assertIn('python-syntax', self.rules())

    def test_symlink_not_read(self):
        (self.root / 'demo').mkdir()
        (self.root / 'demo/link.md').symlink_to(self.root / 'outside')
        self.files['demo/link.md'] = None
        for name, text in self.files.items():
            if text is not None:
                path = self.root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding='utf-8')
        issues, _ = validator.validate(self.root, self.files)
        self.assertIn('symlink-not-allowed', {i.rule for i in issues})

    def test_cli_returns_failure_for_staged_broken_skill(self):
        self.files['demo/SKILL.md'] += '\n[Broken](missing.md)\n'
        self.run_check()
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        subprocess.run(['git', '-C', str(self.root), 'add', '.'], check=True)
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/validate_skills.py'), '--root', str(self.root)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn('missing-link-target', result.stdout)


if __name__ == '__main__':
    unittest.main()
