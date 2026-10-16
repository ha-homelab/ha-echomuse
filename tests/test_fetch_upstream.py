"""Offline integrity and publication guards; no release download or device access."""
import hashlib
import http.client
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import sys
import subprocess
import tempfile
import unittest
import unittest.mock
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fetch = load('fetch_upstream')
public = load('check_public')


class Response(io.BytesIO):
    status = 200

    def __init__(self, data, length=None):
        super().__init__(data)
        self.headers = {} if length is None else {'Content-Length': str(length)}

    def geturl(self):
        return 'https://release-assets.githubusercontent.com/release-asset'


class FetchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.destination = self.root / 'private' / 'artifacts'
        self.body = b'verified release fixture'
        self.artifact = {
            'filename': 'firmware-fixture',
            'url': 'https://github.com/wilbowes/EchoMuse/releases/download/v-fixture/server',
            'bytes': len(self.body), 'sha256': hashlib.sha256(self.body).hexdigest(),
        }

    def opener(self, body=None, length=None):
        return unittest.mock.Mock(open=unittest.mock.Mock(return_value=Response(self.body if body is None else body, length)))

    def assert_no_files(self):
        self.assertFalse(list(self.destination.glob('*')))

    def test_valid_artifact_is_atomic_and_private(self):
        old = os.umask(0)
        try:
            path = fetch.fetch(self.artifact, self.destination, opener=self.opener())
        finally:
            os.umask(old)
        self.assertEqual(path.read_bytes(), self.body)
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.destination.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(self.destination.parent.stat().st_mode), 0o700)
        self.assertEqual(list(self.destination.iterdir()), [path])

    def test_corruption_same_length_is_rejected_and_cleaned(self):
        with self.assertRaisesRegex(fetch.FetchError, 'SHA-256'):
            fetch.fetch(self.artifact, self.destination, opener=self.opener(b'x' * len(self.body)))
        self.assert_no_files()

    def test_short_transfer_is_rejected_and_cleaned(self):
        with self.assertRaisesRegex(fetch.FetchError, 'size or SHA-256'):
            fetch.fetch(self.artifact, self.destination, opener=self.opener(self.body[:-1]))
        self.assert_no_files()

    def test_interrupted_transfer_is_rejected_and_cleaned(self):
        response = Response(self.body)
        response.read = unittest.mock.Mock(side_effect=[self.body[:3], http.client.IncompleteRead(b'part')])
        with self.assertRaisesRegex(fetch.FetchError, 'download failed'):
            fetch.fetch(self.artifact, self.destination, opener=unittest.mock.Mock(open=unittest.mock.Mock(return_value=response)))
        self.assert_no_files()

    def test_oversize_transfer_without_length_is_bounded(self):
        with self.assertRaisesRegex(fetch.FetchError, 'exceeds'):
            fetch.fetch(self.artifact, self.destination, opener=self.opener(self.body + b'extra'))
        self.assert_no_files()

    def test_incorrect_content_length_is_rejected(self):
        with self.assertRaisesRegex(fetch.FetchError, 'content length'):
            fetch.fetch(self.artifact, self.destination, opener=self.opener(length=len(self.body) + 1))
        self.assert_no_files()

    def test_existing_mismatch_is_not_overwritten_or_downloaded(self):
        self.destination.mkdir(parents=True)
        path = self.destination / self.artifact['filename']
        path.write_bytes(b'x' * len(self.body))
        opener = self.opener()
        with self.assertRaisesRegex(fetch.FetchError, 'refusing overwrite'):
            fetch.fetch(self.artifact, self.destination, opener=opener)
        self.assertEqual(path.read_bytes(), b'x' * len(self.body))
        opener.open.assert_not_called()

    def test_valid_existing_file_is_verified_without_network(self):
        self.destination.mkdir(parents=True)
        path = self.destination / self.artifact['filename']
        path.write_bytes(self.body)
        opener = self.opener()
        self.assertEqual(fetch.fetch(self.artifact, self.destination, opener=opener), path)
        opener.open.assert_not_called()

    def test_download_does_not_replace_a_concurrent_writer(self):
        actual_link = os.link
        def competing_link(source, destination):
            Path(destination).write_bytes(b'other process')
            return actual_link(source, destination)
        with unittest.mock.patch.object(fetch.os, 'link', side_effect=competing_link):
            with self.assertRaises(fetch.FetchError):
                fetch.fetch(self.artifact, self.destination, opener=self.opener())
        self.assertEqual((self.destination / self.artifact['filename']).read_bytes(), b'other process')
        self.assertFalse(list(self.destination.glob('*.partial')))

    def test_existing_symlink_is_not_followed(self):
        self.destination.mkdir(parents=True)
        path = self.destination / self.artifact['filename']
        path.symlink_to(self.root / 'missing')
        with self.assertRaises(fetch.FetchError):
            fetch.fetch(self.artifact, self.destination, opener=self.opener())
        self.assertTrue(path.is_symlink())

    def test_redirects_reject_http_credentials_and_other_hosts(self):
        request = urllib.request.Request(self.artifact['url'])
        handler = fetch.ReleaseRedirects()
        for url in ('http://github.com/file', 'https://github.com.evil.example/file',
                    'https://user:pass@github.com/file', 'https://github.com:444/file',
                    'https://example.invalid/file'):
            with self.subTest(url=url), self.assertRaises(fetch.FetchError):
                handler.redirect_request(request, None, 302, 'Found', {}, url)

    def test_lock_rejects_traversal_unbounded_size_and_invalid_digest(self):
        lock = self.root / 'lock.json'
        for key, value in (('filename', '../outside'), ('bytes', fetch.MAX_BYTES + 1),
                           ('bytes', True), ('sha256', 'not-a-sha'),
                           ('url', 'https://github.com/other/project/releases/download/v1/file')):
            changed = {**self.artifact, key: value}
            lock.write_text(json.dumps({'artifacts': {'firmware': changed}}))
            with self.subTest(key=key, value=value), self.assertRaises(fetch.FetchError):
                fetch.load_artifacts(lock)

    def test_committed_lock_is_valid_without_downloading(self):
        self.assertEqual(set(fetch.load_artifacts(ROOT / 'upstream-lock.json')), {'firmware', 'emos'})


class PublicAuditTests(unittest.TestCase):
    def test_plain_yaml_credential_assignment_is_flagged(self):
        sensitive = ('password' + ': ' + 'private-value').encode()
        self.assertEqual(public.content_problems(sensitive), [(1, 'possible credential assignment')])
        self.assertEqual(public.content_problems(b'password: REPLACE_WITH_PASSWORD'), [])

    def test_addresses_and_credentials_are_reported_without_values(self):
        address = '.'.join(('10', '12', '13', '14'))
        mac = ':'.join(('ab', 'cd', 'ef', '12', '34', '56'))
        credential = 'gh' + 'p_' + 'q' * 36
        problems = public.content_problems((address + '\n' + mac + '\n' + credential).encode())
        self.assertEqual({label for _, label in problems},
                         {'live IPv4 address', 'device MAC address', 'GitHub credential'})
        self.assertNotIn(credential, repr(problems))

    def test_cli_omits_matched_values_from_both_output_streams(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(['git', 'init', '--quiet', str(root)], check=True)
            credential = 'gh' + 'p_' + 'q' * 36
            address = '.'.join(('10', '12', '13', '14'))
            (root / 'notes.txt').write_text(credential + '\n' + address + '\n')
            subprocess.run(['git', '-C', str(root), 'add', 'notes.txt'], check=True)
            result = subprocess.run(
                [sys.executable, str(ROOT / 'scripts/check_public.py'), '--root', str(root)],
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, '')
            self.assertIn('notes.txt:1: GitHub credential', result.stderr)
            self.assertIn('notes.txt:2: live IPv4 address', result.stderr)
            self.assertNotIn(credential, result.stdout + result.stderr)
            self.assertNotIn(address, result.stdout + result.stderr)

    def test_documentation_and_bind_addresses_are_allowed(self):
        self.assertEqual(public.content_problems(b'192.0.2.10 198.51.100.10 203.0.113.10 127.0.0.1 0.0.0.0'), [])

    def test_private_paths_and_artifacts_are_rejected(self):
        for name in ('private/result.json', 'backups/boot.txt', '.env', 'firmware.bin',
                     'models/wake.tflite', 'recording.wav', 'inventory/devices.local.json'):
            with self.subTest(name=name):
                self.assertIsNotNone(public.path_problem(name))
        self.assertIsNone(public.path_problem('deployments/.env.example'))

    def test_staged_sensitive_content_is_checked_even_if_worktree_is_cleaned(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(['git', 'init', '--quiet', str(root)], check=True)
            path = root / 'notes.txt'
            path.write_text('gh' + 'p_' + 'q' * 36)
            subprocess.run(['git', '-C', str(root), 'add', 'notes.txt'], check=True)
            path.write_text('cleaned working copy\n')
            count, issues = public.audit(root)
            self.assertEqual(count, 1)
            self.assertEqual(len(issues), 1)
            self.assertIn('GitHub credential', issues[0])
            self.assertNotIn('q' * 36, issues[0])


if __name__ == '__main__':
    unittest.main()
