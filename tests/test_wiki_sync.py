"""Verify wiki ownership and safe removal of obsolete generated pages."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('sync_wiki', Path(__file__).resolve().parents[1] / 'scripts/sync_wiki.py')
wiki = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wiki)


class WikiSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.source = root / 'source'
        self.destination = root / 'wiki'
        self.source.mkdir()
        self.destination.mkdir()
        self.git('init', '-q')
        self.git('config', 'user.name', 'Documentation test')
        self.git('config', 'user.email', 'test@example.org')
        self.git('remote', 'add', 'origin', sorted(wiki.REMOTES)[0])
        self.git('commit', '--allow-empty', '-qm', 'Initialize')

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.destination), *args], text=True)

    def source_files(self, files):
        for name, text in files.items():
            (self.source / name).write_text(text)
        (self.source / '.generated.json').write_text(json.dumps({'source_ref': 'a' * 40, 'files': list(files)}))

    def save(self):
        self.git('add', '.')
        self.git('commit', '-qm', 'Generated pages')

    def test_owned_removal_preserves_manual_pages_and_preview_does_not_write(self):
        (self.destination / 'Manual.md').write_text('Manual notes')
        self.save()
        self.source_files({'Home.md': 'Home', 'Old.md': 'Old'})
        plan = wiki.synchronize(self.source, self.destination)
        self.assertEqual(plan['write'], ['Home.md', 'Old.md'])
        self.assertFalse((self.destination / 'Home.md').exists())
        wiki.synchronize(self.source, self.destination, True)
        self.save()
        self.source_files({'Home.md': 'New home'})
        plan = wiki.synchronize(self.source, self.destination, True)
        self.assertEqual(plan['remove'], ['Old.md'])
        self.assertFalse((self.destination / 'Old.md').exists())
        self.assertEqual((self.destination / 'Manual.md').read_text(), 'Manual notes')

    def test_manual_collision_is_refused(self):
        (self.destination / 'Home.md').write_text('A manual home page')
        self.save()
        self.source_files({'Home.md': 'Generated home'})
        with self.assertRaisesRegex(ValueError, 'unowned'):
            wiki.synchronize(self.source, self.destination, True)
        self.assertEqual((self.destination / 'Home.md').read_text(), 'A manual home page')

    def test_manual_edit_of_generated_page_is_refused_even_when_committed(self):
        self.source_files({'Home.md': 'Generated home'})
        wiki.synchronize(self.source, self.destination, True)
        self.save()
        (self.destination / 'Home.md').write_text('Later human edit')
        self.save()
        with self.assertRaisesRegex(ValueError, 'changed outside'):
            wiki.synchronize(self.source, self.destination, True)

    def test_wrong_remote_and_path_traversal_are_refused(self):
        self.source_files({'Home.md': 'Home'})
        self.git('remote', 'set-url', 'origin', 'https://example.org/other.git')
        with self.assertRaisesRegex(ValueError, 'expected EchoMuse'):
            wiki.synchronize(self.source, self.destination, True)
        self.git('remote', 'set-url', 'origin', sorted(wiki.REMOTES)[0])
        (self.source / '.generated.json').write_text(json.dumps({'source_ref': 'a' * 40, 'files': ['../outside.md']}))
        with self.assertRaisesRegex(ValueError, 'filename'):
            wiki.synchronize(self.source, self.destination, True)


if __name__ == '__main__':
    unittest.main()
