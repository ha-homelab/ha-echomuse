# Family conversation, poetry and music

The `myshka_family` integration adds reviewed poems, nursery rhymes, riddles and
optional original stories alongside the existing household assistant. It keeps
the wake-word model, Russian STT/TTS selection and home-control tools. A request
for a poem should produce a poem rather than an explanation that a home-control
model has no poems.

The component runs in Home Assistant and works with both TECHO5 and EchoMuse
satellites using the same Assist pipeline; it does not require a firmware change.

This feature is separate from wake-word training. Better recognition does not
give a language model a verified book collection, a web-search tool or a singing
voice. The [home-control investigation](home-control.md#investigation-on-october-16-2026)
records why changing the general household prompt alone was insufficient.

## Local content and native intents

Five native intents handle reading, original creation, family activities, riddle
answers and song requests. They run before the existing conversation agent when
**Prefer handling commands locally** is enabled. The normal assistant retains
household state, history and control. Mixed creative/device commands are rejected
with a request to say them separately.

The [literary catalogue](../custom_components/myshka_family/library.json)
contains these four complete works:

- **Александр Блок — «Зайчик»**, for a request such as «Расскажи мне стишок о
  зайке». The [source text](https://ilibrary.ru/text/5114/p.1/index.html) describes
  an autumn bunny; it is not Agniya Barto's different work with a similar title.
- **Аполлон Майков — «Колыбельная песня»**. The
  [source text](https://ilibrary.ru/text/4378/p.1/index.html) is the poem beginning
  «Спи, дитя мое, усни!». Recitation is different from a musical performance.
- **Аполлон Майков — «Ласточка примчалась»**, from a
  [pinned Wikisource revision](https://ru.wikisource.org/w/index.php?title=Ласточка_примчалась_(Майков)&oldid=5708895).
- **Сергей Есенин — «Берёза»**, from a
  [pinned Wikisource revision](https://ru.wikisource.org/w/index.php?title=Берёза_(Есенин)&oldid=5746567).

Each entry records its source edition, review date, authorship, rights evidence,
normalization and SHA-256 of the complete text. Composition and publication dates
are separate; unknown first-publication dates remain unknown. Only historical
poem bodies are mirrored, not modern illustrations or editorial commentary.
This is a local mirror of verified online sources, **not live Internet search**.
The response includes attribution and a source card. It must not claim to have
just searched the web for a cached poem.

«Расскажи свой стишок про зайку» or «Расскажи весёлый стишок про котика»
selects a locally prepared original piece, without a model request.

The activity module also contains **nine original short verses/nursery rhymes
and six riddles**, including harder riddles for adults. Original works are
labelled as original and are not attributed to famous authors. A specific named
work outside the reviewed catalogue receives an explanation and alternatives;
it is not silently replaced with a different author's poem. A general topic
without a catalogue match may use the explicitly configured creative backend.

Riddles keep their answer hidden until the listener answers or requests help.
Useful follow-ups include «Мой ответ — заяц», «Подсказка к загадке», «Ответ на загадку» and «Ещё одну загадку». State
is isolated by the source device and user, expires after ten minutes and has a
bounded session count. Browser requests without a device identity cannot share
another listener's riddle. The code does not start recording or enable automatic
follow-up listening. Use the usual wake phrase for a new turn when the microphone
is idle. Bare numbers and generic phrases such as «Не знаю» or «Подскажи»
are deliberately not registered as global family commands, so they cannot
steal a household assistant's clarification. Repeating a riddle or nursery rhyme
retains its audience or topic.

## Optional original stories and poems

Original generation is a separate opt-in capability. Neither creative backend
receives home tools, household state or conversation history from this
integration. Reading the reviewed catalogue and using the built-in activities
continue to work without either backend.

### Public topics through the existing general-purpose bridge

The optional `public_creative_uri` can point to the existing stateless FCC
bridge for Nemotron 550B. It is **not enabled in the reference deployment**:
additional trials returned malformed Russian verse and prose. The user previously approved
that provider for general questions without personal data. This is a specific
creative route, **not an automatic cloud fallback from the household agent**.

The reviewed bridge version **0.1.4** was attested without an IGW configuration,
HA credentials, home tools or conversation history. That deployment property
must be preserved: a private network address alone does not prove that an
arbitrary replacement bridge is stateless. The integration validates the local
bridge address, but cannot inspect another service's credentials or retention
policy. The external provider's own data handling still applies.

[The public-topic gate](../custom_components/myshka_family/public_topics.py)
validates every word against a finite vocabulary. It accepts one to three
canonical themes, such as a bunny, a robot and cat, a dinosaur, friendship or
space. An unknown word, name, number or unsupported character rejects the
**entire** request before any creative network call. It does not try to redact
personal data and then forward the remainder.

For example, «Сочини сказку про робота и кота» becomes a code-owned instruction
to write a short original Russian story with the canonical themes `робот, кот`.
Only that instruction is sent. The original transcript, device identity, user
identity, conversation context and household state are not included. A more
specific or unfamiliar subject may therefore receive a request to name a
simpler general theme. The full vocabulary is defined in the linked source;
this limited expressiveness is intentional.

Generated text is labelled as a new work. Requests are serialized, have a
**25-second generation budget**, and receive bounded plain-text validation.
Timeouts or malformed responses produce a useful suggestion to ask for a
ready-made poem or riddle. There is no retry through the household agent or a
second provider. The prompt requests child-suitable Russian, but does not
establish that every generated rhyme or story is good; listening review remains
necessary.

### Local generation and its measured limits

The [fixed-model local server](local-family-server.md) provides a bounded MLX
endpoint on Apple Silicon, with a separate private authentication key. It
accepts the same local request contract and does not expose model management.


The optional `ollama_url` route uses a local model with a separate creative
prompt and no household tools. It remains supported for an adequately capable
local server. It is **not the selected production option for the measured CPU
server**: two synthetic Qwen 4B trials took approximately **35 and 38 seconds**
and did not meet the creative-response target. A synthetic FCC story trial took
approximately **9.1 seconds**, but further 2.8–3.0 second trials produced weak
Russian and were rejected. Two other free model candidates timed out at
approximately 31 seconds; a third returned provider-unavailable. No candidate
was accepted as a reliable creative upgrade. These are individual backend trials, not a
benchmark guarantee and not the delay from wake word to audible response. STT,
networking, TTS and playback add their own time.

A larger model can run on an Apple Silicon Mac. The separately pinned
[fixed-model server](local-family-server.md) uses
[MLX-LM](https://github.com/ml-explore/mlx-lm) and a non-thinking
[Qwen3-14B 4-bit model](https://huggingface.co/mlx-community/Qwen3-14B-4bit).
It presents only the bounded creative API; it does not expose model download,
model selection or household tools. [Ollama's Metal support](https://docs.ollama.com/gpu#metal-apple-gpus)
is another possible runtime for an independently validated model.

The reference Mac has limited free disk and also runs unrelated image-generation
jobs. Model files are kept on private NAS storage rather than copied into the
repository or consuming the remaining Mac disk space. An SMB cold load and a
warm generation are separate measurements: network-file stalls must not be
reported as a model's thinking time. A model is not selected for the live route
merely because its download or protocol tests completed. See the deployment
record below for the actual acceptance state.

A Mac's sleep, shutdown, memory pressure or lost NAS connection can make original
generation unavailable. The permanent HA server still provides the reviewed
library, local activities and household intents. There is no automatic Homeway
or other cloud fallback.

## Install and configure

1. Copy `custom_components/myshka_family` into the HA configuration directory's
   `custom_components` folder.
2. Copy [the Russian sentence file](../examples/custom_sentences/ru/myshka_family.yaml)
   to `custom_sentences/ru/myshka_family.yaml` in the HA configuration directory.
   Keep the existing household and music sentence files.
3. Add the configuration below, validate the complete HA configuration, then
   restart HA. Keep the current Assist agent, Russian STT/TTS and wake word.
4. Enable **Prefer handling commands locally** for that assistant and verify
   native text intents before an attended speaker test.

The minimal configuration enables the offline content and activities:

```yaml
myshka_family: {}
```

To opt into the separately audited public-topic bridge and song playback:

```yaml
myshka_family:
  public_creative_uri: !secret myshka_public_creative_uri
  music_config_entry_id: !secret myshka_music_config_entry_id
  music_players:
    YOUR_HA_SATELLITE_OR_DEVICE_ID: media_player.your_dot
```

Keep real service addresses and registry identities in private configuration.
The secret's URI format is
`tcp://creative-bridge.example.svc.cluster.local:10600`; replace it with the
actual audited internal service. `music_config_entry_id` identifies the Music
Assistant integration entry, not a speaker. Each mapping key must match the
source satellite ID, or device ID when no satellite ID is supplied. Its value
must be the corresponding current Music Assistant player entity. Add a mapping
for each speaker rather than routing all requests to a shared default.

For a future independently validated local server, replace
`public_creative_uri` with this configuration:

```yaml
myshka_family:
  ollama_url: !secret myshka_ollama_url
  model: qwen3:14b
```

`ollama_url` must be an HTTP(S) origin with a private IP, `localhost`, or a
Kubernetes `.svc.cluster.local` hostname, without credentials, path or query.
Installing the integration does not download the selected model. Configure one
creative backend deliberately: if both are present, `public_creative_uri`
takes precedence and there is no automatic local fallback.

The content handler being local does not make the full voice path offline.
The [recorded pipeline](russian-voice-validation.md) uses cloud speech
recognition; this feature does not change that provider.

## Expression and songs

The installed female Russian speech service already exposes voice, speed, pitch,
sentence pause, intonation and emphasis controls. See
[speech settings](speech-settings.md). Its
[upstream SSML implementation](https://github.com/snakers4/silero-models/wiki/SSML)
supports pauses and prosody. The application accepts bounded options rather than
arbitrary user-provided SSML. Preserve punctuation and verse structure before
synthesis; audition small changes before changing shared defaults.

Silero Baya is a speech synthesizer. Pitch controls do not make it a singing
synthesizer or supply a melody. «Спой песню…» therefore requests an existing
recording through Music Assistant, not generated singing. The handler searches
**the user's music library only**, requires a single exact normalized title
match, and accepts a library track URI. It does not search the public web,
choose an arbitrary similarly named song, or synthesize copyrighted lyrics.

A missing title, ambiguous result or unavailable player receives a clarification.
The handler checks the requesting user's player-control permission when a user
identity is present and routes to the explicitly mapped source speaker. A
successful service call is reported as sending a song to that speaker; actual
audibility remains a playback check. Search and playback dispatch share a 15-second deadline. A search timeout does
not start music; a playback timeout is reported as uncertain because the player
may already have received the command. No automatic retry is sent. Existing
general music and stop commands continue through their established routes.

## What Homeway already does

[Homeway Sage](https://blog.homeway.io/homeway-sage-free-private-intelligent-chatgpt-for-home-assistant-assist-voice/)
combines hosted language models with web search, page retrieval, weather and
conversation memory. Those capabilities help explain the richer free-form
experience. Its public repositories contain the add-on and relay protocol; the
reviewed sources do not expose a portable set of children's entertainment skills
that can simply be copied into a local model.

The [reviewed Sage handler](https://github.com/homewayio/AddOn/blob/1c0bfacfa3d0727cef4dd90454ef5509def3b9d0/homeway/homeway_linuxhost/sage/sagehandler.py)
passes conversation history and exposed home context/states to its cloud chat
operation. Selecting it as an automatic fallback therefore needs more than an
instruction saying that a query is general. This differs from the family route's
finite canonical prompt and separately audited stateless bridge. The
[current privacy policy](https://homeway.io/privacy) says Sage stores chat
history and that third-party processing has provider-specific terms. This is
more specific than the older launch article's deletion wording.

## Existing tools worth reusing

[Tools for Assist](https://github.com/skye-harris/llm_intents) is an existing HACS
integration that adds optional search, Wikipedia, weather, media and utility
tools to supported conversation agents, including Ollama. Search supports
Brave, Tavily and a configured SearXNG server. It is a plausible extension for
general factual lookup without replacing the wake word or voice.

Its [reviewed SearXNG implementation](https://github.com/skye-harris/llm_intents/blob/112aed155c90bdc5f9255bf1ffdd696b741a0d48/custom_components/llm_intents/searxng_search.py)
returns titles and snippets rather than a verified complete poem; it omits the
result URLs in that response. The
[shared search instruction](https://github.com/skye-harris/llm_intents/blob/112aed155c90bdc5f9255bf1ffdd696b741a0d48/custom_components/llm_intents/base_web_search.py)
asks for short summaries. Installing it alone would not solve exact literary
recitation. SearXNG hosted at home still sends search queries to its configured
external engines.

The [built-in Gemini integration](https://www.home-assistant.io/integrations/google_generative_ai_conversation/#google-search)
documents a separate search-only agent called through a script because its
Google Search tool cannot be combined with other tools in that integration.
[Extended OpenAI Conversation](https://github.com/jekalmin/extended_openai_conversation)
supports external API/webpage functions and configurable compatible endpoints.
These are alternatives to evaluate, not dependencies installed by this feature.

A future general web route should retain source URLs, separate retrieved text
from executable instructions, bound time/output, and never automatically send
household state, history or a private transcript to an outside model. It should
distinguish a sourced quotation from an original story. The current family
integration does not install live web search or replace the household agent.

## Verification

The catalogue tests run offline and pin full-text hashes, line counts, attribution
and source metadata. Activity tests cover riddle state, expiry and rejection of
unsupported or mixed requests. The public-topic tests must verify that an
unknown word, personal name or number prevents every outbound creative call,
and that accepted prompts contain only canonical themes and code-owned text.
Integration checks should additionally exercise:

1. «Расскажи мне стишок о зайке» and a supported author/title, with attribution
   and a source card; an unavailable named work must not become a fake quotation.
2. «Сочини сказку про робота и кота», an allowed dinosaur topic, an unknown
   subject, an unavailable backend and the generation deadline.
3. A riddle, a wrong answer, a hint, the right answer and a new riddle.
4. Two independent listeners; neither receives the other's hidden answer.
5. A current household sensor request and an unambiguous light command through
   the existing native route, without simulated success being spoken as fact.
6. Exact-title song search, ambiguous/unavailable results, requesting-player
   routing and the existing stop command.
7. Real Russian TTS generation with valid audio; listening quality is a separate
   attended check and must not be inferred from generated byte counts.

Do not run physical playback or actuator checks as unattended unit tests.
Publication of this guide or passing tests does not prove that the integration
has been loaded by the running HA instance. Record deployment and attended
listening outcomes separately from the backend trials above.

## Reference deployment — October 26, 2026

The native family integration and sentence file were installed in the existing
HA configuration, then HA was restarted. Both creative endpoints are absent
from the deployed settings. A private MLX runtime and the pinned 14B model were
prepared, but a cold load stalled on NAS reads after a network handover. The
model did not reach generation, so no 14B speed or Russian-quality result is
claimed and it is not enabled for family conversation. A separate SSH transfer
probe excluded connection setup and measured approximately 1.97 MB/s of payload
throughput. An 8B model on local disk was also considered, but its preflight
would leave only 6.72 GiB free, below the chosen 8 GiB reserve, so it was not
downloaded. The private runtime and verified NAS weights are retained; all test
processes exited and temporary package caches were removed. Homeway was not enabled: its monthly free allowance
was exhausted, and the household retained the local-data preference.

The reported bunny request returned the complete attributed Blok text through
the selected **Local Russian Home** pipeline in both Dot device contexts. These
warm intent-only requests took approximately **0.058 and 0.077 seconds**. A riddle,
hint, wrong answer and answer reveal also completed locally. These checks used
text inputs and did not activate a microphone or play sound. They do not measure
end-to-end speech delay or prove acoustic quality on the offline first Dot.

A service-connectivity check also found a missing host-network source in the
Ollama ingress policy and a temporary NUC heartbeat outage. A single observed
source was added to the private policy; its egress denial was preserved. The
NUC recovered without a restart, both Ollama entries returned to loaded, and the
original heater sensor phrase again completed through native intents.

The original household tool source, household voice package and pipeline storage
were byte-identical before and after installation. The optional creative-model
comparison did not change any shared model deployment. Music targeting was tested
with an isolated HA service registry; no real music was started. A library search
for a sample children's song returned no match, so song availability must not be
assumed from the new command support.
