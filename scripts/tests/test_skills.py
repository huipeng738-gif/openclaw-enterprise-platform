"""验证 Skill 部署不会覆盖已有文件，并保持重复执行幂等。"""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from install_skills import install


class SkillInstallTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.manifest = self.root / 'openclaw.plugin.json'
        self.original = {'id': 'enterprise-data-tools', 'skills': ['./existing'],
                         'contracts': {'tools': ['knowledge_search']},
                         'configSchema': {'type': 'object'}}
        self.manifest.write_text(json.dumps(self.original), encoding='utf-8')

    def test_preflight_does_not_write(self):
        before = self.manifest.read_bytes()
        install(self.root)
        self.assertEqual(self.manifest.read_bytes(), before)
        self.assertFalse((self.root / 'skills').exists())

    def test_install_preserves_fields_and_is_idempotent(self):
        original_bytes = self.manifest.read_bytes()
        install(self.root, apply=True)
        installed = json.loads(self.manifest.read_text(encoding='utf-8'))
        self.assertEqual(installed['skills'], ['./existing', './skills'])
        for key in ('id', 'contracts', 'configSchema'):
            self.assertEqual(installed[key], self.original[key])
        self.assertEqual((self.root / 'openclaw.plugin.before-skills.json').read_bytes(), original_bytes)
        self.assertTrue((self.root / 'skills/enterprise-document-draft/references/draft-templates.md').is_file())
        before = {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob('*') if path.is_file()}
        install(self.root, apply=True)
        after = {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob('*') if path.is_file()}
        self.assertEqual(before, after)

    def test_conflict_stops_before_writing(self):
        existing = self.root / 'skills/enterprise-document-draft/SKILL.md'
        existing.parent.mkdir(parents=True)
        existing.write_text('user content', encoding='utf-8')
        before = self.manifest.read_bytes()
        with self.assertRaises(RuntimeError):
            install(self.root, apply=True)
        self.assertEqual(existing.read_text(encoding='utf-8'), 'user content')
        self.assertFalse((self.root / 'skills/enterprise-knowledge-qa').exists())
        self.assertEqual(self.manifest.read_bytes(), before)

    def test_wrong_plugin_is_rejected(self):
        self.manifest.write_text('{"id":"another-plugin"}', encoding='utf-8')
        with self.assertRaises(RuntimeError):
            install(self.root, apply=True)
        self.assertFalse((self.root / 'skills').exists())


if __name__ == '__main__':
    unittest.main()
