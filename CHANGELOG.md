# Changelog

## Unreleased

- Add native Russian family activities with four sourced public-domain poems,
  nine original short pieces and six riddles with isolated sessions. Document optional
  creative generation through a finite public-topic gate, measured local-model
  limits, exact-title music-library playback and the existing speech controls.

- Add a pinned Controller 2.26.0 fix that retains BLE Noise authentication when
  active GATT is disabled or unavailable, serializes proxy lifecycle changes,
  and makes administrator key retrieval read-only. Document same-entry HA
  reauthentication, persistent-storage limits and regression checks.
- Add the Russian Speech Settings integration (0.1.0): five local Silero voices,
  bounded prosody and pronunciation controls, persistent service settings, cache
  invalidation and English/Russian/German/Spanish/French UI translations.
- Add a local Russian openWakeWord training, validation, calibration and deployment workflow; record the two-Dot switch to «Привет, Мышка» and its measured limits.
- Add attended button-controlled recording with serialized save/close handling, verified feature-cache provenance, and a pinned Controller overlay that treats incomplete wake-model inventories as unknown rather than missing.
- Document the failed literary-name and quotation investigation, rejected prompt candidates, native-intent checks, and requirements for a grounded literary feature.

- Add an opt-in verified strict TLS profile for pinned artifact downloads, with synthetic full-chain and handler-wiring tests.
- Add a real CLI regression proving public-source scans never print matched
  credential or private-address contents; document the CodeQL false positive.
- Use module-qualified unittest mocking imports to resolve quality diagnostics.
- Provide a concrete private vulnerability-reporting fallback and response policy.

## EchoMuse Home Tools 0.4.0b3

- Initialize Home Assistant's base LLM API defaults so recognized speech can
  reach the conversation handler on Home Assistant 2026.11. Preserve older
  supported HA versions, local-provider restrictions and per-user entity permissions.
- Exercise the registered API acquisition path in runtime tests, including a
  removed user's denied access. This beta is the full integration source, not
  an export of a customized installation or a device-firmware release.

## Historical integration source: 0.3.0

The earlier integration manifest identified EchoMuse Home Tools source as 0.3.0.
This repository also contains version-pinned upstream download and offline emOS
build helpers, deployment examples and operational documentation. A complete Git
commit identifies each source snapshot across these files. These notes do not
announce a new upstream EchoMuse/emOS release or claim a new device validation.
