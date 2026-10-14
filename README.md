# ha-echomuse

Reproducible EchoMuse deployment and Home Assistant integration for existing
Amazon Echo Dot 2 devices. This is an independent deployment and migration
project, not a fork or official distribution of
[EchoMuse](https://github.com/wilbowes/EchoMuse).

## Current status

The pilot is the second previously converted Echo Dot 2. It now boots **emOS
v0.10** and runs **EchoMuse v2.18.0**, built around its own ARM32 kernel from
Fire OS 6 / Android 7.1.2. Its verified USB recovery backups remain private.
The first EchoLocal unit was not changed.

Controller **2.26.0** is deployed separately, and the pilot has reached it over
WSS using device-specific credentials; TLS is now required. Home Assistant
ESPHome enrollment is complete and both Assistant selectors use the existing
FCC Russian Backup pipeline. An attended button-triggered question received
the correct audible answer. Music routing is configured through the existing
Music Assistant provider. Further wake-word and audible music checks are in
progress; a five-metre trial woke correctly but STT misheard the question. See the dated
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

## Upstream and related work

- [EchoMuse](https://github.com/wilbowes/EchoMuse): device software, controller,
  emOS and the openWakeWord training workflow.
- [EchoLocal deployment](https://github.com/ha-homelab/ha-echo-dot): existing
  deployment and the source environment for this migration.
- [Organization infrastructure](https://github.com/4alvit/terraform-github-ha-homelab):
  Terraform ownership of this public repository.

Upstream software keeps its own licenses and attribution. No Amazon firmware,
upstream release binaries or personal wake-word models are redistributed here.
