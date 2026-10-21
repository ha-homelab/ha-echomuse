# Stable Bluetooth proxy authentication for EchoMuse 2.26.0

This patch keeps an enrolled Bluetooth proxy encrypted when active GATT
connections are disabled or temporarily unavailable. The key is preserved;
active connection support still requires compatible firmware and the setting
being enabled. First-time passive proxies without a key remain compatible.
It also serializes proxy lifecycle operations, makes Show key read-only, and
keeps the key available in the UI for encrypted passive proxies.

The patch is pinned to upstream commit
`e119433c0845dfe80f4b1ec44c9e8e8028adbb07`. It is an integration patch maintained
here, not a claim that upstream has released this fix. See
[manifest.json](manifest.json), the [patch](ble-auth-lifecycle.patch), and the
[upstream MIT license](LICENSE-EchoMuse-MIT.txt).

## Check and prepare

Use a private source copy. The tool has no network or device access, does not
restart services, and never modifies its input files. A check without `--output`
is read-only. Every patched file must match its pinned input or output hash.
The generated overlay may contain your custom code, so keep it private.

```sh
mkdir -p private
# Fetch the exact source revision, not a moving branch.
git init private/echomuse-source
git -C private/echomuse-source remote add origin https://github.com/wilbowes/EchoMuse.git
git -C private/echomuse-source fetch --depth 1 origin e119433c0845dfe80f4b1ec44c9e8e8028adbb07
git -C private/echomuse-source checkout --detach FETCH_HEAD

python3 scripts/apply_ble_auth_patch.py --source private/echomuse-source
npm install --prefix private/echomuse-build-tools --no-audit --no-fund --package-lock=false esbuild@0.20.2
python3 scripts/apply_ble_auth_patch.py \
  --source private/echomuse-source --output private/ble-auth-overlay \
  --esbuild private/echomuse-build-tools/node_modules/.bin/esbuild
```

The output directory must not already exist. `patch-receipt.json` records input,
patch, and output hashes and is written last. Do not deploy an incomplete output
without its receipt. Deployment remains a separate operation: mount or package
the changed Python files (`em_ble_proxy.py` and `em_api.py`) and the compiled
`static/dashboard.js` using your normal controller deployment. Keep the patched
`static/dashboard.jsx` with the deployment source for provenance. The upstream
HTML loads **dashboard.js**, so mounting JSX alone does not update the UI.
The tool requires esbuild **0.20.2** with `--output`, uses the exact upstream
JSX flags, and records the compiled asset hash in its receipt. The other source
file updates the upstream test assertions. Restart the controller to load the
Python changes and refresh the browser for the UI. The Dot firmware and HA do
not need a restart merely to load this patch.

## Preserve a custom API overlay

Do not replace an existing recorder API overlay with a pristine upstream file.
Place the current custom `controller/em_api.py` into the private source copy and
review its changes. By default its differing hash is rejected. After review,
pass the exact current file hash explicitly:

```sh
python3 scripts/apply_ble_auth_patch.py \
  --source private/echomuse-source \
  --reviewed-custom-api-sha256 REVIEWED_SHA256
```

Only this API file can receive that exception. Its complete original key-handler
function, including decorators, must still match the pinned upstream function.
Only that function is replaced, its result is verified, and all surrounding
custom code remains byte-for-byte unchanged. Other files still require exact
hash matches. Run the same command with a new `--output` directory and the pinned `--esbuild` executable to
prepare that reviewed overlay. There is no force, fuzzy patch, or automatic rebase mode.

## Verification

The shared Python CI pipeline runs the offline patch-tool tests. The existing
source-validation job additionally fetches the pinned source, checks all hashes,
and runs the actual BLE implementation in a network-disabled, read-only
EchoMuse 2.26.0 container. Tests use synthetic identities, a temporary SQLite
database, and substituted I/O; no household endpoints are required.

```sh
python3 -m unittest tests.test_ble_auth_patch -v

# Requires the controller's Python dependencies. CI runs this in the pinned image.
python3 scripts/check_ble_auth_runtime.py \
  --source private/echomuse-source --overlay private/ble-auth-overlay
```

For a reviewed custom API source, pass the same
`--reviewed-custom-api-sha256` to the runtime checker.

The runtime suite reproduces the original plaintext transition and concurrent
creation bug, then checks encrypted passive transport, actual protobuf and
mDNS flags, reconnect/capability transitions, stable SQLite keys, malformed or
lost key handling, read-only retrieval, and shutdown serialization. It also
checks that the HTML loads dashboard.js and that the compiled asset matches
its input/output build receipt. CI runs as the runner UID inside the container,
so the generated private overlay remains readable without relaxing permissions.

The upstream developer-only `tools/gatt_client_check.py --real-proxy` uses the
old constructor convention. If you use that optional tool with this patched
source, pass `connections=True` explicitly to `DeviceBleProxyServer`. Its fixture
edit is intentionally outside the deployable runtime patch.

## Recovery and rollback

A latched HA repair may still need the existing correct key to complete its
reauthentication flow. Do not rotate keys or recreate entities as a routine
repair. Verify the same proxy becomes connected **and subscribed**, with
increasing forwarded advertisement counts. A loaded HA entry alone is not proof
that forwarding resumed. See the [Bluetooth guide](../../docs/bluetooth-proxy.md).

Malformed keys fail closed. If a key disappears during a running process, the
failure remains latched until a valid key is restored. After an entirely new
process starts, a deleted SQL NULL key cannot be distinguished from a legacy
proxy that never had one; restore the original database/backup instead of
relying on this patch to recover deleted credentials.

There is no database migration. Keep exact backups of your previous customized
runtime files and restore those to roll back, then restart the controller.
Rolling back also restores the original encryption-mode transition behavior.
