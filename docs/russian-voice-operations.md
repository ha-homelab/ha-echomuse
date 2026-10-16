# Operate the Russian voice pipeline

This runbook connects the energy reports, general conversation and Russian
speech services. It applies to both EchoLocal and EchoMuse Assist satellites.
No USB connection or new Dot firmware is required for these server-side changes.

For a local model that can control household devices and read Recorder history,
follow the [local home-control setup](home-control.md). The FCC configuration
below remains the separate general-question baseline and rollback path. Keep
household conversations on the local pipeline; the external FCC model must not
receive home state or history through a fallback.

## Current household baseline

Both Dots were assigned **Local Russian Home** with the local household model
and **Piper Irina medium** (`piper-ru-irina`). Speech recognition still uses the
configured FCC cloud service, so this is not a fully offline voice pipeline.
Keep household state, tools and statistics on the local conversation route.
The female-voice cutover and generated-audio evidence are recorded in
[home control](home-control.md#female-voice-cutover--october-14-2026). The later
Wyoming 0.2.0 adapter supports [sentence streaming](voice-features.md).

For a new household setup, first deploy and validate these services, then use
the [operations handbook](operations.md#service-startup-and-enrollment-order)
and the local home-control installation steps. Do not select the external
conversation model below as an automatic fallback for household requests.

## Historical FCC baseline and rollback sequence

The following sequence records the original **Denis** pilot. It is useful for
understanding the deployment and restoring an intentionally selected former
configuration; it is not the current default to assign to both Dots.

1. Deploy the IGW version with the Russian energy formatter. Keep the existing
   MQTT sources and authentication. Check the authenticated
   `/v1/energy?locale=ru` response for `schema_version: 1`, `locale: ru`, current
   timestamps and the expected report keys. The default English endpoint must
   continue to work. See the [IGW change](https://github.com/victron-venus/inverter-gateway/pull/74).
2. Install the [read-only energy Assist package](energy-assist.md). Validate HA
   configuration and reload the documented integrations. Use a scoped IGW read
   token stored in HA secrets. Keep “Prefer handling commands locally” enabled.
3. Deploy the [FCC reliability changes](https://github.com/ha-homelab/ha-echo-show-5/pull/54)
   and check the running versions: bridge 0.1.4, cloud speech 0.1.2. Ensure old
   ConfigMap code mounts do not override the new image. Keep a rollback receipt
   containing the original image, configuration and selectors.
4. Deploy the [Russian speech service](https://github.com/4alvit/google-home-voice-stats/pull/36)
   with the pinned Piper Denis medium model. Follow that repository's renderer,
   TLS, bearer-token and container instructions. Verify real WAV synthesis, then
   verify the Wyoming listener on port 10601. Wyoming itself has no bearer/TLS
   authentication; keep it within the trusted service network. The adapter's
   HTTPS backend requires its private CA and token.
5. In HA, open **Settings → Devices & services → Add integration → Wyoming
   Protocol**. Enter the speech service hostname reachable from HA and port
   **10601**. The integration should expose a TTS entity and the
   **piper-ru-denis** voice.
6. In **Settings → Voice assistants**, copy the working Russian pipeline.
   Retain its Russian speech recognition and FCC conversation agent; select
   the new TTS entity, Russian and `piper-ru-denis`. Use a distinct name such as
   **FCC Russian Local Voice**, keeping the old pipeline for rollback.
7. Assign the new pipeline to one Dot first through its **Assistant** entity.
   If the device exposes two Assistant selectors, update and read back both.
   After an attended listening test, assign the same pipeline to the other Dot.

The general-conversation model is selected in the FCC bridge deployment, not in
the Wyoming integration or Dot firmware. Use the explicit free alias
`claude-3-freecc-no-thinking/open_router/nvidia/nemotron-3-ultra-550b-a55b:free`
with an empty fallback list. This external endpoint is for general questions
without personal or confidential data. Keep IGW model context disabled. Its
missing-measurement guard is not a general personal-data filter.

## Acceptance

Start with HA's Assist text interface. Check each of the six example phrases in
[the energy guide](energy-assist.md) and compare the response with the current
IGW report. Warnings about unavailable or stale sources must remain audible;
missing values must not become zero. Historical household measurements are not
provided by this snapshot integration.

Generate and fetch an actual TTS audio response; a registered entity or returned
URL alone is insufficient. Run two requests with different originating device
contexts and ensure both return. The energy helper allows four active requests;
the Piper service allows one active synthesis and one waiting request within its
bounded deadline. The external conversation bridge still allows one active
model request and can return busy when both Dots ask general questions at once.

For an attended physical check, press the Dot's action button and say
«Сколько будет семь плюс пять?», then «Сколько заряда в аккумуляторе?».
Listen for a complete Russian answer from the same Dot. Repeat on the other
unit. Button tests isolate the voice pipeline from wake-word detection; wake
accuracy needs its own labelled acoustic test. Do not enable background
recording to troubleshoot these server-side services.

Check that existing music controls still target the originating player. These
energy intents do not invoke Cast or select a fixed media player.

## Rollback and boundaries

Restore both Assistant selectors to their saved pipeline to revert TTS. Model
selection is separate: restore the saved FCC model configuration to revert
conversation. Use saved immutable image digests and the matching configuration
to revert services; do not restore an old broad cluster overlay. To remove only
the energy feature, follow the package rollback in the energy guide.

Piper handles speech, not recognition or reasoning. The larger model does not
improve the microphone or wake detector. A short CPU synthesis benchmark also
does not establish end-to-end response time, music quality or long-term uptime.
The [evaluation record](russian-voice-roadmap.md) distinguishes these measurements.
