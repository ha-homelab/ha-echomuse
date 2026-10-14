# EchoMuse controller pilot

This guide describes the controller configuration. See the
[deployment record](deployment-record.md) for checks actually completed on the
pilot. Reviewed on 2026-10-13 against upstream controller tag
`controller-v2.26.0`, source commit
`e119433c0845dfe80f4b1ec44c9e8e8028adbb07`.

The initial scope is one previously converted second-generation Echo Dot. Leave
the first Dot on EchoLocal for comparison. Do not import EchoLocal runtime state
into EchoMuse's database or copy its wake-word files as if they were compatible.

## Version and image identity

The pinned controller is 2.26.0; the pinned device firmware is v2.18.0. These are
independent release tracks. The templates use the immutable multi-platform index:

`ghcr.io/wilbowes/echomuse-controller:2.26.0@sha256:3e28ccba1102b0ef1c10d3821c937730afc1fb78e5f6f3811f3860079fc0008b`

The registry advertises Linux amd64 and arm64 images. Its amd64 manifest is
`sha256:4f21aec35044644d9cec0ed15f941904f6232478d69665b8871031a9b97a6056`;
arm64 is `sha256:561795098168784e17acae74d817fb42a08fa18af9bde4f263101da71cbc2663`.
The published image runs CPU inference. No GPU or local compilation is required.

## Hosting

Use an always-on Linux host with a stable wired LAN address. The controller must
reach Home Assistant's response/media URLs, and the Dot must reach the
controller. The Docker template uses host networking, following upstream. The
Kubernetes template uses a single replica, `hostNetwork`, a pinned node,
`Recreate`, and a local-path volume. Do not apply both templates.

The proposed Kubernetes resource requests are starting reservations, not measured
requirements. Readiness verifies the HTTP process only; it does not verify a
Dot, its wake model, HA, or cloud speech providers. Local-path storage pins the
data to its node; it is not automatic failover or a backup.

Replace `REPLACE_WITH_CONTROLLER_NODE` and the documentation-only `192.0.2.10`
before applying the Kubernetes template. For Compose, copy `.env.example` to
`.env`, set `SERVER_IP`, create `controller-data` with private permissions, then
use `docker compose --env-file .env -f compose.yaml up -d` from the `deployments` directory. Keep `.env` and the
whole data directory ignored. The controller's default model runs on the Dot
after its assets are installed; continuous microphone streaming is not required.

## Network and authentication

The device-to-controller WSS link and the controller-to-HA ESPHome link are
separate. In controller 2.26.0 the voice ESPHome listener is passwordless;
do not assume the old EchoLocal Noise PSK protects it. Restrict these listeners
to the trusted LAN/private routed network and do not expose them publicly.


- TCP 8768: authenticated dashboard and HTTP API. First-run setup uses a one-time
  token printed in private container logs. Create an admin account immediately.
- TCP 8767: device WebSocket control/data/shell bootstrap.
- TCP 8770: device WSS link using the controller's own CA and a per-device token.
- TCP 16001 onward: one ESPHome native-API listener per approved Dot. The first
  Dot in this new controller normally gets 16001 even if it is the household's
  second physical Dot. Use the actual assigned port shown in the dashboard.
  In this release the voice listener is not password-protected; device-link WSS
  does not encrypt this separate HA connection. Restrict it to the trusted LAN
  and HA path, and never expose it to the Internet.
- UDP 5353 multicast: controller `_emcontroller._tcp` and satellite
  `_esphomelib._tcp` discovery. Routed VLANs require an existing reflector or
  explicitly configured controller endpoints/manual HA entry; publishing a
  Kubernetes Service does not make mDNS cross a routed boundary.
- Optional BLE proxy ports are satellite port +1000. BLE proxy and Sendspin remain
  off for the initial pilot. No new router port forwarding or public ingress is
  required.

Keep `DEVICE_APPROVAL=strict`. Approve only the intended pilot device after
checking its physical identity against the private backup. Preserve `/app/data`
in full: the SQLite database stores users, device credentials/configuration and
port allocation; `tls/` contains the controller CA/key and certificates. A fresh
CA breaks trust with previously paired Dots. Save a consistent database plus its
sidecars or stop the controller during a complete data-directory backup.

Leave `REQUIRE_DEVICE_TLS=0` only for bootstrap. Once the approved Dot shows
`wss (TLS)` and reconnects successfully, change it to `1` and restart the
controller. The dashboard's HTTP transport is separate from WSS. Use an existing
trusted HTTPS reverse proxy or an SSH tunnel for administrator access if the LAN
is not trusted. Do not publish bootstrap tokens, admin sessions, pairing keys,
device identifiers, database files, support bundles or transcripts.

## Home Assistant and the existing FCC pipeline

Home Assistant Container on Kubernetes has no Supervisor add-on store. Run this
separate controller and use HA's built-in **ESPHome** integration; no new custom
HA component is needed. EchoLocal HACS management does not manage EchoMuse.

1. Back up the second Dot and its existing HA entry privately. Leave the old
   entry in place until its replacement is validated; never alter the first Dot.
2. Install the supported device runtime and approve only that Dot in EchoMuse.
3. Confirm that the dashboard reports it online, the firmware version and wake
   assets match the chosen release, and its controller connection is encrypted.
4. In HA, go to **Settings → Devices & services → Add integration → ESPHome**.
   Use the controller's LAN IP and that Dot's assigned port, not the Dot IP and
   not EchoLocal's old 6053 port. If discovery works, confirm its identity and
   endpoint before accepting it. Do not re-use the old EchoLocal encryption key.
5. On the new satellite device, select the existing **FCC Russian Backup**
   assistant in its **Assistant** selector. Preserve the existing Russian STT,
   conversation and TTS configuration and the global preferred assistant.
6. Verify one action-button request first, then the stock **Hey Jarvis** wake
   word. This separates connectivity/provider issues from wake-word accuracy.
7. Check the completed HA pipeline and audible response; test a longer response
   and music only after a short turn succeeds. Update device-specific music
   routing to the new media-player entity after inspecting the existing mapping.
8. Disable the superseded second-Dot EchoLocal entry only after a successful
   acceptance and with its configuration preserved for rollback.

EchoMuse does not remove FCC quota, provider failures or latency: the same HA
pipeline still calls FCC. No HA long-lived token is required by the controller's
native ESPHome voice path. A hosted private-CA HA URL needs the relevant CA
mounted in the controller and `EM_EXTRA_CA_CERT` set; test fetching the actual
response URL rather than assuming that a working dashboard proves audio access.

## Initial wake and recording posture

Start from upstream's `hey_jarvis` model and 0.5 threshold. Its numerical scores
are not comparable to the old EchoLocal TFLite detector. Retain the default
on-device mode (`owwOnDevice: on`) and explicitly verify `saveUtterances: false`
and `wakeClipCapture: false`. A missing or incompatible wake model should leave
the Dot button-only; do not enable continuous server listening to mask a failed
model installation. Russian custom wake-word migration is a separate measured
experiment after the stock baseline works.

## Source references

- [Pinned deployment configuration](https://github.com/wilbowes/EchoMuse/blob/controller-v2.26.0/controller/docker-compose.deploy.yml)
- [Pinned environment variables](https://github.com/wilbowes/EchoMuse/blob/controller-v2.26.0/controller/.env.example)
- [Quickstart and HA integration](https://github.com/wilbowes/EchoMuse/blob/controller-v2.26.0/docs/quickstart.md)
- [Configuration, TLS and response URLs](https://github.com/wilbowes/EchoMuse/blob/controller-v2.26.0/docs/configuration.md)
- [Separate controller release process](https://github.com/wilbowes/EchoMuse/blob/controller-v2.26.0/.github/workflows/controller-release.yml)
- [Default device settings](https://github.com/wilbowes/EchoMuse/blob/controller-v2.26.0/controller/em_db.py)
