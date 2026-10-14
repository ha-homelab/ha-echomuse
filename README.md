# ha-echomuse

Reproducible EchoMuse deployment and Home Assistant integration for existing
Amazon Echo Dot 2 devices. This is an independent deployment and migration
project, not a fork or official distribution of
[EchoMuse](https://github.com/wilbowes/EchoMuse).

## Current status

Both existing Echo Dot 2 units now boot **emOS v0.10** and run **EchoMuse
v2.18.0**. Each image was built around that unit's own ARM32 kernel from
Fire OS 6 / Android 7.1.2, with separate credentials and verified private USB
recovery backups. The second unit was the original pilot; the first unit was
migrated on October 14. See the [repeat migration procedure](docs/migration.md#9-migrate-another-existing-echolocal-unit).

Controller **2.26.0** is deployed separately, and both units have reached it over
WSS using device-specific credentials; TLS is required. Home Assistant
ESPHome enrollment is complete for both. The initial pilot migration used the existing
FCC Russian Backup pipeline; the current voice rollout is recorded in the
[Russian voice validation](docs/russian-voice-validation.md). An attended
button-triggered question during migration received
the correct audible answer. An attended Hey Jarvis test at approximately one
metre also produced the expected audible answer. After stream-address and
native-command fixes and HA recovery, the operator confirmed that a spoken
music request started playback on the second Dot without a device-selection
question. After the operator reported audible hiccups and buffering,
normalization was disabled only for the pilot's Music Assistant queue. A
bounded trace showed improved delivery, but another source stall followed;
the operator subsequently confirmed smooth music playback after the change.
Long-term reliability remains unmeasured. An explicit
player card was added to the existing Lovelace media view. A five-metre trial
woke correctly but STT misheard the question. See the dated
[deployment record](docs/deployment-record.md) for verified results and limits.

EchoMuse's supported path for this operating-system base is **emOS**. The
upstream FireOS in-place installation path supports Fire OS 5 and must not be
forced on this pilot.

## Start here

1. Read the [migration runbook](docs/migration.md) and identify the exact model,
   Fire OS generation, boot layout and recovery path.
2. Deploy the [controller](docs/controller.md) using either
   [Docker Compose](deployments/compose.yaml) or the
   [Kubernetes template](deployments/kubernetes.yaml). Keep real configuration
   and state private; do not apply the placeholder manifest unchanged.
3. Verify the upstream files against [upstream-lock.json](upstream-lock.json)
   with `python3 scripts/fetch_upstream.py` (see `--help`).
4. Complete per-device escrow, then prepare an image with
   [the offline builder](scripts/build_emos.py). The builder never flashes a
   device and cannot verify a partition map on your behalf.
5. Follow the migration runbook through verified USB installation, explicit
   device approval, HA enrollment and attended acceptance.

## Scope

- Pin and verify upstream controller, firmware and emOS artifacts.
- Preserve a device-specific recovery copy before changing boot software.
- Deploy a local controller with private persistent data.
- Connect the pilot through Home Assistant's ESPHome integration and retain
  the chosen Assist pipeline.
- Test wake detection, speech, playback and recovery before migrating another
  device.

All documentation and scripts are in English, except phrases a user must speak.
Wi-Fi credentials, tokens, device identities, boot backups, captured audio and
trained personal models stay outside the public repository.

See [shared CI and PR automation](docs/ci.md) for required checks, independent
bot approvals, opt-in merging, and Terraform-managed access.

See [Russian voice and energy reports](docs/russian-voice-roadmap.md) for the
implementation choices, measured Piper/KittenTTS comparison, general-conversation
model scope and the original audit. Software checks, runtime deployment and
physical listening tests are tracked separately.
Follow the [Russian voice operations runbook](docs/russian-voice-operations.md)
for service order, HA integration, per-Dot assignment, acceptance and rollback.

The [Russian Assist energy adapter](docs/energy-assist.md) implements the first
part of that plan: six read-only intents that return validated IGW reports to
the originating conversation. The Russian IGW endpoint and HA package are now
deployed; [service acceptance](docs/russian-voice-validation.md#local-energy-reports)
is recorded separately from microphone and listening tests.

The optional [local home tools](docs/home-control.md) connect an Ollama
conversation agent to current HA entity states, a reviewed device-control list
and Recorder statistics. The integration discovers relevant entities on demand
instead of sending the entire household catalog in every prompt. Its setup,
access boundaries, Russian command examples and rollback are documented separately.
Both EchoMuse units now select **Local Russian Home**; see the
[deployment checks and measured limits](docs/home-control.md#deployed-local-home-assistant--october-14-2026).

## Upstream and related work

- [EchoMuse](https://github.com/wilbowes/EchoMuse): device software, controller,
  emOS and the openWakeWord training workflow.
- [EchoLocal deployment](https://github.com/ha-homelab/ha-echo-dot): existing
  deployment and the source environment for this migration.
- [Organization infrastructure](https://github.com/4alvit/terraform-github-ha-homelab):
  Terraform ownership of this public repository.

Upstream software keeps its own licenses and attribution. No Amazon firmware,
upstream release binaries or personal wake-word models are redistributed here.
