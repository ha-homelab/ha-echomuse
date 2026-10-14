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

### Diagnose a button that briefly lights and stops

The Dot-to-controller WSS link and the controller-to-HA ESPHome connection
are separate. A Dot can reach its controller while HA is unable to accept a
voice turn. In the pinned release, a button press in this state logs
`Dot button but no HA connection — standing down`. With the default ring
scene, the listening indication is held for 0.6 seconds, followed by the
orange `no_ha` cue, which clears itself. Check the log and connection state
alongside the color; a customized ring scene can look different.

Check the pilot's HA ESPHome connection, then test HA's HTTP listener from
inside its own runtime as well as from the controller. An unavailable local
listener, missing integration services, and `Session is closed` errors
across integrations indicate a wider HA availability problem. Preserve
logs and configuration before recovery, and identify which process is
unavailable before changing satellite settings.

For the Kubernetes deployment, a controlled restart of the affected HA pod
can recover a stalled HA process after diagnostics are saved. HTTP recovery
is only the first check: verify that the native ESPHome connection returns,
the selected Assist pipeline is available, and the required Music Assistant
services register again. Then repeat an attended short voice turn and the
physical music playback/stop test.

The behavior is defined by the pinned
[button handler](https://github.com/wilbowes/EchoMuse/blob/e119433c0845dfe80f4b1ec44c9e8e8028adbb07/controller/em_controller.py#L4255)
and [end-of-turn ring handling](https://github.com/wilbowes/EchoMuse/blob/e119433c0845dfe80f4b1ec44c9e8e8028adbb07/controller/em_controller.py#L1682).

## Music Assistant and the existing player dashboard

The pilot uses Music Assistant's existing **Home Assistant** and **Home
Assistant MediaPlayers** providers. After the native EchoMuse ESPHome player
appears in HA, append that entity to the MediaPlayers provider's selected
players. Preserve the other selections and provider settings. Verify that MA
imports an available player, then identify its exported HA queue entity; do
not infer its entity ID or require the same wrapper type as the old player.

Change only the pilot's voice-dispatch origin (new HA device and Assist
satellite) and music target (the MA queue entity). Preserve the Plex source,
queue defaults, and other rooms. Compare the current live scripts and
automation actions against any local generator before reloading: a full
regeneration can introduce unrelated changes. Keep private canonical bindings
consistent with the updated live routing and save a rollback copy.

The former EchoLocal Sendspin player does not follow the converted hardware
automatically. EchoMuse's own Sendspin integration is an optional, separately
paired route marked Early Access in this pinned release; it is disabled in
this pilot. No additional MA provider or HA custom component was needed.

An existing Lovelace auto-entities card can list available native and MA
players, but its presence does not establish that the operator can find the
new player. Inspect the actual media view and its filters. For this pilot,
the operator reported the player missing and an explicit card was added first
in the existing view's first grid. Existing dynamic cards were retained.

Use the new **Music Assistant queue entity**, not the superseded EchoLocal
player or an assumed entity suffix. With `mini-media-player` already installed,
an explicit card can use this placeholder configuration:

```yaml
type: custom:mini-media-player
entity: media_player.replace_with_music_assistant_queue
name: EchoMuse Dot 002
icon: mdi:speaker
artwork: cover
```

Replace the placeholder after inspecting the live HA entity. Save a private
dashboard backup, insert the card in the intended existing view, and read the
configuration back to verify that other cards and filters are unchanged.
Dashboard editing should not start playback. Test **«играй музыку»**, sustained
audible playback, and pause on the intended physical Dot separately.

### Check the advertised stream address

A successful voice acknowledgment does not prove that music can reach the
controller. Inspect the actual Music Assistant queue stream URL privately,
then test it from the EchoMuse controller's network environment. A URL that
works on the Music Assistant host may still advertise an old or unreachable
address to other clients.

For a Music Assistant deployment using host networking, verify that the
supported `streams.publish_ip` setting advertises the current, reachable
host address. The bind address and the advertised address serve different
purposes: do not advertise a wildcard bind address or blindly reuse a former
host's address. Preserve the stream port and other provider settings.

Before correcting this shared setting, save private configuration and queue
snapshots and make sure all affected players are idle. Change only the
advertised address through Music Assistant's supported configuration API or
settings interface. Verify the saved value and generated URL afterward;
do not edit database files to bypass configuration validation.

Retest the same queue flow from the controller. Check the HTTP response and
audio content type, then decode a bounded interval to confirm that actual
non-silent audio is available. Keep stream URLs, queue identifiers, and any
captured data private. This verifies transport and decoding only. Complete a
separate attended playback and stop test on the physical Dot before claiming
that music works.

For a bounded playback check, preserve queue contents and record the native
and MA player states, time to the first device audio frame, sent audio
periods, and the stop acknowledgment. A direct MA queue test verifies a
different path from a spoken command; validate voice dispatch separately.
Neither a `playing` state nor sent PCM proves what a listener heard.

If the conversation agent asks which player to use despite a known satellite
origin, inspect the exact STT result and native sentence match. Prefer-local
handling does not guarantee a match: an unlisted wording can reach the
conversation agent with `processed_locally: false`. In this pilot,
**«Играем музыку»** needed an additional alternative in the existing native
play grammar. The [canonical vocabulary fix](https://github.com/ha-homelab/ha-echo-show-5/pull/51)
includes origin and explicit-target recognition regressions. Validate such
changes with the installed Hassil runtime and preserve routing guards and
service actions; then repeat the actual spoken request.

Decoder-read stalls measure when the controller receives decoded data. They
can include startup and may be absorbed by playback buffers; they do not
alone prove audible glitches. Correlate them with actual playback underruns
and an attended listening result before changing buffers or audio settings.

In this pilot, the operator subsequently confirmed audible hiccups and
buffering. A later 9.141-second decoder starvation exceeded the Dot's
approximately 5.46-second fixed playback buffer, while inspected Wi-Fi health
was good. Trace the same stream through Music Assistant/Plex and the
controller, separating source delivery gaps from device-link loss. Record
the period tested and compare it with the listening report. Healthy Wi-Fi
at one checkpoint does not prove every network path is fault-free.

### Test queue-specific normalization when source delivery stalls

The pilot's source-processing chain used dynamic loudness normalization while
the Music Assistant host had high CPU pressure. Disabling normalization only
for this queue improved a bounded delivery trace. This is a targeted
mitigation, with post-change listening confirmation still pending; do not
assume it resolves every playback interruption. The saved queue policy
persists, and disabling normalization allows track-to-track loudness
differences.

1. Save private snapshots of the target queue, its ordered items, and its
   configuration. Record the current `volume_normalization` value and compare
   the other queues and global/player configuration after the change.
2. Through Music Assistant's supported `config/player_queues/save` API, set
   only the target queue's `volume_normalization` to `disabled`. The pilot's
   previous value was `global`, meaning it inherited the global policy.
   Saving this setting resumed the current track in the pilot; perform the
   test while attended and verify the selected track and queue order.
3. Observe a bounded interval and compare source-stall warnings, delivered
   audio, and the listener's experience. Separate initial startup waits from
   gaps during ongoing playback. Bytes acknowledged over WebSocket do not
   establish zero speaker underruns.
4. To roll back this pilot change, set the same queue field back to `global`.
   Restore a different original value if that was what the snapshot held;
   leave the global policy and other players unchanged.

The measured pilot stream had an initial 3.042-second wait and one 745 ms
wait, then approximately 53 seconds with no further starvation warnings.
A subsequent passive snapshot recorded a 3.488-second source stall without
a disconnect, reconnect, or stop. This supports continued investigation
and listening evaluation; it does not establish that hiccups are resolved
or that long-term playback quality is acceptable.

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
