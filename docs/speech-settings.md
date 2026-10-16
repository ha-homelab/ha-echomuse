# Local Russian voice settings

The `russian_speech_settings` custom integration controls the shared local
Russian speech service. It complements the existing **Wyoming Protocol** TTS
integration; it does not replace speech recognition, the conversation agent,
wake-word detection, or the EchoMuse firmware.

## Where to change the voice

Open **Settings → Devices & services → Russian Speech Settings → Local Russian
Speech**. The device has ten configuration entities. The entity labels are
translated into English, Russian, German, Spanish and French using the HA
profile language. Voice names remain unchanged.

The existing **Media** dashboard can show the same controls using the
[entities card example](../examples/lovelace/russian-speech-settings.yaml).
Check entity IDs in your own registry before copying it.

In **Settings → Voice assistants**, edit each relevant assistant. Keep its
existing conversation agent and speech recognition. Under text-to-speech,
choose **Local Russian Speech**, Russian, and **silero-ru-default**. This alias
follows the voice selected on the settings device. A pipeline selecting a
specific voice, such as `silero-ru-baya`, keeps that speaker while still using
the shared prosody settings. Reload Wyoming after upgrading the service so HA
learns the new voice list.

Changes take effect on the next utterance. An utterance already in progress
keeps its settings, including across streamed sentences. Settings are global
to the service: Dots, displays and other clients sharing it are affected.
There is no need to restart or reflash speakers. The integration clears HA's
TTS cache after a change so repeated text is synthesized with the new settings.
This clears cached TTS audio for all TTS providers; it does not play audio.
External API changes are detected on the next 30-second refresh. Direct HTTPS
clients should invalidate their own audio caches.

## Available controls and limits

- **Voice:** Baya, Kseniya, Xenia, Aidar or Eugene. Default: Baya.
- **Speech rate:** 80–130%, in steps of 1. Default: 100%. Higher means faster.
- **Pitch adjustment:** −10–+10%, in steps of 1. Default: 0%. This changes pitch,
  not speaker identity. Large changes can sound unnatural.
- **Added sentence pause:** 0–1000 ms, in steps of 50. Default: 0. Adds a break
  after sentence boundaries and at the end of each synthesized segment;
  the model's natural pauses still exist. Streamed responses use the same gaps.
- **Intonation:** automatic, statement, question or exclamation. Default:
  automatic, which follows the text and punctuation. Forcing one type applies
  it to every sentence; it is primarily useful for announcements or testing.
- **Words to emphasize:** up to ten comma-separated whole words, at most 160
  characters in total. Letters and internal hyphens are allowed. Matching is
  case-insensitive but does not infer grammatical forms. For example,
  `батарея, готова` does not match `батареи`. Default: empty, with no forced
  emphasis. Numbers are expanded before matching, so use written words.
- **Emphasis strength:** integer 1–3. Default: 3. Only affects matched emphasis
  words. This is a deliberately bounded application range, not a claim about
  every value the upstream neural model might accept.
- **Automatic stress:** enabled by default, including homograph handling.
- **Automatic ё:** enabled by default, including homograph handling. Disabling
  either pronunciation aid can reduce intelligibility.
- **Reset voice settings:** restores all nine values above, including Baya,
  the normal rate/pitch, no added pause and an empty emphasis list.

There is no generic “happy” or “sad” setting. Exclamations, word emphasis and
prosody can change delivery, but they do not guarantee an emotional style.
The upstream SSML API also accepts named speed/pitch presets; this service
exposes bounded numeric controls instead. It builds its own SSML internally
and continues rejecting raw user-supplied SSML and arbitrary model options.
A literal `*` from generated Markdown is stripped instead of becoming hidden
emphasis markup. Explicit Russian stress, for example `молок+о`, remains a
text pronunciation aid. Loudspeaker volume and EQ remain EchoMuse settings.

A reasonable audition starts with Baya at 100% rate and 0% pitch, then compares
110% rate with everything else unchanged. Do not enable forced exclamations
for all home responses without listening first. Only play test audio on a
speaker authorized for that test.

## Voice catalog

The deployed Silero `v5_6_ru` package includes these selectable speaker IDs:

- **Baya** — `silero-ru-baya`; the default used by this deployment.
- **Kseniya** — `silero-ru-kseniya`.
- **Xenia** — `silero-ru-xenia`; distinct from Kseniya.
- **Aidar** — `silero-ru-aidar`.
- **Eugene** — `silero-ru-eugene`.

They share one pinned model file; selecting a speaker does not download or
load another model. The `silero-ru-default` Wyoming entry is an alias, not a
sixth speaker. Voice selection changes acoustics, not the grammatical gender
chosen by the conversation agent. If an agent says `готова`, a different
speaker still reads that word unless its prompt/text is changed.

The speech repository also implements **Piper Denis medium**
(`piper-ru-denis`), **Piper Irina medium** (`piper-ru-irina`) and the optional
**KittenTTS 2 Russian** pilot (`kitten2-russian`). These need their corresponding
backend image and verified assets. They are not additional installed voices
in the running Silero service, and are deliberately absent from this selector.
The English Kitten/Nano service is separate. Arbitrary voice cloning, uploaded
voice files, and multilingual model downloads are not supported here.

See the [speech service repository](https://github.com/4alvit/google-home-voice-stats),
[Silero model catalog](https://github.com/snakers4/silero-models), and
[upstream SSML reference](https://github.com/snakers4/silero-models/wiki/SSML).
The pinned Silero weights use CC BY-NC-SA 4.0; their license is independent
of this integration's code license.

## Installation

1. Upgrade the Russian speech service with the settings-capable Silero image.
   Mount a persistent, writable directory at `/state` and set
   `RUSSIAN_SPEECH_SETTINGS_FILE=/state/settings.json`. The service UID/GID is
   10001. The deployment renderer creates a 64 MiB PVC. Do not use a transient
   `emptyDir` for production settings. Keep the existing private TLS and token.
2. Copy `custom_components/russian_speech_settings` from this repository into
   HA's `/config/custom_components`. Restart HA once to discover the new
   integration. Future voice-setting changes do not require restarting HA.
3. Copy the service's **CA certificate** into a private HA configuration path,
   for example `/config/certs/russian-speech-ca.crt`. Do not copy the server's
   private TLS key. Obtain the existing service token from your deployment's
   secret store; it is the token mounted as `/run/speech/token` in the service.
   It is not an HA login token or a Dot SSH password.
4. Add **Russian Speech Settings** in Devices & services. Enter the private
   HTTPS origin including port, for example `https://speech.local:8093`, the
   service token and the CA path as seen inside the HA container. The hostname
   must match the server certificate. Certificate verification cannot be disabled.
5. Reload the existing Wyoming integration and select `silero-ru-default` in
   the Assist pipelines that should follow the global voice selector.

The integration stores its credential in HA's config entry storage, never in
an entity state or dashboard. Keep HA backups private. The settings JSON has
only voice preferences, but custom emphasis words may still reveal household
names; keep that file out of public repositories too. The integration is a
manual custom integration, not an automatically installed HACS package.

## Service API

The existing bearer-authenticated, CA-verified HTTPS listener provides:

- `GET /v1/settings`: current values, defaults, schema, model and whether a
  persistent settings path is configured.
- `PATCH /v1/settings`: update only the supplied keys; validate everything
  before saving. Updates are serialized and persisted by atomic replacement.
- `POST /v1/speech`: accepts `text` and an optional `options` object with the
  same keys. Overrides affect one request and do not change saved defaults.

For example, the PATCH body `{"rate":110,"pitch":0}` changes just those two
values. A synthesis body can be
`{"text":"Готова помочь.","options":{"voice":"silero-ru-xenia"}}`.
Unknown keys, out-of-range values, wrong types and malformed emphasis lists
return HTTP 400. An unauthorized request returns 401; a failed settings save
returns 503 and does not change the in-memory settings. The settings endpoint
returns 404 on non-Silero backends. The API is a private service, not an Internet
management endpoint. Existing authenticated TTS clients have the same token
and therefore can also manage these settings.

## Verification and rollback

`tests/runtime_speech_settings.py` runs the actual HA config flow and entity
platforms in an isolated configuration. It checks changes, reset, failure
handling, refresh, cache invalidation and unloading. The speech repository
checks TLS authorization, input limits, atomic persistence and immutable
per-utterance settings. Test all five voices and prosody boundaries with the
real pinned model before promoting a new image. Generated files can be checked
without playing them on household speakers.

If settings are undesirable, use **Reset voice settings**. If rolling back to
an older Baya image, first restore explicit `silero-ru-baya` in each pipeline:
older images do not recognize `silero-ru-default`. Then restore the saved image
and reload Wyoming. Disable the settings integration while running a service
without `/v1/settings`. Preserve its PVC for a later upgrade. Piper rollback
also requires the matching Piper backend and pipeline voice, as described in
the speech service runbook.

## Settings rollout — October 16, 2026

The pinned model generated valid audio for all five installed voices. On the
NUC, the final image passed two concurrent Wyoming requests in 3.50 and 5.80
seconds (6.90 seconds of output each). Its streaming probe delivered first audio
in 2.32 seconds, before input ended. The inference container retained its two-CPU,
1 GiB limit; the adapter retained its 250m CPU and 128 MiB limits.

The probe exercised speech-rate and pitch boundaries, all three emphasis levels,
forced sentence types, pauses, and disabled pronunciation aids. Settings were
saved on a persistent volume. These are generated-audio and protocol checks,
not a listening preference test or an end-to-end microphone latency measurement.

The settings integration was also installed in the active HA instance. A rate
change from 100 to 101 and back to 100 was made through the actual HA number
service and verified against the HTTPS API. Both shared TTS pipelines selected
`silero-ru-default`; both Dot satellites reported idle. HA generated a 48,164-byte
audio response, which was not played. The Media dashboard configuration was
saved and read back with all ten control references present.
