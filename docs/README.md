# Documentation map

[English overview](../README.md) · [Русский](../README.ru.md) · [Deutsch](../README.de.md) · [Español](../README.es.md) · [Français](../README.fr.md)

Start with the task you need to complete. Detailed runbooks are maintained in
English. The localized project READMEs cover the same scope, prerequisites,
installation sequence, boundaries and support links.

Start with the **[illustrated process and result guide](visual-guide.md)** for
the conversion journey, request flow, measured response timeline and observable
acceptance targets. Its color diagrams link back to the detailed runbooks below.

## Choose and migrate hardware

- [Compatibility and decision points](compatibility.md): supported evidence,
  model identification and stop conditions.
- [Migration](migration.md): preparation, per-device escrow, installation,
  recovery and a second-unit migration.
- [Controller deployment](controller.md): Compose or Kubernetes, private state,
  TLS and device enrollment.
- [Device access](device-access.md): administrator credentials, Console,
  normal operation versus USB recovery.

## Configure Home Assistant

- [Operations](operations.md): ordered setup, acceptance and maintenance.
- [Architecture and measured latency](architecture.md): voice, music, BLE and
  data boundaries, with accessible SVG diagrams.
- [Home control and statistics](home-control.md): local tools, permissions,
  aliases, Ollama and Recorder.
- [Languages and i18n](i18n.md): what is localized, language selection, fallback
  and the limits of speech support.
- [Family conversation](family-interaction.md): sourced poems, local riddles,
  optional original stories, music-library playback and privacy boundaries.
- [Local creative server](local-family-server.md): fixed-model Apple Silicon
  inference, loopback transport, authentication and resource limits.
- [Energy reports](energy-assist.md): bounded read-only reports.
- [Dashboard](dashboard.md): current voice and music entities in Lovelace.
- [Voice settings and catalog](speech-settings.md): live Silero controls and all installed speakers.
- [Voice features](voice-features.md): streaming speech, interruption, cues,
  announcements and timers.
- [Bluetooth proxy](bluetooth-proxy.md): separate enrollment, connection slots,
  persistent authentication, HA reauth recovery, obsolete records and the role
  of iBeacon Tracker.

## Diagnose and verify

- [Troubleshooting](troubleshooting.md): symptom-to-layer diagnosis.
- [Music troubleshooting](music-troubleshooting.md): missing files, queues,
  buffering and native stop routing.
- [Russian voice operations](russian-voice-operations.md): service order and rollback.
- [Russian voice validation](russian-voice-validation.md): what was tested and what was not.
- [Deployment record](deployment-record.md): dated migration evidence.
- [Russian voice roadmap](russian-voice-roadmap.md): historical experiments and decisions.

## Maintain this project

- [CI and review](ci.md), [contribution guide](../CONTRIBUTING.md) and
  [security reporting](../SECURITY.md).
- [Wiki publishing](wiki.md): render a reproducible snapshot from these sources.
- [Diagram sources and measurements](assets/README.md).
- [Language inventory](languages.json): machine-readable README coverage.

A recorded test result is evidence for that version and scenario. It is not a
live status report or a guarantee for a different device, language or provider.
