# Migrate one EchoLocal Dot 2 to EchoMuse

This runbook targets an already unlocked **Echo Dot second generation,
RS03QR / biscuit**, running **Fire OS 6, Android 7.1.2 / SDK 25** after amonet
2.0.0. It prepares a reversible pilot on one selected device. Completion of a
step below is not evidence that the later steps have passed; record actual
results in the [deployment record](deployment-record.md).

The software pins are EchoMuse firmware **v2.18.0**, controller
**controller-v2.26.0**, and **emOS v0.10**. The firmware and controller tags
resolve to source commit `e119433c0845dfe80f4b1ec44c9e8e8028adbb07`.

## 1. Confirm the device and installation route

Select one pilot by its privately recorded hardware identity. Match its live
identity before every session that can write to it. Keep another working Dot
unchanged as a comparison device; it need not be running EchoLocal. An IP address or room name alone is not
an identity check.

Read the OS version, root status, boot state, installed EchoLocal version,
storage capacity, and partition map. Save the results privately. Do not copy
serial numbers, addresses, credentials, or device logs into public examples.

**Use emOS for this Fire OS 6 device.** EchoMuse's older FireOS installation
flow supports Fire OS 5 / Android 5 and rejects amonet 2 devices. Do not force
that flow or downgrade bootloaders to make it pass. emOS instead retains the
device's own kernel and uses a new userspace; its init must match that kernel's
architecture. This device requires the **ARM32** path, which the image builder
also verifies from the boot image. See the pinned
[upstream compatibility rules](https://github.com/wilbowes/EchoMuse/blob/e119433c0845dfe80f4b1ec44c9e8e8028adbb07/docs/rooting.md)
and [installer refusal](https://github.com/wilbowes/EchoMuse/blob/e119433c0845dfe80f4b1ec44c9e8e8028adbb07/controller/static/dashboard.jsx#L4733).

**Continue when:** the intended pilot is identified and its OS/unlock state
matches this runbook.

## 2. Prepare the controller and Home Assistant

Run the pinned controller with private persistent storage and a stable address
reachable from both the pilot and Home Assistant. Keep its dashboard inside
the trusted network. Configure its administrator account and device approval
before enrolling the pilot.

The controller's normal device-link ports are TCP **8767** for the initial
plain connection and **8770** for TLS. The dashboard uses **8768**. Each admitted
Dot receives a separate ESPHome listener, normally starting at **16001**, on
the **controller's address**. Confirm the actual allocated port rather than
assuming every Dot uses the same port. mDNS helps discovery on the same
network; an explicitly configured controller endpoint is useful across routed
networks. See [upstream configuration](https://github.com/wilbowes/EchoMuse/blob/e119433c0845dfe80f4b1ec44c9e8e8028adbb07/docs/configuration.md).

Keep the intended Home Assistant Assist pipeline available: speech-to-text,
conversation agent, and text-to-speech must all work. EchoMuse changes the
satellite and controller; it does not make a cloud-backed Assist pipeline
independent of its cloud provider, quota, or latency.

**Continue when:** the controller is healthy, persistent data is backed up,
and its address and Home Assistant connectivity are verified.

## 3. Establish recovery and preserve the current installation

Network ADB is useful for inventory, backups, and staging. **Before the first
boot-partition write, connect a tested USB data cable and verify TWRP recovery
access on the selected pilot.** A Linux host with ADB/fastboot can provide
this access; the upstream browser wizard instead uses Chromium WebUSB and
Web Serial on a supported host. Do not confuse power from a USB port with a
working data connection.

Back up both current boot partitions, recovery and partition metadata,
`misc`/boot-selection metadata, and the existing EchoLocal installation:

- `/system/app/echod/echod`, its startup configuration and
  `/system/bin/ledcontroller` symlink target.
- `/data/misc/echolocal`, including state, identity, keys, and wake models.
- The current Wi-Fi configuration and relevant file permissions.
- Existing full-device recovery images from the original conversion, if
  available. Keep these as an additional recovery layer.

Use binary-safe transfers. Record byte counts and SHA-256 values, compare an
independent device read with the saved files, and keep a second private copy.
Keep complete partition backups even if a later image builder only needs the
boot-image portion. A locally computed hash of one unverified transfer does
not prove that transfer matches the device.

Read both boot headers and **both** system partitions' build properties.
Resolve `boot_a`, `boot_b`, `system_a`, and `system_b` through the device's
actual partition map; do not copy a block number from an example. All retained
boot/system slots must agree with the expected Fire OS generation. A partially
completed OS conversion must be repaired before this migration.

For amonet 2, upstream targets **boot_a** and keeps a usable original boot
image in **boot_b**. `ro.boot.slot_suffix` alone is not a reliable selection
rule for this bootloader. The donor boot image and its matching system
partition must be identified together. The wizard's
[slot-selection code](https://github.com/wilbowes/EchoMuse/blob/e119433c0845dfe80f4b1ec44c9e8e8028adbb07/controller/static/dashboard.jsx#L5129)
contains the relevant checks.

**Continue when:** USB recovery works, backups have verified hashes, the
partition map is recorded, and the original boot selection can be restored.

## 4. Build the emOS image offline

Clone upstream into a private working directory and check out the exact commit
above. Download the pinned `emos-v0.10/emos-payload.zip` from the
[official release](https://github.com/wilbowes/EchoMuse/releases/tag/emos-v0.10).
Its SHA-256 must be:

```text
5c2c4e02f17bfa3c5e9a83e189b64a41025f16b8bfe43f4e6accd430621b06b8
```

Run the repository's [offline builder](../scripts/build_emos.py). Set these
variables from the verified private inventory; `SYSTEM_PART` is the numeric
partition belonging to the **donor boot image's system slot**, not the boot
partition being replaced.

```sh
python3 scripts/build_emos.py \
  --source-dir "$ECHOMUSE_SOURCE" \
  --payload "$EMOS_PAYLOAD" \
  --reference "$ESCROWED_BOOT" \
  --reference-sha256 "$VERIFIED_BOOT_SHA256" \
  --system-part "$SYSTEM_PART" \
  --output private/prepared/pilot-emos.img
```

The builder requires a clean tracked upstream checkout at the pinned commit,
checks the executed source file against its committed Git blob, verifies both
input hashes, and uses the upstream parser and packer. It checks the ARM32
kernel/init pairing, preserves the kernel and device trees, and includes
`busybox`, `em-wifi`, `wpa_cli`, and `wpa_supplicant`. Those tools are necessary
on the Fire OS 6 path. An image made with only a manually selected init may
omit the networking tools; do not substitute that route.

Supply the **complete verified boot-partition backup** as the reference.
The builder keeps it unchanged and derives the page-aligned Android boot
image length from its header, matching the pinned wizard's
[reference-image slicing](https://github.com/wilbowes/EchoMuse/blob/e119433c0845dfe80f4b1ec44c9e8e8028adbb07/controller/static/dashboard.jsx#L7464).
The upstream roundtrip checks remain enabled on that bounded image. Beyond
the image, only zero padding or one canonical DER X.509 certificate followed
by zero padding is accepted; unknown nonzero bytes cause refusal. A reference
with a certificate requires the local `openssl` executable. Parsing the
certificate checks its structure, not its signature or authenticity.

The receipt records the full escrow hash and size, the bounded reference
hash and size, and the excluded trailer's hash and classification. This
distinguishes a complete recovery backup from the image supplied to the
packer; never replace the full backup with its shorter derived image.

It creates the image and a JSON receipt with mode **0600** and refuses to
replace either existing file. It does not contact a device or flash anything.
Its numeric `--system-part` validation cannot prove the physical partition
mapping; that remains the preceding inventory checkpoint. Keep both outputs
private: the image contains the device's original kernel and device trees.

**Continue when:** the builder succeeds, the receipt matches the intended
inputs and partition, and the resulting image fits the target partition.

## 5. Stage firmware, credentials, and wake assets

Download the pinned [firmware v2.18.0](https://github.com/wilbowes/EchoMuse/releases/tag/v2.18.0)
and verify its SHA-256:

```text
6c9262dfd4938cd8abb8532d006b396e90fdf81b921873f9bc015e48b852cb9b
```

The binary uses `/system/bin/linker` and the system libraries `libm.so`,
`libtinyalsa.so`, `libdl.so`, `liblog.so`, and `libc.so`. Its `version` and
`board` subcommands can check execution and hardware discovery without
starting the daemon. A bare invocation starts the audio stack and changes
services; do not run it alongside EchoLocal.

Following the pinned upstream installer, stage:

- Firmware at `/data/local/bin/server_a`, mode 0755, and a relative
  `/data/local/bin/server` symlink to `server_a`.
- The exact pinned
  [startup script](https://github.com/wilbowes/EchoMuse/blob/e119433c0845dfe80f4b1ec44c9e8e8028adbb07/controller/device_payloads/start_server.sh)
  at `/data/local/bin/start_server.sh`, mode 0755.
- Per-device TLS credentials from the administrator API
  `POST /api/provision/tls_credentials`, with the pilot's private device ID.
  Store the returned CA at `/data/local/etc/echomuse/ca.pem`, mode 0644, and
  token at `/data/local/etc/echomuse/token`, mode 0600. Do not log the response.
- The intended controller endpoint configuration at
  `/data/local/etc/echomuse/controller.json`. The controller API
  `GET /api/provision/controller_endpoints` provides its configured file.
  If mDNS is disabled, ensure the explicit address is reachable and has a
  recovery plan if it changes.
- On-device wake assets from `GET /api/provision/oww_assets` and the individual
  `GET /api/provision/oww_asset/{name}` endpoints, under
  `/data/local/share/echomuse/oww`. Verify their advertised size and digest
  after transfer. This includes ONNX Runtime, the shared feature models,
  selected classifier, and the supported speech-gating model.

Preserve a valid `/data/misc/wifi/wpa_supplicant.conf`; it needs a control
socket and persistent updates. Verify `ctrl_interface=/data/misc/wifi/sockets`
and `update_config=1` without printing network credentials. Preserve the
network entries and appropriate Wi-Fi ownership (UID/GID 1010) and mode 0660.
Never replace a valid configuration with an empty template.

Use on-device detection for the initial pilot. Start with a supplied
openWakeWord model such as **Hey Jarvis**. EchoLocal's microWakeWord TFLite
files for «Привет, Мышка» cannot simply be copied into EchoMuse's ONNX model
directory. Custom phrase training and evaluation is a separate stage.

**Continue when:** all staged bytes and permissions verify, the controller
knows the pending pilot, and Wi-Fi/controller settings have been checked.

## 6. Install through verified USB recovery

Reconnect to the pilot in TWRP and repeat the identity and partition checks.
Keep the first Dot outside this session. Upload the prepared image to a
temporary file and verify its digest **before** a partition write.

Use the upstream wizard's verified write procedure or an equivalently guarded
operator procedure. It writes only the resolved target boot partition, keeps
the original boot image available, checks the write's result and byte count,
flushes storage, drops the page cache, and compares an independent readback
of **exactly the image length**. Check the actual `dd` capabilities: some
Fire OS 6 recovery builds reject `conv=fsync`. Never infer success from speed,
exit status alone, or a cached read. See the
[upstream write and restore implementation](https://github.com/wilbowes/EchoMuse/blob/e119433c0845dfe80f4b1ec44c9e8e8028adbb07/controller/static/dashboard.jsx#L7740).

Set and verify the selected boot slot using the device's supported boot-control
tool, retaining the original selection for rollback. Do not write guessed raw
boot-control bytes. If any verification fails, **remain in recovery**, restore
the escrowed image, and verify it before rebooting.

**Continue when:** the intended partition's uncached readback matches the
prepared image and boot selection is verified.

## 7. Boot emOS and enroll the pilot

For ongoing access after enrollment, see
[device access and administrator credentials](device-access.md), including
the network Console, optional USB password and the absence of ADB in emOS.

Watch the first boot through the USB serial console. emOS has **no ADB daemon**;
loss of network ADB is expected and is not proof of failure. Verify emOS's
reported version, Wi-Fi association, an IP lease, and the controller
connection. A saved compatible Wi-Fi configuration may reconnect immediately.

Use the pinned [USB console helper](https://github.com/wilbowes/EchoMuse/blob/e119433c0845dfe80f4b1ec44c9e8e8028adbb07/emos/tools/emconsole.py),
which sets raw mode, flushes pending input, and performs the newline handshake
before issuing commands. After USB re-enumeration, match the device's serial
and the node's major/minor numbers against sysfs; a retained node or buffered
text alone is not evidence of a failed boot. emOS identifies itself as USB
**1949:2007**, manufacturer **EchoMuse**, product **emOS** in the tested v0.10
payload (the pinned source also uses **emOS console**). Confirm a
shell response and `/etc/os-release` before considering another reset.

If Wi-Fi needs configuration, use `em-wifi` from the USB console or the
pinned wizard's console step. emOS prefers `/data/emos/wpa.conf` and falls
back to Android's existing configuration when its own file is absent. A
manual `wpa_cli` command must select `wlan0` and the control socket declared
in the active configuration. Save changes and call `sync`. Do not put
passwords in public logs or shell history. This path requires a compatible
WPA2 network; do not assume WPA3-only service will work.

Approve only the verified pilot in the EchoMuse dashboard. Credential issuance
alone does not approve the device. Verify its version, link security,
microphone state, loaded wake model, and allocated ESPHome port.

In controller 2.26.0, an authenticated but unapproved device updates its pending
record and then disconnects before joining the live device map. Consequently,
`connected` and `linkTls` can remain false until approval. Before approving,
require a recent authenticated contact for the exact device, the expected
firmware, its separately issued credentials, and successful USB boot checks.
After approving, require a live TLS connection and verify the emOS and firmware
versions. Initial version telemetry can arrive after the connection becomes
live; wait for all three conditions within a bounded deadline before enrolling
HA, without issuing a second approval or rotating credentials. A record
created during credential issuance alone is not proof that
the device has booted or contacted the controller.

In Home Assistant, use **Settings → Devices & services → ESPHome**. Accept
the discovered EchoMuse satellite, or add the controller's address and the
pilot's allocated port manually. Controller 2.26.0 exposes this ESPHome
voice listener without a password or Noise encryption key; do not reuse
EchoLocal's key. Keep it on the trusted LAN. The device-to-controller WSS
credentials protect a separate connection. Assign the intended Assist
pipeline and language to that satellite. Preserve the old pilot configuration for rollback; pause its
obsolete EchoLocal integration entry if it otherwise produces failed
connections. Do not alter the comparison Dot's entry.

Update the existing audio-player dashboard to target the new pilot entities
only after verifying their mapping. Entity IDs and media-player services may
differ from EchoLocal, so existing automations need explicit review.

**Continue when:** the controller and HA both identify the intended pilot,
and its Assist pipeline is selected.

## 8. Verify operation before expanding the pilot

Test button-triggered listening and a complete spoken request/reply first.
Then test the supplied wake word at normal voice level, from the intended
position, and over representative room noise. Observe an idle interval long
enough to assess false activations; a few quiet minutes are only a smoke test.
Test microphone mute, volume, playback, interrupting a reply, and power-cycle
recovery while USB recovery remains available.

Record observed results separately from expectations. If the selected Assist
pipeline uses FCC or another cloud service, test those stages independently
when a request fails. Success at wake detection does not establish successful
speech recognition, conversation, or playback.

Do not migrate another Dot or deploy the custom Russian wake phrase until the
pilot meets the agreed acceptance checks.

## 9. Migrate another existing EchoLocal unit

Treat each Dot as a separate migration even when the model, Fire OS release and
intended EchoMuse version match. The second hardware unit completed the earlier
button, wake and music checks. The operator has now requested the same system on
the first unit, while postponing the newer Russian-voice listening test. That
test remains pending independently of firmware preparation.

The first unit's historical inventory identified an unlocked Dot 2 with amonet2,
Fire OS 6 / Android 7.1.2 and TWRP 3.7. That supported preparing the same ARM32
emOS route, but did not replace current USB inventory. Work stopped at local
preparation until physical USB became available. On October 14 the operator
connected the first unit, its live identity and layout were verified, and it
was migrated using its own fresh recovery copies. The [deployment record](deployment-record.md#october-14-2026--first-dot-migration)
separates completed firmware and integration checks from acoustic acceptance.

Repeat the migration in this order:

1. Connect the intended first Dot to the NAS with a tested USB data cable,
   initially without holding buttons. Match its USB serial to the private
   inventory. A unit in an unexpected state must be investigated before any
   reboot. Keep the already working EchoMuse unit running normally.
2. Create a separate per-device workspace and isolated USB maintenance session.
   Read current firmware, root access, partition map and identity. Never import
   the completed pilot's target state or run its dated private scripts unchanged.
3. Take fresh full boot, recovery and boot-control backups, plus EchoLocal
   runtime and Wi-Fi state. Verify independent partition reads and copy the
   verified escrow to another host. An old pre-wipe or pre-conversion backup is
   recovery insurance, not the current EchoLocal configuration to restore.
4. Enter and verify recovery, inspect both donor slots read-only, then build the
   image from this unit's own verified boot backup. Derive the system partition
   from that inspection. Do not reuse another Dot's prepared image, even when
   both devices report the same release.
5. Issue separate device credentials and prepare the pinned firmware and wake
   assets. Stage only the new EchoMuse paths, preserving Wi-Fi and EchoLocal
   state. Review a dry-run result before explicitly enabling the target boot
   write. Independently verify readback and unchanged retained partitions
   before requesting a boot.
6. Verify emOS through USB and the authenticated controller connection. Approve
   only this unit under its distinct label. Read its actual allocated ESPHome
   port; the working unit already owns its own port. Controller-wide TLS and
   recording settings do not need changing.
7. Enroll a new HA ESPHome entry and assign the validated household pipeline
   to both Assistant selectors. The current documented baseline is **Local
   Russian Home** with Irina; the original migration used **FCC Russian Local
   Voice**. Preserve the original entry configuration privately for rollback.
   Resolve new entity IDs from the registry rather than guessing suffixes.
8. Add its native player to the existing Music Assistant provider. Update only
   its originating-device music routes and add its card to the existing audio
   view. Preserve the other unit's routes and card. Apply the proven per-queue
   normalization choice to the new queue explicitly, without changing global
   normalization settings.
9. Verify transport and actual generated audio, then perform the deferred
   attended button, wake and music checks when the operator is available. Mark
   firmware, HA integration and acoustic acceptance separately.

The original migration wake baseline was **Hey Jarvis**. Both pilot Dots later
received the [«Привет, Мышка» model trial](russian-wake-word.md); its independent
room-distance acceptance remains pending. The old personal microWakeWord
TFLite files cannot be copied into EchoMuse's ONNX detector. Firmware conversion
does not establish Russian wake-word accuracy or solve speech-model errors by
itself. See the [Russian voice operations](russian-voice-operations.md) for the
independent server-side pipeline and rollback.

If adding the new native player causes Music Assistant exports to disappear
while the native HA players remain available, inspect the HA provider connection
before changing speaker settings. During this migration, the `hass_players`
reload encountered a disconnected HA client. Reloading only the HA connection
provider and then `hass_players`, through `config/providers/reload`, restored
both Dots. Preserve the complete selected-player list and other provider
configuration, and verify the existing Dot as well as the new one. An unrelated
selected player that was already unavailable should not trigger repeated
reloads. This recovery does not establish that the underlying client error is
permanently fixed.

## Roll back to EchoLocal

Boot the pilot into TWRP using the verified USB recovery route. A responsive
emOS console supports `/init recovery`; if userspace does not start, use the
device's physical recovery entry procedure established before installation.

Restore the **exact escrowed boot image** to the recorded original target,
verify an uncached byte-for-byte readback, and restore the original boot
selection if it changed. Preserve the EchoLocal system files and data. The
staged EchoMuse files under `/data/local` can remain inert during recovery;
deleting all of `/data` would destroy the configuration being restored.

After reboot, verify the EchoLocal executable/version, its `ledcontroller`
startup mapping, resident state, network address, and encrypted ESPHome
connection. Re-enable the pilot's original HA entry if retained; if it was
removed during cleanup, re-enroll EchoLocal using its private preserved endpoint
and key, then restore its dashboard and automation mappings. Entity IDs may
change after re-enrollment. Confirm a complete spoken exchange before declaring
rollback complete.

emOS's automatic recovery handles some unsuccessful boots when its init runs
and a known-good image is available. **It cannot recover a kernel or init that
never starts**, and a first migration has no previously accepted emOS image to
rely on. USB access and verified escrow remain necessary. See
[upstream recovery limits](https://github.com/wilbowes/EchoMuse/blob/e119433c0845dfe80f4b1ec44c9e8e8028adbb07/emos/init/init.c#L726).
