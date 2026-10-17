"""A lost shell reply must not trigger destructive assumptions about assets."""
import ast
import importlib.util
from pathlib import Path
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'recorder_overlay', ROOT/'training/recorder/patch_controller.py')
overlay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(overlay)

# Relevant pinned upstream function, without external runtime dependencies.
UPSTREAM_FUNCTION = '''async def _oww_device_state(live) -> dict:
    d = em_oww_assets.DEVICE_DIR
    out = await _shell_run(live, (
        f'for f in {d}/*.so {d}/*.onnx; do '
        f'[ -f "$f" ] && echo "$(busybox md5sum "$f" | busybox cut -d\\" \\" -f1) '
        f'$(busybox stat -c %Y "$f") $f"; done; '
        f'echo "FREE $(busybox df -m /data | busybox tail -1)"'
    ), timeout=120.0)

    free_mb = None
    lines = []
    for line in out.splitlines():
        if line.startswith("FREE "):
            free_mb = em_oww_assets.parse_free_mb(line[5:])
        else:
            lines.append(line)
    return {
        "installed": em_oww_assets.parse_device_listing("\\n".join(lines)),
        "free_mb": free_mb,
    }
'''
MARKER = '__EM_OWW_INVENTORY_OK__'


class InventoryProbeTests(unittest.IsolatedAsyncioTestCase):
    async def probe(self, reply):
        self.commands = []
        self.free_rows = []
        self.inventory_rows = []

        async def shell(live, command, timeout):
            self.commands.append(command)
            self.assertEqual(timeout, 120.0)
            return reply(command) if callable(reply) else reply

        def free_mb(row):
            self.free_rows.append(row)
            return 1061

        def inventory(row):
            self.inventory_rows.append(row)
            return {line.split()[-1]: line.split()[0]
                    for line in row.splitlines() if line.strip()}

        namespace = {'_shell_run': shell, 'em_oww_assets': types.SimpleNamespace(
            DEVICE_DIR='/data/oww', parse_free_mb=free_mb,
            parse_device_listing=inventory)}
        tree = ast.parse(overlay.patch_oww_inventory(UPSTREAM_FUNCTION))
        function = next(n for n in tree.body
                        if isinstance(n, ast.AsyncFunctionDef)
                        and n.name == '_oww_device_state')
        exec(compile(ast.Module(body=[function], type_ignores=[]),
                     'patched_inventory', 'exec'), namespace)
        return await namespace['_oww_device_state'](object())

    async def test_complete_inventory_and_free_space(self):
        result = await self.probe(
            'aaa 123 /data/oww/model.onnx\nbbb 124 /data/oww/runtime.so\n'
            'FREE /dev/data 1231 170 1061 14% /data\n' + MARKER + '\n')
        self.assertEqual(result, {'installed': {
            '/data/oww/model.onnx': 'aaa', '/data/oww/runtime.so': 'bbb'},
            'free_mb': 1061})
        self.assertEqual(self.free_rows, ['/dev/data 1231 170 1061 14% /data'])
        self.assertNotIn(MARKER, self.inventory_rows[0])
        self.assertNotIn(MARKER, self.commands[0])

    async def test_genuine_empty_inventory_is_valid(self):
        result = await self.probe('FREE /dev/data 1231 170 1061 14% /data\n'
                                  + MARKER + '\n')
        self.assertEqual(result, {'installed': {}, 'free_mb': 1061})

    async def test_empty_partial_or_trailing_output_is_unknown(self):
        for reply in ('', 'aaa 123 /data/oww/model.onnx\n',
                      'FREE /dev/data 1231 170 1061 14% /data\n',
                      MARKER + '\nunexpected trailing output\n'):
            with self.subTest(reply=reply):
                with self.assertRaisesRegex(RuntimeError, 'installed assets are unknown'):
                    await self.probe(reply)
                self.assertEqual(self.inventory_rows, [])

    async def test_echoed_command_does_not_complete_probe(self):
        with self.assertRaisesRegex(RuntimeError, 'did not complete'):
            await self.probe(lambda command: command + '\n')
        self.assertNotIn(MARKER, self.commands[0])

    def test_patch_refuses_changed_or_duplicate_hook(self):
        for source in ('unreviewed source', UPSTREAM_FUNCTION * 2):
            with self.subTest(source=source[:20]):
                with self.assertRaisesRegex(ValueError, 'exactly once'):
                    overlay.patch_oww_inventory(source)


if __name__ == '__main__':
    unittest.main()
