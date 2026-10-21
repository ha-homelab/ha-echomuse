"""Offline checks for hash-pinned patching and preservation of custom API code."""
import difflib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from scripts import apply_ble_auth_patch as patcher


class PatchToolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        (self.source / 'controller').mkdir(parents=True)
        self.before = 'async def _get_ble_proxy_key(request):\n    return "before"\n'
        self.after = self.before.replace('before', 'after')
        self.name = 'controller/em_api.py'
        (self.source / self.name).write_text(self.before)
        self.patch = self.root / 'change.patch'
        self.patch.write_text(''.join(difflib.unified_diff(
            self.before.splitlines(keepends=True), self.after.splitlines(keepends=True),
            fromfile='a/' + self.name, tofile='b/' + self.name, n=0)))
        self.manifest = self.root / 'manifest.json'
        self.data = {'schema': 1, 'upstream': {'version': 'fixture'},
                     'patch': self.patch.name, 'patch_sha256': patcher.sha256(self.patch.read_bytes()),
                     'files': {self.name: {'before_sha256': patcher.sha256(self.before.encode()),
                                          'after_sha256': patcher.sha256(self.after.encode())}},
                     'custom_api': {'path': self.name, 'function': '_get_ble_proxy_key',
                                    'before_function_sha256': patcher.sha256(self.before.encode()),
                                    'after_function_sha256': patcher.sha256(self.after.encode())}}
        self.save_manifest()

    def save_manifest(self):
        self.manifest.write_text(json.dumps(self.data))

    def prepare(self, **kwargs):
        return patcher.prepare(self.source, self.manifest, **kwargs)

    def test_check_has_no_side_effects_and_output_is_separate(self):
        receipt, files = self.prepare()
        self.assertEqual(files[self.name], self.after.encode())
        self.assertEqual((self.source / self.name).read_text(), self.before)
        output = self.root / 'overlay'
        patcher.write_overlay(output, receipt, files)
        self.assertEqual((output / self.name).read_text(), self.after)
        self.assertEqual((output / self.name).stat().st_mode & 0o777, 0o600)
        self.assertTrue((output / 'patch-receipt.json').is_file())
        with self.assertRaises(FileExistsError):
            patcher.write_overlay(output, receipt, files)
        # Already patched inputs are checked, not patched a second time.
        _, again = patcher.prepare(output, self.manifest)
        self.assertEqual(again, files)

    def test_unknown_source_fails_without_output(self):
        (self.source / self.name).write_text(self.before + '# unexpected\n')
        with self.assertRaises(patcher.PatchError):
            self.prepare()
        self.assertFalse((self.root / 'overlay').exists())

    def test_custom_api_requires_exact_explicit_review_and_preserves_surroundings(self):
        prefix, suffix = '# reviewed recorder extension\n\n', '\ndef recorder():\n    return 42\n'
        custom = prefix + self.before + suffix
        (self.source / self.name).write_text(custom)
        with self.assertRaises(patcher.PatchError):
            self.prepare()
        with self.assertRaises(patcher.PatchError):
            self.prepare(reviewed_custom_api_sha256='0' * 64)
        receipt, files = self.prepare(reviewed_custom_api_sha256=patcher.sha256(custom.encode()))
        self.assertEqual(files[self.name].decode(), prefix + self.after + suffix)
        self.assertTrue(receipt['files'][self.name]['reviewed_custom_api'])

    def test_custom_api_ignores_unchanged_neighboring_context(self):
        neighbor = '\n# unchanged neighboring code\n'
        self.patch.write_text(''.join(difflib.unified_diff(
            (self.before + neighbor).splitlines(keepends=True),
            (self.after + neighbor).splitlines(keepends=True),
            fromfile='a/' + self.name, tofile='b/' + self.name, n=3)))
        self.data['patch_sha256'] = patcher.sha256(self.patch.read_bytes())
        self.save_manifest()
        custom = '# custom extension\n' + self.before + neighbor
        (self.source / self.name).write_text(custom)
        _, files = self.prepare(reviewed_custom_api_sha256=patcher.sha256(custom.encode()))
        self.assertEqual(files[self.name].decode(), '# custom extension\n' + self.after + neighbor)

    def test_custom_handler_changes_are_rejected_even_with_reviewed_file_hash(self):
        custom = self.before.replace('before', 'different')
        (self.source / self.name).write_text(custom)
        with self.assertRaises(patcher.PatchError):
            self.prepare(reviewed_custom_api_sha256=patcher.sha256(custom.encode()))

    def test_patch_tampering_is_rejected(self):
        self.patch.write_text(self.patch.read_text().replace('after', 'wrong'))
        with self.assertRaises(patcher.PatchError):
            self.prepare()

    def test_context_and_traversal_are_rejected(self):
        with self.assertRaises(patcher.PatchError):
            patcher.apply_exact('wrong\n', [{'start': 1, 'before': ['before\n'], 'after': ['after\n']}])
        for name in ('../outside', '/outside', 'controller/../outside', 'a\\b'):
            with self.subTest(name=name), self.assertRaises(patcher.PatchError):
                patcher.safe_relative(name)

    def test_symlink_is_rejected(self):
        target = self.source / self.name
        target.unlink()
        outside = self.root / 'outside.py'
        outside.write_text(self.before)
        target.symlink_to(outside)
        with self.assertRaises(patcher.PatchError):
            self.prepare()

    def test_dashboard_build_pins_version_flags_and_receipt(self):
        files = {'controller/static/dashboard.jsx': b'const element = <div />;\n'}
        receipt = {'files': {}}
        calls = []
        def run(args, **kwargs):
            calls.append(args)
            if args[-1] == '--version':
                return SimpleNamespace(stdout='0.20.2\n')
            output = next(arg.split('=', 1)[1] for arg in args if arg.startswith('--outfile='))
            Path(output).write_bytes(b'const element = React.createElement("div");\n')
            return SimpleNamespace(stdout='')
        with patch.object(patcher.subprocess, 'run', side_effect=run):
            patcher.compile_dashboard(receipt, files, self.root / 'esbuild')
        self.assertIn('--jsx-factory=React.createElement', calls[1])
        self.assertIn('--jsx-fragment=React.Fragment', calls[1])
        self.assertIn('--bundle=false', calls[1])
        self.assertEqual(receipt['dashboard_build']['version'], '0.20.2')
        self.assertEqual(receipt['dashboard_build']['output_sha256'],
                         patcher.sha256(files['controller/static/dashboard.js']))

    def test_dashboard_wrong_compiler_version_is_rejected(self):
        with patch.object(patcher.subprocess, 'run', return_value=SimpleNamespace(stdout='different')):
            with self.assertRaises(patcher.PatchError):
                patcher.compile_dashboard({'files': {}}, {}, self.root / 'esbuild')

    def test_committed_manifest_and_patch_inventory_match(self):
        path = patcher.DEFAULT_MANIFEST
        data = json.loads(path.read_text())
        raw = (path.parent / data['patch']).read_bytes()
        self.assertEqual(patcher.sha256(raw), data['patch_sha256'])
        self.assertEqual(set(patcher.parse_patch(raw.decode())), set(data['files']))
        self.assertEqual(data['upstream']['version'], '2.26.0')
        self.assertEqual(len(data['upstream']['commit']), 40)


if __name__ == '__main__':
    unittest.main()
