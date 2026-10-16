# Russian voice and energy reports

Research and implementation date: **2026-10-14**.
For installation order and Home Assistant settings, see the
[operations runbook](russian-voice-operations.md).

## Implementation decisions

The [Russian energy Assist adapter](energy-assist.md) implements six deterministic
intents, validates gateway responses and returns speech to the originating
conversation. Tests exercise the actual HA intent/script engine, simultaneous
requests and failure handling. IGW formats the Russian reports; neither the
conversation model nor the speech model calculates their values.

The initial Russian speech backend was **Piper Denis medium**, served through
Wyoming. The later [female-voice cutover](home-control.md#female-voice-cutover--october-14-2026)
selected **Piper Irina medium**; the measurements in this original evaluation
remain measurements of their stated test models and hosts. The larger **KittenTTS 2** remains experimental: in a synthetic CPU
benchmark it needed 14.24 seconds to generate 2.08 seconds of short speech,
34.57 seconds for an energy report and 7.21 GiB peak process memory. Piper's
two-thread Apple Silicon benchmark generated a short warm reply in 0.055
seconds and an energy report in 0.32–0.33 seconds. These are generation
measurements on the test host, not end-to-end Dot response times or a listening
comparison. Full methods, model hashes, licenses and serving configuration are
maintained in the [speech service change](https://github.com/4alvit/google-home-voice-stats/pull/36).

The selected general-conversation candidate is the explicit free
`claude-3-freecc-no-thinking/open_router/nvidia/nemotron-3-ultra-550b-a55b:free`
route. Synthetic Russian arithmetic and science explanations passed; this does
not establish reliability for every question. The endpoint excludes personal
and confidential data and describes request logging. It is intended here for
general questions only. **IGW context stays disabled in the model bridge**;
energy questions use local intents. The missing-measurement guard is not a
general personal-data detector. Do not dictate private information to this
external route. See the [model evaluation](https://github.com/ha-homelab/ha-echo-show-5/pull/54)
and [provider conditions](https://openrouter.ai/nvidia/nemotron-3-ultra-550b-a55b:free).

The speech adapter separates bounded ASR and TTS concurrency, and the text bridge
records timing and outcome without logging transcript content. The text model
still has a single active request slot and returns an explicit busy result for
contention; this work does not promise two simultaneous LLM answers. The local
energy helper supports four concurrent requests.

Deployment and acoustic acceptance are separate gates. The sections below
preserve the **pre-implementation audit and proposed sequence**; they do not
describe the current live configuration.

## Original audit: recommended direction

Reuse Inverter Gateway (IGW) as the source of energy facts. Add a deterministic
Russian report formatter, then a dedicated Russian text-to-speech service shared
by Home Assistant and the Google display adapter. Evaluate **KittenTTS 2** first
because it is the multilingual successor to the Nano voice already used by the
display project. Keep a Russian Piper voice as a lightweight comparison and
possible local fallback. Evaluate a larger conversational model separately.

The Dot remains a microphone, wake detector and speaker. Inference belongs on
a server; this work does not require another firmware flash or USB connection.
The existing EchoLocal and EchoMuse satellites can use the same HA voice services
even though their device software and wake-word models differ.

## What the system did at the original audit

The Google display implementation is
[google-home-voice-stats](https://github.com/4alvit/google-home-voice-stats).
Its path is MQTT → IGW → validated report → speech and video → Google Cast.
It does not use a conversational LLM to calculate or narrate the statistics.
Its preloaded KittenTTS Nano 0.8/Jasper backend is English-only. IGW currently
also generates English report text. The existing optional Piper adapter validates
English voices, so inserting a Russian model into that adapter is insufficient.

The inspected EchoMuse pipeline uses:

- NVIDIA Parakeet 1.1B multilingual ASR with Russian selected;
- native HA commands, then FCC for unmatched conversation;
- Liquid LFM2.5-2.6B through the existing explicit free text route;
- NVIDIA Chatterbox Multilingual with the Russian male voice.

The FCC bridge receives an isolated transcript. It has no HA state catalogue,
energy measurements, tools, clock context or conversation history. A larger
model alone cannot answer questions about current household energy accurately.
Russian recognition, Russian reasoning and Russian speech synthesis are three
different capabilities; changing one model does not change the other two.

The server-side services were ready during the read-only inspection, but the
pilot Dot was disconnected. This inspection therefore establishes configuration,
not present acoustic quality or successful playback.

## Reuse energy facts without redirecting speech to the display

IGW's authenticated, read-only `GET /v1/energy` already supplies battery charge,
solar power, today's generation, status and alarms. Power-flow reports are
available when their sources are configured. The envelope includes units,
freshness, receipt age and MQTT connectivity.

Add Russian wording where IGW already owns report semantics. Retain English as
the default, preserve existing fields, and introduce an explicit locale without
breaking old clients. Preserve source warnings and distinguish stale,
unavailable and unconfigured values. Never turn an unknown value into zero.
Render numbers, plural forms and units deterministically before TTS.

Add Russian HA custom sentences, for example:

- «Какая сейчас энергетическая сводка?»
- «Сколько заряда в аккумуляторе?»
- «Сколько солнце выработало сегодня?»
- «Что с сетью?»
- «Есть ли аварии?»

The intent must fetch and validate the report, then return a conversation speech
response to the originating Assist session. Do not call the existing
`script.igw_google_*` wrappers: their output is intentionally bound to a fixed
Cast display. The Dot path does not need video rendering or Cast discovery.
See HA's [custom sentence and intent support](https://www.home-assistant.io/voice_control/custom_sentences_yaml/).

The present energy snapshot does **not** supply yesterday's history, a weekly
comparison, electricity cost or a defensible remaining-runtime prediction.
Those need separate measured inputs and calculations before becoming answers.
The existing energy RAG service indexes technical documentation; it must not be
treated as a source of live measurements. A future explanatory path can combine
an explicit snapshot with read-only document search, keeping both sources
identified. Document ingestion is unnecessary for the voice assistant's tool set.
Benchmark Russian and bilingual retrieval before enabling that path: the source
default embedding is `all-MiniLM-L6-v2`, and a larger answer model does not by
itself improve retrieval. Verify the live embedding configuration separately.

## Russian speech candidates

**KittenTTS 2, 1.7B — first quality candidate.** The publisher documents a built-in
`Russian` voice and requires `normalize=False` for non-English text. Its English
normalizer can corrupt Russian numbers and abbreviations. Use the stable preset
and fully prepared Russian text. Multilingual voices have a smaller reference
base than English; local listening tests remain necessary.
[Language and voice documentation](https://github.com/KittenML/KittenTTS/blob/main/docs/voices-and-expression.md).

The Python runtime advertises about 6 GB RAM for CPU use; a small downloaded
checkpoint is not the process's memory requirement. The official C++ backend is
a CPU-oriented batch runtime with a custom GGUF format and LibTorch waveform
decoder. It is not a drop-in model for the existing ONNX Nano service or stock
Ollama, and its CLI does not implement Python's streaming API. A resident adapter
and measured first-audio latency are required before selecting a serving design.
[Python runtime](https://github.com/KittenML/KittenTTS/blob/main/README.md),
[C++ runtime](https://github.com/KittenML/kitten-tts-2-cpp).

**Piper Russian — baseline and possible local fallback.** Evaluate published
Russian voices such as `irina`, `dmitri`, `denis` and `ruslan` on identical text.
Piper already fits the HA/Wyoming ecosystem. A smaller model may be the better
choice for immediate confirmations even if a larger one wins on long narration.
No Russian voice has been selected by listening during this investigation.
[Russian voice inventory](https://huggingface.co/rhasspy/piper-voices/tree/main/ru/ru_RU),
[maintained engine](https://github.com/OHF-Voice/piper1-gpl).

**Qwen3-TTS 1.7B CustomVoice — alternative quality candidate.** Its official model
card includes Russian. Treat published streaming figures as upstream results,
not a latency guarantee for this deployment. Benchmark its actual supported
runtime and memory use before choosing it over Kitten or Piper.
[Model card](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice).

Keep model weights and downloaded runtimes outside this public repository.
Record exact revisions, hashes and each model's own license when implementing;
a library's license does not establish the license of its model weights.

## Placement and HA integration

The inspected always-on VM has enough memory headroom for a KittenTTS 2 pilot.
The smaller controller/HA hosts do not have comfortable headroom for another
roughly 6 GB process. Existing measurements also show that native execution
versus a VM can materially affect speech latency. Benchmark both a suitable
native host and the VM under realistic load before deployment. Do not put more
speech inference on the NAS merely because it already runs the Cast adapter.

The available Apple Silicon workstation can host experiments, but its sleep,
availability and resource sharing must be resolved before making it a required
household service. Existing local coding-model throughput is not a TTS benchmark.

Create a dedicated Russian TTS service, preload its model, and expose it to HA
through a [Wyoming integration](https://www.home-assistant.io/integrations/wyoming/)
or a purpose-built HA TTS adapter. The display service's HTTPS `/v1/speech`
interface is not itself a Wyoming endpoint. An adapter can share its backend
while preserving authenticated transport across hosts. Do not assume that a
bare Wyoming listener provides the existing HTTPS authentication or encryption.

In HA: Settings → Devices & services → Add integration → Wyoming Protocol;
then Settings → Voice assistants → create a pilot pipeline with Russian TTS.
Keep the current STT and conversation engine for the first comparison. Assign
the pilot to the second Dot's Assistant selector(s) and verify the readback.
Only after attended acceptance assign it to the first Dot. Retain the old
pipeline for rollback. This is a proposed sequence, not an action already taken.

## Reliability improvements, in priority order

1. **Separate service availability from acoustic failure.** Show device online,
   HA connection, wake detection, STT outcome, conversation outcome and playback
   outcome separately. Include a correlation ID and elapsed time per stage,
   without recording speech or storing transcripts by default.
2. **Remove unrelated contention.** The current cloud-speech adapter has one
   shared slot across recording, ASR and TTS. The text bridge also allows one
   inference at a time. Separate bounded pools and per-session cancellation;
   test two concurrent satellites. Expired requests must not build up in a queue.
3. **Reduce first-audio delay.** Current TTS assembles all sequential segments
   before returning any audio. `streamReply` alone cannot fix this upstream
   wait. Benchmark short complete responses first, then implement bounded
   sentence streaming only if the complete transport supports it.
4. **Keep ordinary controls deterministic.** Preserve local music/volume/device
   routing and its origin checks. A conversational model must not claim an
   action succeeded without the existing action handler's actual result.
5. **Treat wake reliability separately.** Larger TTS or LLM models cannot cure
   false wake-ups. Use an attended, labelled test with quiet, TV, music and
   normal speech; measure false activations and missed wakes before changing
   thresholds. Never silently enable microphone capture.
6. **Use explicit failure and fallback rules.** Speech-only fallback can retry
   the same prepared text before playback starts. Do not replay home-control
   actions, silently introduce a paid/cloud route, or splice two voices halfway
   through an answer. Retain the current known pipeline as a manual rollback.

## Larger conversational model: separate experiment

A larger model is useful for explanations and follow-up questions after it has
access to validated facts. It is unnecessary for reading battery charge or
today's generation. Test Russian answers, factual consistency and latency on the
same synthetic cases before replacing the small current model.

Use explicit provider/model IDs. FCC registry entries, public catalogue entries
and successful inference are different evidence levels. A zero-priced route may
still be unavailable or rate-limited; do not infer unlimited capacity. Existing
local Qwen3-Coder deployment work is a possible transport starting point, but a
coding-tuned model and its short warm benchmark are not evidence of good
Russian household conversation.

The first larger text candidate is
`anthropic/open_router/google/gemma-4-26b-a4b-it:free`, with the 31B variant as a
second comparison. On the research date, OpenRouter listed both routes with
zero prompt/completion prices; this was a metadata check, not successful
inference. Earlier deployment notes already recorded rate limits/timeouts on
Gemma routes. The publisher describes broad multilingual coverage; test Russian
answers directly rather than infer quality from model size.
[Gemma model card](https://ai.google.dev/gemma/docs/core/model_card_4),
[26B route metadata](https://openrouter.ai/api/v1/models/google/gemma-4-26b-a4b-it:free/endpoints).

The inspected FCC registry also named a Qwen route that was absent from the
current provider catalogue. This is why registry-only recommendations are
insufficient. A local conversational model remains an alternative if avoiding
external quota is the priority, but requires a supported backend adapter and
an always-on host; the existing bridge restricts selection to explicit free
OpenRouter routes.

Add bounded session context only after defining expiry, source timestamps and
per-satellite isolation. Queries about live state must refresh facts rather than
reuse yesterday's answer. Never expose unrestricted HA or shell tools merely to
make the model more capable.

## Acceptance and implementation sequence

1. Add and test Russian IGW report wording against synthetic fixtures: normal,
   stale, missing, MQTT disconnected, import/export, negative power and alarms.
2. Add the HA energy intents; test returned text and originating-session routing
   before introducing a new voice model.
3. Benchmark KittenTTS 2 and Piper on the same short confirmations and energy
   reports. Include Russian fractions, percentages and kilowatt-hours. Measure
   cold start, warm first audio, full generation, peak RSS and cancellation.
4. Serve the selected backend independently; exercise unavailable backend,
   malformed output, timeouts and two simultaneous requests. Retain bounds on
   text, audio duration, memory and deadlines.
5. Assign the pilot pipeline to one Dot and listen to short and long answers,
   then test two Dots together. Adopt only after a clear improvement; preserve
   the original selectors and pipeline for rollback.
6. Evaluate the larger LLM with read-only facts and short Russian replies, then
   separately address historical energy questions and document retrieval.

Suggested acceptance targets, **not measured results**: immediate controls
should not regress; warm short-answer first audio within three seconds of ready
text; no incorrect numbers, units or freshness claims in the test set; no silent
loss of either simultaneous request; and no unexpected action retries. Record
failures and distributions, not just the fastest sample. Long reports must fit
the chosen audio deadline or be explicitly shortened/split; do not simply raise
the current limits to mask slow generation.

## Source locations for the implementation

- IGW: `src/energy.rs`, `docs/energy-api.md`.
- Google adapter: `igw_google_voice/cast_gateway.py`, `kitten_service.py`,
  `piper_worker.py`, `docs/kitten-speech.md`.
- HA voice integration in `ha-echo-show-5`:
  `integrations/fcc-voice-backup/bridge.py`, `cloud_speech.py`,
  `scripts/render_voice_controls.py`, `docs/fcc-assist-behavior.md`.
- Documentation retrieval: `src/energy_rag/mcp_server.py`,
  `src/energy_rag/retrieval/chain.py` in `energy-data-rag-pipeline`.
- Device/controller observations and rollback: this repository's
  [controller guide](controller.md) and [deployment record](deployment-record.md).

Live host mappings, credentials, config snapshots and raw diagnostics stay
private. None are required to understand or reproduce this design.
