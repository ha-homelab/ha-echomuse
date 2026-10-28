# EchoMuse Bluetooth proxy

Controller 2.26.0 and device firmware 2.18.0 support BLE advertisement forwarding
and optional active GATT connections. This is a Bluetooth Low Energy proxy for
Home Assistant sensors/integrations, not Bluetooth speaker pairing or A2DP music.

## Enable and enroll

1. Enable **Bluetooth proxy** (`bleProxyEnabled`) for the Dot in the EchoMuse
   Controller. Enable **Connections** (`bleProxyConnections`) for active GATT
   clients. Keep the remaining effective device configuration intact.
2. Note the controller's allocated proxy port. The proxy endpoint is on the
   **controller host**, not the Dot. Each Dot gets its own endpoint; the voice
   ESPHome endpoint is separate.
3. Retrieve that proxy's encryption key through the controller's administrator
   interface. The administrator API is
   `GET /api/devices/{device_id}/ble_proxy/key`. Keep its Noise PSK private; it is
   not the controller password, device WSS credential, or voice API key. A
   never-enrolled passive proxy has no key; enabling active connections
   provisions one and requires HA to use it.
4. In HA, select **Settings → Devices & services → Add integration → ESPHome**.
   Enter the controller host and allocated BLE proxy port, then its encryption
   key. Keep the existing voice integration. Give the new entry an identifiable
   name such as **EchoMuse Kitchen BT Proxy**.
5. Verify the entry is loaded, HA is connected and subscribed in the controller,
   and BLE advertisement counters increase. Active connections additionally need
   free connection slots. The reported limit on this deployment is three.

Only expose the proxy to the trusted HA network. Do not publish private
addresses, encryption keys, captured nearby device addresses, or inventory.

## Persistent authentication with the controller fix

The repository's fix for the pinned **Controller 2.26.0** separates transport
encryption from permission to make active GATT connections. It is a local
controller patch, not a new upstream release or a Dot firmware update. The
unpatched image retains the behavior described in the warning below.

Use the [pinned patch and manifest](../patches/echomuse-2.26.0/manifest.json)
with [the source-checking helper](../scripts/apply_ble_auth_patch.py). The helper
checks source hashes by default; `--output` creates a separate overlay directory.
It does not edit the input tree, contact a service, deploy files or restart the
controller. Review custom API source explicitly so existing recorder changes
survive. Follow the [overlay and rollback precautions](operations.md#backup-cleanup-and-rollback)
before deployment.

- An assigned, valid Noise key stays in use when **Connections** is turned off,
  when firmware lacks active GATT support, and after an ordinary reconnect or
  restart. Passive advertisement forwarding can remain encrypted.
- Active GATT requires both an encrypted transport and the enabled, supported
  Connections feature. Turning Connections off removes active handlers and
  features without opening a plaintext endpoint.
- Turning **Bluetooth proxy** off stops its listener. Re-enabling it preserves
  the stored key and the existing proxy identity and port.
- A never-enrolled passive proxy with no stored key retains its existing
  plaintext behavior. First enabling supported active connections creates one
  key; an already enrolled passive HA entry then needs that key through reauth.
  The fix does not silently migrate every passive installation to encryption.
- The administrator's **Show encryption key** action reads stored state without
  creating a replacement key. It remains available for an encrypted passive
  proxy. Missing or malformed storage requires recovery, not repeated clicks.

Malformed keys disable the listener instead of falling back to plaintext. If a
running encrypted proxy loses its stored key, reconciliation also disables the
listener and remembers that failure for the lifetime of the process. Restore a
valid backed-up key before retrying. A new process cannot distinguish an erased
SQL NULL key from a passive proxy that never had one; this fix cannot recover
lost enrollment history. Persistent storage and a verified backup remain
necessary. Deleting and recreating the controller's device record also loses
its stored key and is not an authentication repair.

The fix does not clear an existing HA reauthentication request automatically.
Complete the same-entry recovery below after the encrypted endpoint is stable.

## Operational limits and diagnostics

The scanner shares device resources with Wi-Fi and audio. Brief scanning yields
are expected during voice/music activity. Track HCI errors, restarts, received
advertisements and forwarded advertisements separately. A growing receive count
without forwarding can mean HA has not subscribed.

An earlier slot-status workaround toggled **Connections** off and on. **Do not
use that workaround on the unpatched 2.26.0 controller.** That version couples
active GATT support to transport encryption: the same BLE endpoint can briefly
switch from Noise encryption to plaintext. Home Assistant can then stop retrying
and request reauthentication even though its stored key is still correct.

If the slot count looks wrong, first distinguish a stale report from occupied
GATT slots. Check the scanner, controller connection and advertised slot count.
Do not change transport security to refresh a status display. Reload only the
identified BLE ESPHome entry after its encrypted endpoint is stable and no GATT
client is using it. A correct slot count alone does not prove that every GATT
device works.

An offline Dot has no listening proxy endpoint even when a port and encrypted
configuration have been allocated. Wait for it to reconnect before enrollment;
do not fabricate a loaded HA entry or use another Dot's endpoint. Root Console
sessions may pause Bluetooth while they are open.

## “Authentication expired” in Home Assistant

The BLE proxy uses a persisted 32-byte Noise pre-shared key. It does not have a
scheduled expiration time. This repair message can also mean that Home
Assistant encountered an unexpected encryption mode, a different endpoint, or
an invalid key. Do not rotate a working key or delete an integration just
because the message uses the word “expired”.

1. Identify the affected **BLE** ESPHome entry by its device identity, controller
   host and allocated BLE port. Keep voice and unrelated Bluetooth entries out
   of the repair. A matching display name alone is insufficient.
2. Check that the intended Dot is connected and the controller reports the BLE
   endpoint as encrypted. Confirm the key against the controller's private
   administrator interface; never paste keys into logs, issues or screenshots.
   Do not accept an encryption-removal prompt to bypass an expected encrypted
   endpoint.
3. If the identity, endpoint and key match, restore the entry using Home
   Assistant's reauthentication flow with that same key. Do this only after the
   endpoint's encryption mode is stable. Preserve the existing entry and its
   entities instead of enrolling a duplicate.
4. Verify the entry is loaded, the controller reports HA connected and
   subscribed, and advertisement counters increase between observations.
   Confirm that the repair disappeared; dismissing it alone does not repair
   authentication. Recheck voice/player availability separately.

If the endpoint or MAC identity differs, use the intended proxy's endpoint and
HA's supported reconfiguration flow before retrying credentials. If the key
really changed, first establish whether the database or device record was
replaced; restore the original key from backup, or reauthenticate the verified
existing entry with the intended current key. Remove an entry only after
confirming that it is obsolete: follow the
[EchoLocal cleanup procedure](#remove-obsolete-echolocal-entries) or, for a Dot
that has moved away from EchoMuse, the
[controller identity retirement procedure](#retire-an-echomuse-identity-after-migrating-a-dot).

The controller's status fields describe different stages: `listening` means
the endpoint exists; `encrypted` describes its transport; `haConnected` alone
does not prove completed authentication; `haSubscribed` and fresh
`advertsForwarded` progress demonstrate useful HA traffic. If advertisements are
being received but not forwarded, check subscription and authentication before
changing radio settings. Zero active GATT slots is a separate diagnosis.

Keep the controller database and its device-link certificates on persistent
storage. Back them up together before a controller change. A recoverable SQLite
backup must include committed WAL data; copying only a live database file is
not sufficient. Keep all snapshots, key comparisons and device inventories
private.

For restart acceptance, compare the existing BLE identity, port and key before
and after, then verify HA reconnects without reauthentication. Test transport
and GATT capability transitions in an isolated regression test, not by changing
encryption on a household proxy in use.

Home Assistant 2026.10.0's ESPHome implementation starts reauthentication and
stops reconnecting for relevant encryption/authentication errors. Its reauth
flow validates the device identity before updating the existing entry. This
explains why restoring the old encryption mode alone may leave a repair open;
it does not prove which error originally affected a particular installation.
See the [ESPHome connection manager](https://github.com/home-assistant/core/blob/2026.10.0/homeassistant/components/esphome/manager.py)
and [reauthentication flow](https://github.com/home-assistant/core/blob/2026.10.0/homeassistant/components/esphome/config_flow.py).

## See what the proxy receives

Open HA's [Bluetooth panel](https://my.home-assistant.io/redirect/config_bluetooth/)
under **Settings → Connectivity → Bluetooth**. Inspect the adapters and their
capabilities, then the [advertisement monitor](https://my.home-assistant.io/redirect/bluetooth_advertisement_monitor/)
and [connection monitor](https://my.home-assistant.io/redirect/bluetooth_connection_monitor/).
The [official Bluetooth guide](https://www.home-assistant.io/integrations/bluetooth/)
explains these views. Observed advertisements and active GATT connections are
different: a working scanner can have no active connections.

Confirm fresh timestamps or increasing counters over an observation interval;
a single nonzero total may be old. Correlate the source with the current
EchoMuse proxy. Multiple copies of a display name are not proof of multiple
physical radios. Nearby addresses and payloads can identify household or
neighbouring devices, so keep captures private.

Check sensor units when comparing different satellite systems. The EchoMuse
advertisement sensor is a cumulative `total_increasing` value; the TECHO5
sensor observed in this deployment reports an advertisement rate in `/s`.
A falling TECHO5 rate is not a counter reset. Use fresh source-attributed HA
advertisement events to establish reception from either implementation.

## iBeacon Tracker is a consumer, not another proxy

The path is **beacon → Dot's BLE scanner → EchoMuse proxy → HA Bluetooth →
iBeacon Tracker**. Adding iBeacon Tracker installs a consumer for supported
beacon advertisements; it does not create another radio or require another Dot.
It is optional for voice, music and other Bluetooth integrations.

HA creates devices as qualifying beacons are discovered. An empty integration
alone does not show that the proxy failed. Unnamed beacons require an explicit
UUID allowlist in the integration options; changing major/minor identifiers can
also prevent stable discovery. Estimated distance uses received signal strength
and ideal radio assumptions. Treat it as rough proximity, not room-accurate
position. Check the source attribute because the strongest receiving adapter
can change. See the [official iBeacon Tracker documentation](https://www.home-assistant.io/integrations/ibeacon/)
for configuration and calibration. Do not build critical actions on one
unvalidated proximity sample.

## Remove obsolete EchoLocal entries

An old EchoLocal scanner may remain in HA after the same physical Dot has booted
emOS. The new EchoMuse proxy has its own generated Bluetooth identity, so a
different address is not evidence of an extra physical Dot. Compare the current
controller endpoint, HA integration and active scanner before deleting anything.

1. Save the old integration configuration and recovery information privately.
   Check cards, scripts and automations for old entity references.
2. Identify the obsolete **ESPHome** entry and its associated **Bluetooth**
   entry. Keep the current EchoMuse voice entry and encrypted BLE entry.
3. Remove only the obsolete entries through HA's integration controls. Do not
   edit live `.storage` files or erase the Dot to clean up a registry record.
4. Verify the current scanner, fresh advertisements, current voice/player
   entities and dashboard references independently.

During the October 14 cleanup, two former EchoLocal ESPHome entries and two
associated Bluetooth entries were removed after backup. HA removed 14 old
device records and 212 old entity records, with no HA restart required. The
current EchoMuse BLE entry remained loaded with three free slots. These are
results from that cleanup, not expected counts for other installations. The
first Dot had not yet been enrolled as an active EchoMuse proxy at that checkpoint.

## Verified deployment — October 14, 2026

Both Dots have Bluetooth scanning and active connections enabled in persisted
configuration. Dot 2 was online: its encrypted ESPHome proxy was enrolled in HA,
HA subscribed, advertisements were forwarded, three slots were free, and HCI
errors/restarts were zero. No unidentified nearby GATT device was connected as a
test. Dot 1 was offline: its configuration, port and private key were prepared;
HA enrollment and runtime validation still require the device to reconnect.

## Retire an EchoMuse identity after migrating a Dot

When a physical Dot moves to another satellite system such as TECHO5, HA can
retain its disabled EchoMuse voice, BLE and scanner entries. A disabled entry
does not represent an active second radio. A proxy belonging to another
physical Dot remains a separate valid device.

The controller registers mDNS advertisements for approved offline devices even
though their TCP listeners are stopped. Deleting only the old HA entries can
therefore cause rediscovery. First identify the migrated record and check its
entity references, including the local assistant's media-player allowlist.
Preserve other physical Dots and their controller configuration.

Use a bounded private SQLite online backup before retirement; a raw copy of a
live database can omit WAL data. Preserve required training and utterance
recordings separately and verify their hashes. The controller administrator's
`DELETE /api/devices/{device_id}` operation, verified on the deployed controller,
removes that device's voice and BLE listeners and mDNS registrations. It is a
hard delete: configuration, keys, device logs, boot/wear records, wake samples
and ordinary utterance recordings are removed. The separate training-recorder
directory is outside that deletion path. Check the actual storage layout before
relying on this distinction. Retained historical metrics cannot recreate a
device advertisement without its approved registry record.

Then remove only the corresponding obsolete ESPHome and Bluetooth entries
through HA's integration controls. Its supported administrator API is
`DELETE /api/config/config_entries/entry/{entry_id}`; do not edit live `.storage`
files. Disabling `bleProxyEnabled` tears down BLE alone and preserves the old
voice advertisement, so it is not complete retirement.

On October 27, the migrated Dot's old record and three HA entries were removed
after an integrity-checked online database backup and preservation of 56
training files. The archive was approximately 2.65 MB compressed. HA removed
three old device records and ten entity records; the other physical Dot's
controller configuration remained unchanged. These are observed cleanup counts,
not a general deletion target. The current TECHO5 migration and final acceptance
record are maintained in
[ha-techo5-dot](https://github.com/ha-homelab/ha-techo5-dot/blob/main/docs/home-assistant.md#retire-the-former-controller-identity).

The other physical Dot's encrypted EchoMuse BLE endpoint was then enrolled in
HA and successfully subscribed. After a separate TECHO5 radio outage was
recovered with a normal device reboot, a 45-second HA observation received
12 fresh TECHO5 reports and 4 fresh EchoMuse reports, excluding 42 cached reports.
Both satellites remained idle and their saved wake/assistant settings were
preserved. This verifies observed recovery, not long-term absence of radio
failures. Final HA verification showed exactly two loaded Bluetooth entries,
one per physical Dot, with the obsolete entries absent and no pending ESPHome
setup flows or related repairs.

Verify absence of the retired identity, fresh advertisements from each intended
scanner, and current voice/player availability independently. No full Alexa
filesystem backup or device reflash is required for registry cleanup.
