#!/usr/bin/env python3
"""Exercise the pinned BLE patch with real protocol code and synthetic I/O.

Run in the documented EchoMuse test container or an environment with its
controller dependencies. No device, Home Assistant, or network is contacted.
"""
from __future__ import annotations

import argparse
import ast
import asyncio
import base64
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from apply_ble_auth_patch import prepare, read_regular, sha256

DEVICE = 'SYNTHETIC-BLE-TEST'
KEY = bytes(range(32))
ENCODED = base64.b64encode(KEY).decode()
MAC = ':'.join(('00', 'EC', '00', '00', '00', '02'))
SOURCE = OVERLAY = None


class FakeDB:
    def __init__(self, key=ENCODED, connections=True):
        self.row = {'device_id': DEVICE, 'approved': True, 'label': 'Test', 'ble_proxy_key': key}
        self.config = {'bleProxyEnabled': True, 'bleProxyConnections': connections}
        self.key_calls = self.port_calls = 0
        self.gate = None
        self.entered = threading.Event()
        self.second = threading.Event()
        self.lock = threading.Lock()

    def get_device(self, _):
        return dict(self.row)

    def get_all_devices(self):
        return [dict(self.row)]

    def get_effective_device_config(self, _):
        return dict(self.config)

    def ensure_ble_proxy_key(self, _):
        self.key_calls += 1
        if not self.row['ble_proxy_key']:
            self.row['ble_proxy_key'] = ENCODED
        return self.row['ble_proxy_key']

    def ensure_ble_proxy_port(self, _):
        with self.lock:
            self.port_calls += 1
            if self.port_calls == 2:
                self.second.set()
        self.entered.set()
        if self.gate and not self.gate.wait(3):
            raise RuntimeError('Synthetic test gate timed out')
        return 17001


class FakeZC:
    def __init__(self):
        self.registered = []

    async def async_register_service(self, info, **_):
        self.registered.append(info)
        await asyncio.sleep(0)

    async def async_unregister_service(self, _):
        await asyncio.sleep(0)


class Listener:
    def __init__(self, listeners):
        self.listeners = listeners

    def close(self):
        self.listeners.discard(self)

    async def wait_closed(self):
        await asyncio.sleep(0)


class Transport:
    def __init__(self):
        self.closed = False
        self.data = bytearray()

    def write(self, data):
        self.data.extend(data)

    def close(self):
        self.closed = True

    def is_closing(self):
        return self.closed

    def get_extra_info(self, name):
        return ('192.0.2.1', 1234) if name == 'peername' else None


class Rig:
    def __init__(self, owner, original=False, key=ENCODED, connections=True):
        path = (SOURCE if original else OVERLAY) / 'controller/em_ble_proxy.py'
        spec = importlib.util.spec_from_file_location('tested_ble', path)
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)
        self.db = FakeDB(key, connections)
        self.mod.db = self.db
        self.zc, self.listeners, self.starts = FakeZC(), set(), []
        mocked = patch.dict(sys.modules, {'em_esphome': SimpleNamespace(
            ESPHOME_PROJECT_VERSION='2.26.0', ESPHOME_DEVICE_MODEL='Test Dot',
            SERVER_IP='127.0.0.1', _serialno_to_mac=lambda _: MAC, _azc=self.zc)})
        mocked.start()
        owner.addCleanup(mocked.stop)

        async def serve(factory, *_args):
            await asyncio.sleep(0)
            if self.listeners:
                raise OSError('Synthetic duplicate bind')
            listener = Listener(self.listeners)
            self.listeners.add(listener)
            self.starts.append(factory.__self__)
            return listener

        async def slots(_):
            pass

        self.mod.serve, self.mod.sync_slots = serve, slots
        self.mod.em_tasks = SimpleNamespace(spawn=asyncio.create_task)

    def online(self, capable=True):
        self.mod._online.add(DEVICE)
        if capable:
            self.mod._can_connect.add(DEVICE)
        else:
            self.mod._can_connect.discard(DEVICE)

    def contract(self, test, encrypted, connections):
        from esphome.vendor import api_pb2
        proxy = self.mod._proxies[DEVICE]
        state = self.mod.get_status(DEVICE)
        test.assertEqual((state['encrypted'], state['connections']), (encrypted, connections))
        satellite = self.mod.BluetoothProxySatellite(DEVICE, 'Test', MAC, lambda _: None, proxy)
        test.assertEqual(satellite._noise_psk, KEY if encrypted else None)
        test.assertEqual(satellite._gatt is not None, connections)
        info, = satellite.handle_message(api_pb2.DeviceInfoRequest())
        test.assertEqual(info.api_encryption_supported, encrypted)
        test.assertEqual(info.bluetooth_proxy_feature_flags,
                         self.mod.BT_PROXY_FLAGS_ACTIVE if connections else self.mod.BT_PROXY_FLAGS)
        test.assertEqual(b'api_encryption' in proxy._mdns_info.properties, encrypted)
        satellite.close_gatt()
        return satellite


class RuntimeTests(unittest.TestCase):
    def test_original_plaintext_transition_is_reproduced(self):
        rig = Rig(self, original=True)
        async def scenario():
            rig.online()
            await rig.mod.reconcile(DEVICE)
            self.assertTrue(rig.mod.get_status(DEVICE)['encrypted'])
            rig.db.config['bleProxyConnections'] = False
            await rig.mod.reconcile(DEVICE)
            self.assertFalse(rig.mod.get_status(DEVICE)['encrypted'])
            self.assertEqual(rig.db.row['ble_proxy_key'], ENCODED)
        asyncio.run(scenario())

    def test_toggle_capability_and_restart_keep_key(self):
        rig = Rig(self)
        async def scenario():
            await rig.mod.start_ble_proxy_servers()
            self.assertFalse(rig.listeners)
            await rig.mod.device_connected(DEVICE, ble_connect=False)
            rig.contract(self, True, False)
            self.assertFalse(any(proxy.connections for proxy in rig.starts))
            await rig.mod.device_connected(DEVICE, ble_connect=True)
            rig.contract(self, True, True)
            rig.db.config['bleProxyConnections'] = False
            await rig.mod.reconcile(DEVICE)
            rig.contract(self, True, False)
            await rig.mod.device_disconnected(DEVICE)
            self.assertFalse(rig.listeners)
            await rig.mod.device_connected(DEVICE, ble_connect=True)
            rig.contract(self, True, False)
            await rig.mod.stop_ble_proxy_servers()
            await rig.mod.start_ble_proxy_servers()
            rig.contract(self, True, False)
            self.assertEqual(rig.db.key_calls, 0)
        asyncio.run(scenario())

    def test_legacy_passive_and_first_enrollment(self):
        rig = Rig(self, key=None, connections=False)
        async def scenario():
            rig.online()
            await rig.mod.reconcile(DEVICE)
            rig.contract(self, False, False)
            self.assertEqual(rig.db.key_calls, 0)
            rig.db.config['bleProxyConnections'] = True
            await rig.mod.reconcile(DEVICE)
            rig.contract(self, True, True)
            rig.db.config['bleProxyConnections'] = False
            await rig.mod.reconcile(DEVICE)
            rig.contract(self, True, False)
            self.assertEqual(rig.db.key_calls, 1)
        asyncio.run(scenario())

    def test_corrupt_or_lost_key_never_rotates_or_downgrades(self):
        for bad in (None, '', 'invalid-key', base64.b64encode(b'short').decode()):
            for connections in (True, False):
                with self.subTest(bad=bad, connections=connections):
                    rig = Rig(self, connections=connections)
                    async def scenario():
                        rig.online()
                        await rig.mod.reconcile(DEVICE)
                        rig.db.row['ble_proxy_key'] = bad
                        with self.assertLogs('echomuse.bleproxy', level='ERROR'):
                            for _ in range(3):
                                await rig.mod.reconcile(DEVICE)
                        self.assertFalse(rig.listeners)
                        self.assertFalse(rig.mod._proxies)
                        self.assertEqual(rig.db.key_calls, 0)
                        rig.db.row['ble_proxy_key'] = ENCODED
                        await rig.mod.reconcile(DEVICE)
                        rig.contract(self, True, connections)
                    asyncio.run(scenario())

    def test_key_get_is_read_only_even_with_missing_storage(self):
        for stored in (ENCODED, None, '', 'invalid-key'):
            with self.subTest(stored_valid=stored == ENCODED):
                rig = Rig(self, connections=False)
                tree = ast.parse((OVERLAY / 'controller/em_api.py').read_text())
                fn = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef)
                          and n.name == '_get_ble_proxy_key')
                self.assertEqual(ast.unparse(fn.decorator_list[0]), 'auth.require_admin')
                fn.decorator_list = []
                namespace = {'web': SimpleNamespace(Request=object, Response=object),
                             'asyncio': asyncio, 'db': rig.db, 'em_ble_proxy': rig.mod,
                             '_ok': lambda obj: obj, '_error': lambda *args: {'error': args}}
                exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])),
                             '<actual-key-handler>', 'exec'), namespace)
                async def scenario():
                    rig.online()
                    await rig.mod.reconcile(DEVICE)
                    rig.db.row['ble_proxy_key'] = stored
                    result = await namespace['_get_ble_proxy_key'](SimpleNamespace(match_info={'id': DEVICE}))
                    self.assertEqual(rig.db.key_calls, 0)
                    if stored == ENCODED:
                        self.assertEqual(result, {'key': ENCODED})
                    else:
                        self.assertEqual(result['error'][0], 'key_unavailable')
                asyncio.run(scenario())

    def test_protocol_rejects_plaintext_when_gatt_is_off(self):
        from esphome.frame_protocol import encode_frame
        rig = Rig(self, connections=False)
        async def scenario():
            rig.online()
            await rig.mod.reconcile(DEVICE)
            satellite = rig.contract(self, True, False)
            transport = Transport()
            satellite.connection_made(transport)
            with self.assertLogs('echomuse.esphome.frame', level='WARNING'):
                satellite.data_received(encode_frame(1, b'hello'))
            self.assertTrue(transport.closed)
            self.assertTrue(transport.data.startswith(b'\x01'))
            with self.assertRaises(ValueError):
                rig.mod.DeviceBleProxyServer(DEVICE, 'Test', MAC, 17001, connections=True)
        asyncio.run(scenario())

    def test_concurrent_creation_is_serialized(self):
        for original in (True, False):
            with self.subTest(original=original):
                rig = Rig(self, original=original, connections=False)
                rig.db.gate = threading.Event()
                async def scenario():
                    rig.online()
                    first = asyncio.create_task(rig.mod.reconcile(DEVICE))
                    self.assertTrue(await asyncio.to_thread(rig.db.entered.wait, 1))
                    second = asyncio.create_task(rig.mod.reconcile(DEVICE))
                    second_entered = await asyncio.to_thread(rig.db.second.wait, 0.15)
                    rig.db.gate.set()
                    results = await asyncio.gather(first, second, return_exceptions=True)
                    self.assertEqual(second_entered, original)
                    self.assertEqual(len(rig.zc.registered), 2 if original else 1)
                    self.assertEqual(any(isinstance(r, OSError) for r in results), original)
                    self.assertEqual(len(rig.listeners), 1)
                asyncio.run(scenario())

    def test_shutdown_waits_for_pending_reconcile(self):
        rig = Rig(self)
        rig.db.gate = threading.Event()
        async def scenario():
            rig.online()
            pending = asyncio.create_task(rig.mod.reconcile(DEVICE))
            self.assertTrue(await asyncio.to_thread(rig.db.entered.wait, 1))
            stop = asyncio.create_task(rig.mod.stop_ble_proxy_servers())
            await asyncio.sleep(0)
            rig.db.gate.set()
            await asyncio.gather(pending, stop)
            await rig.mod.reconcile(DEVICE)
            self.assertFalse(rig.listeners)
            self.assertFalse(rig.mod._proxies)
        asyncio.run(scenario())

    def test_real_sqlite_key_survives_reopen_and_concurrent_gets(self):
        from concurrent.futures import ThreadPoolExecutor
        import em_db
        with tempfile.TemporaryDirectory() as directory:
            database = str(Path(directory) / 'test.db')
            try:
                em_db.init(database)
                em_db.register_new_device(DEVICE, '192.0.2.1', 'test')
                with ThreadPoolExecutor(max_workers=8) as executor:
                    keys = list(executor.map(lambda _: em_db.ensure_ble_proxy_key(DEVICE), range(24)))
                self.assertEqual(len(set(keys)), 1)
                em_db._conn.close()
                em_db._conn = None
                em_db.init(database)
                self.assertEqual(em_db.ensure_ble_proxy_key(DEVICE), keys[0])
            finally:
                if em_db._conn is not None:
                    em_db._conn.close()
                    em_db._conn = None


def main():
    global SOURCE, OVERLAY
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--source', required=True, type=Path)
    cli.add_argument('--overlay', required=True, type=Path)
    cli.add_argument('--reviewed-custom-api-sha256')
    args = cli.parse_args()
    SOURCE, OVERLAY = args.source.resolve(), args.overlay.resolve()
    _, expected = prepare(SOURCE, reviewed_custom_api_sha256=args.reviewed_custom_api_sha256)
    for name, data in expected.items():
        if read_regular(OVERLAY, name) != data:
            raise SystemExit('Runtime overlay differs from the verified patch')
    receipt = json.loads((OVERLAY / 'patch-receipt.json').read_text())
    built = receipt.get('dashboard_build', {})
    if (built.get('version') != '0.20.2'
            or built.get('input_sha256') != sha256(expected['controller/static/dashboard.jsx'])
            or built.get('output_sha256') != sha256(read_regular(OVERLAY, 'controller/static/dashboard.js'))):
        raise SystemExit('Compiled dashboard is missing or differs from its build receipt')
    html = read_regular(SOURCE, 'controller/static/dashboard.html').decode()
    if '<script src="static/dashboard.js"></script>' not in html:
        raise SystemExit('Upstream dashboard entry point changed')
    sys.path.insert(0, str(SOURCE / 'controller'))
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(RuntimeTests))
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
