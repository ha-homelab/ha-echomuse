# ha-echomuse

[English](README.md) · [Русский](README.ru.md) · [Deutsch](README.de.md) · [Español](README.es.md) · [Français](README.fr.md)

Turn an existing **Echo Dot 2** into a Home Assistant voice satellite with
EchoMuse and emOS. This independent project provides reproducible deployment,
recovery procedures, local home tools, and operational documentation. It is not
an official EchoMuse distribution or a replacement firmware for every Echo.

[Documentation](docs/README.md) · [Operations](docs/operations.md) · [Compatibility](docs/compatibility.md) · [Troubleshooting](docs/troubleshooting.md) · [Wiki](https://github.com/ha-homelab/ha-echomuse/wiki)

![Six stages from identifying the Echo Dot to an attended Home Assistant voice test](docs/assets/conversion-journey.svg)

**[Visual walkthrough: process and result](docs/visual-guide.md)** — conversion stages, voice request flow, measured timing, Bluetooth roles and acceptance checks. [Service architecture](docs/architecture.md) explains the connections.

## What you get

- Reproducible, pinned controller and emOS preparation; **the builder does not flash devices**.
- Home Assistant Assist through ESPHome, native music routing, announcements,
  timers, early speech and wake-word interruption where supported.
- A local Ollama tool API for current states, explicitly allowed device controls,
  and Recorder statistics; bounded, read-only energy reports.
- A separate encrypted Bluetooth proxy endpoint for BLE devices.
- English, Russian, German, Spanish and French README guides and bounded
  assistant-language selection. English and Russian native state-query examples
  are included; see [language coverage](docs/i18n.md).

## Before you start

The documented conversion target is **Echo Dot 2 / RS03QR (biscuit)**. Verify the
exact model, installed OS, partition map and device-specific recovery copy before
changing boot software. Other Echo generations and full-size Echo models are not
validated by this runbook. Use a reliable power supply and a data-capable USB
cable with a supported recovery host; Wi-Fi alone is not a recovery path.

You also need Home Assistant, an Assist speech pipeline and an EchoMuse
Controller. Music Assistant, Plex, Ollama and the energy service are optional
components for their respective features. **Do not apply placeholder deployment
manifests unchanged.**

## Installation order

1. Check [compatibility](docs/compatibility.md), then read the entire
   [migration runbook](docs/migration.md), including rollback.
2. Deploy the [controller](docs/controller.md) with private persistent state,
   TLS and separate credentials per device.
3. Verify the pinned [upstream artifacts](upstream-lock.json), preserve each
   device's recovery backup, and prepare its image with
   [build_emos.py](scripts/build_emos.py). Never reuse another device's backup.
4. Follow the USB installation procedure, approve the device in the controller,
   and enroll its voice endpoint in Home Assistant's **ESPHome** integration.
5. Assign the Assist pipeline, STT and TTS language/voice. Add optional
   [home tools](docs/home-control.md) and [energy reports](docs/energy-assist.md).
6. Add the current entities to [Lovelace](docs/dashboard.md). Enroll the
   [BLE proxy](docs/bluetooth-proxy.md) separately if needed.
7. Complete the [acceptance checklist](docs/operations.md) on each device before
   repeating the migration. A connected controller does not prove audible speech.

## Everyday use

Use the controller's authenticated web interface and root Console for device
administration; see [access and credentials](docs/device-access.md). This project
does not provision a universal SSH/Telnet login. Recovery access is documented
separately from normal operation.

The tested wake phrase is **Hey Jarvis**. The documented firmware exposes one
active wake model; a translated README does not install a translated wake word.
[Voice features](docs/voice-features.md) explains interruption and streaming.
[Music troubleshooting](docs/music-troubleshooting.md) covers missing sources,
buffering and the difference between stopping and pausing the originating player.
**iBeacon Tracker** consumes BLE advertisements; it is not another proxy.

## Verification and limits

The recorded deployment used emOS **0.10**, EchoMuse **2.18.0**, Controller
**2.26.0** and Home Assistant **2026.10.0**. These are a dated tested baseline,
not a claim to be the latest releases or a live device-status display. Both Dot
migrations and nearby Russian voice checks were recorded; distant speech and
long-term reliability have limits. See [deployment evidence](docs/deployment-record.md),
[voice validation](docs/russian-voice-validation.md) and the
[measured latency chart](docs/architecture.md).

The current recorded Russian voice is **Piper Irina**. Local home tools use
Ollama, but the recorded STT provider is FCC cloud speech: **the full recorded
pipeline is not offline**. A different language needs compatible STT, model and
TTS selections and its own listening test. Never send household data to the
optional general-question cloud route; see [privacy boundaries](docs/home-control.md).

## Contributing and documentation

Read [CONTRIBUTING.md](CONTRIBUTING.md) for checks and translations,
[SECURITY.md](SECURITY.md) for private reporting, and [shared CI](docs/ci.md) for
review requirements. The [wiki source and publishing guide](docs/wiki.md)
keeps the public wiki reproducible from reviewed documentation. Private recordings,
models, device identities, keys, tokens and backups do not belong in commits.

## Upstream and related projects

- [EchoMuse](https://github.com/wilbowes/EchoMuse): upstream device software, controller and emOS workflow.
- [ha-echo-dot](https://github.com/ha-homelab/ha-echo-dot): EchoLocal conversion and wake-word training.
- [ha-echo-show-5](https://github.com/ha-homelab/ha-echo-show-5): the separate Echo Show path.
- [Repository infrastructure](https://github.com/4alvit/terraform-github-ha-homelab): Terraform-managed settings.

See [LICENSE](LICENSE). Upstream components retain their own licenses; no Amazon
firmware, release binaries or personal voice models are redistributed here.
