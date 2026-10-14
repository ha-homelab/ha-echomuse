# Deployment record

## October 13, 2026 — controller and pilot preparation

The selected pilot is the second converted Dot. Its live USB identity was
matched to the existing private inventory before any write. The first Dot was
not changed; it was offline during this session, so no comparison result is
claimed.

Read-only inspection confirmed BISCUIT/Puffin hardware, root access, Fire OS 6
(Android 7.1.2 / SDK 25), and EchoLocal 0.0.8. The supported route is emOS;
upstream's FireOS in-place installer rejects this operating-system base.

Completed checks:

- Controller 2.26.0 deployed on a dedicated Kubernetes workload on an existing
  wired Linux host, using the pinned image digest and private persistent data.
  Administrator setup is closed and unauthenticated device API requests fail.
- Strict device approval, on-device wake mode, and the supplied Hey Jarvis
  model are configured. Utterance saving and wake-clip capture are disabled.
- Both original Home Assistant entries, the Assist pipelines, related registry
  entries, and the existing household music routing were backed up privately.
- A tested USB data cable connects the pilot to the maintenance host. TWRP
  3.7.0 and amonet 2 were verified. Both boot images and both system partitions
  match the expected Fire OS 6 / ARM32 layout and required donor files.
- Full boot, recovery, and boot-control partition backups were independently
  read and compared. EchoLocal runtime and Wi-Fi state were preserved. Copies
  on both the maintenance host and operator's Mac have verified hashes.
- The offline emOS v0.10 build uses the pilot's own kernel. A detached X.509
  certificate and partition padding follow its Android boot image. The builder
  now checks those bytes and extracts the same bounded image as upstream's
  wizard, retaining the full escrow and upstream byte-for-byte roundtrip check.
- Firmware v2.18.0, startup script, eight wake assets, and per-device connection
  files were staged with verified hashes and modes. Existing Wi-Fi is unchanged.

## October 13, 2026 — verified installation and first boot

The prepared emOS image was written only to the resolved `boot_a` partition.
An uncached full-partition read matched the image plus the untouched remainder.
`boot_b`, recovery, and boot-control metadata were byte-for-byte unchanged.

The pilot booted emOS, obtained Wi-Fi connectivity from its preserved settings,
and started EchoMuse v2.18.0. USB reported the expected EchoMuse/emOS identity.
The upstream console helper established a working shell without another reset;
its raw-mode setup and input flush avoided stale serial data. Device logs
showed a WSS connection to the intended controller and pending approval.

The exact pilot was approved after its firmware, identity, and authenticated
WSS contact were verified. Mandatory device TLS was then enabled; the
controller restarted and the Dot reconnected successfully. It reports local
wake detection with microphone streaming disabled.

A separate Home Assistant ESPHome entry was created against the controller's
allocated listener. Its new identity does not collide with the old EchoLocal
entry. Both new Assistant selectors explicitly use **FCC Russian Backup**.
The old entries and global pipeline configuration were verified unchanged.

## Attended voice smoke test

A button-triggered Russian question, «Сколько будет два плюс два?», completed
successfully and the operator confirmed the audible answer «четыре».
Controller metadata recorded an `ok` turn lasting 13.473 seconds in total,
zero playback underruns, and a maximum packet gap of 89 ms. These are one
turn's observations, not average latency or a long-term reliability result.
No utterance audio was saved. The device returned to local wake listening,
with WSS and Home Assistant still connected.

Wake-word and music acceptance are still in progress at this checkpoint.
