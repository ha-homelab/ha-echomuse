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
   not the controller password, device WSS credential, or voice API key.
4. In HA, select **Settings → Devices & services → Add integration → ESPHome**.
   Enter the controller host and allocated BLE proxy port, then its encryption
   key. Keep the existing voice integration. Give the new entry an identifiable
   name such as **EchoMuse Dot 002 BT Proxy**.
5. Verify the entry is loaded, HA is connected and subscribed in the controller,
   and BLE advertisement counters increase. Active connections additionally need
   free connection slots. The reported limit on this deployment is three.

Only expose the proxy to the trusted HA network. Do not publish private
addresses, encryption keys, captured nearby device addresses, or inventory.

## Operational limits and diagnostics

The scanner shares device resources with Wi-Fi and audio. Brief scanning yields
are expected during voice/music activity. Track HCI errors, restarts, received
advertisements and forwarded advertisements separately. A growing receive count
without forwarding can mean HA has not subscribed.

On the tested release, initial connection-slot status remained **0 free / 3**
with no connections after scanner startup. After confirming scanning was active
and no GATT clients were connected, disabling **Connections**, saving, then
re-enabling it refreshed the snapshot to **3 free / 3**. Reloading only that BLE
ESPHome entry restored HA's subscription. Preserve the PSK and all other config.
This is a startup-state workaround, not proof that every GATT device works.
Do not toggle active connections when an integration is using them.

An offline Dot has no listening proxy endpoint even when a port and encrypted
configuration have been allocated. Wait for it to reconnect before enrollment;
do not fabricate a loaded HA entry or use another Dot's endpoint. Root Console
sessions may pause Bluetooth while they are open.

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
