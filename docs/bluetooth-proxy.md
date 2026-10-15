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

## Verified deployment — October 14, 2026

Both Dots have Bluetooth scanning and active connections enabled in persisted
configuration. Dot 2 was online: its encrypted ESPHome proxy was enrolled in HA,
HA subscribed, advertisements were forwarded, three slots were free, and HCI
errors/restarts were zero. No unidentified nearby GATT device was connected as a
test. Dot 1 was offline: its configuration, port and private key were prepared;
HA enrollment and runtime validation still require the device to reconnect.
