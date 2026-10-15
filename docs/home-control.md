# Local home control and statistics

EchoMuse is the microphone and speaker. Home Assistant owns the devices, their
permissions and recorded history. An Ollama model running on a home server can
use the optional `custom_components/echomuse_home` integration to find devices,
read current values, request historical statistics and perform device actions.
No firmware change or USB connection is needed for this feature.

## Install

1. Keep a working Assist pipeline and a backup of HA configuration. This
   integration targets Home Assistant 2026.10 and its `probatio`/`ToolResult` API.
   Run both isolated runtime tests before using a different HA version.
2. Copy `custom_components/echomuse_home` into HA's `custom_components` directory.
3. Add the configuration below to a package, replacing example entities with
   your reviewed device list. Copy `examples/custom_sentences/ru/echomuse_home.yaml`
   to `custom_sentences/ru/echomuse_home.yaml` in HA's configuration directory.
   Validate configuration and restart HA once.
4. Run Ollama on an always-on local server. Store model files on persistent
   storage. Keep the API private; allow HA to reach it, not the internet. Disable
   Ollama cloud features and, after downloading the model, deny workload egress.
5. Add the built-in **Ollama** integration using that private endpoint. Add a
   conversation agent, select the downloaded tool-capable model, disable thinking
   for this latency-sensitive use, and select only **EchoMuse local home control
   and statistics** in the agent's Home Assistant API selector. Use
   `examples/home-assistant-prompt.txt` as the agent instructions; it distinguishes
   switch states from energy sensors when answering Russian questions.
6. Clone the working Russian Assist pipeline. Keep its tested recognition and
   Russian TTS providers, enable **Prefer handling commands locally**, and change
   only the conversation agent. Give the pipeline a distinct name.
7. Assign the new pipeline to both Assistant selectors on each satellite. Keep
   the previous FCC pipeline for rollback. Do not route unmatched household
   requests automatically to an external model.
8. For a CPU-based local model, set the EchoMuse controller environment variable
   `EM_TTS_WAIT_TIMEOUT=120` and restart the controller. Its upstream default is
   30 seconds; the supported ceiling is 120 seconds. This is separate from an
   Assist WebSocket test's timeout. Increasing one does not increase the other.

```yaml
echomuse_home:
  control_entities:
    - light.kitchen_lamp
    - switch.heater_one
    - cover.living_curtains
  aliases:
    light.kitchen_lamp:
      - кухонная лампа
      - кухонную лампу
    switch.heater_one:
      - первый обогреватель
      - обогреватель один
```

These aliases help the model's search tool. Also add the same aliases through
HA's entity settings and expose those devices to Assist for the faster built-in
intent path. Add Russian aliases to areas. Names and room assignments should
reflect actual wiring; do not infer an unidentified outlet's load from its ID.

A reproducible starting profile is Qwen3 4B Instruct (`Q4_K_M`, approximately 4.0
billion parameters) with Ollama 0.40.4. Provision it before denying outbound
connections:

```sh
ollama pull qwen3:4b-instruct
ollama create echomuse-home:4b -f examples/Modelfile.home-assistant
```

Select `echomuse-home:4b` in HA, disable thinking, set context to 8192 and keep the
model loaded (`keep_alive: -1`). The profile bounds generation to 384 tokens,
uses deterministic sampling and disables presence penalties. Keep
conversation history short on a CPU server. The thread count in the example is
host-specific; benchmark it alongside speech synthesis and other resident services.
Do not judge steady-state latency from the first request, which also loads weights.

For Kubernetes, `examples/home-voice-ollama.yaml` provides storage, a private
service and ingress policy. If HA uses `hostNetwork`, its traffic may originate
from the HA node or its overlay interface instead of a namespaced pod. Add only
that observed source address as an ingress `ipBlock` (`/32` for IPv4), and verify connectivity. After
provisioning, apply `examples/home-voice-offline.yaml` and verify both blocked
outbound connections and working HA inference. Namespace labels alone do not
establish isolation unless the cluster's network plugin enforces the policies.

## Voice and grammatical gender

The example agent prompt uses feminine Russian forms when the assistant refers
to itself, such as «поняла» and «готова». It preserves the normal gender of device
names and other subjects. It also preserves action verification: a feminine
confirmation must not imply that a requested action succeeded before the tool
confirms it. Copy the updated prompt into the local Ollama conversation agent's
instructions to apply this change; editing the example file alone does not
update Home Assistant. Keep the agent's model, API permissions and local-only
data handling unchanged.

The intended female speech voice is **Piper Irina medium**. Voice selection is
separate from the agent prompt: provision and validate the pinned Irina assets
in the Russian speech service, then select the voice actually advertised by its
Wyoming integration in **Settings → Voice assistants → Local Russian Home**.
Keep a receipt of the previous service image, voice configuration and pipeline
for rollback. Do not relabel Denis as Irina; the loaded model must match the
advertised voice. Verify both Assistant selectors on each Dot still use the
intended pipeline. Other satellites using that same pipeline also inherit its
TTS choice.

After applying both changes, fetch an actual Russian WAV from the selected TTS
entity and test each satellite. Ask «Ты готова?» to check the model's self-reference,
then ask for a current device reading and compare it with HA. Native intent
responses use their own templates and do not pass through the model prompt.
These instructions describe the rollout; they are not proof that a live voice
or pipeline has been changed.

## Tools and behavior

- **FindEntities** searches current names, IDs, aliases and assigned rooms. It
  accepts Russian and English terms, an optional domain/state filter and an
  offset. Results contain at most 12 entities, a total count and a continuation
  offset. Discovery includes control-device state and whether control is allowed.
  Sensors return names, units and measurement classes without numeric snapshots.
  Fetch a current reading with **GetEntityState**, or a past interval with
  **GetStatistics**. This prevents a lifetime counter in search results from
  masquerading as monthly consumption. Search aliases stay inside HA; the model
  does not receive the alias catalog or unnecessary timestamps.
- **GetEntityState** refreshes one previously discovered entity. It returns a
  bounded state and selected operational attributes; credentials, URLs, camera
  tokens and arbitrary attributes are not included.
- **ControlDevice** accepts a device/room query, an optional domain and a fixed
  operation. It searches only `control_entities`, checks user permissions and
  requires exactly one match before dispatch. It resolves and executes in one
  call; the model does not need a separate lookup before issuing a command. There is no arbitrary service, template,
  shell, SQL or URL tool. Ambiguous names and unavailable devices are rejected before dispatch.
  Service completion and the observed state are reported separately: a service
  accepting a request is not proof that the physical device moved or switched.
- **GetStatistics** queries HA Recorder for a discovered sensor. Supported
  periods are today, yesterday, the last 24 hours, this week, this month and a
  custom past interval of at most 366 days. Calendar boundaries use HA's timezone;
  custom interval ends are exclusive. HA computes minimum, mean, maximum and
  accumulated-counter change. Missing values remain missing. Database gaps and
  the unfinished current interval mean a result may not cover the entire period.

Examples to say after the wake word:

- «Включи кухонную лампу»
- «Выключи второй обогреватель»
- «Какие лампы сейчас включены?»
- «Первый обогреватель сейчас включён?»
- «Какая мощность третьего обогревателя?»
- «Сколько энергии потребил первый обогреватель вчера?»
- «Какая средняя температура была вчера?» — specify the room or sensor when asked.

In HA 2026.10, the pipeline deliberately filters `HassGetState` and standard
media-search intents out of the built-in fallback when the selected model has
control support. Therefore “prefer handling commands locally” does not make every
state question bypass the model. The included sentence file uses the distinct
**EchoMuseGetState** intent, registered by this integration, for common sensor
readings, on/off questions and lists of active lights. It reuses HA's native target
matching and Assist exposure checks, checks user read permissions and never
calls an actuator. Sensor aliases should contain the measurement as well as the
device, for example «мощность первого обогревателя». Both «Какая» and «Какова»
are accepted. Unknown/unavailable readings are reported explicitly. Period
questions stay outside this current-state grammar and retain the Recorder path.
Existing sentence-trigger music routing remains separate and takes priority.

The existing deterministic IGW energy sentences remain available. They return
the measured energy report without using the LLM. Do not interpret watts as
kilowatt-hours, sum instantaneous power samples as consumption, or quote costs
without a configured tariff and a measured consumption interval.

A fifth read-only tool, **GetDateTime**, supplies the current HA date, time and
timezone on demand. HA recognizes this tool and omits its changing timestamp
from the system prompt, allowing Ollama to reuse the common prompt prefix across
requests. Relative statistics periods still resolve against HA's current time.
Avoid adding a seconds-level clock to the agent's own prompt.

## Access boundaries

The API is offered only to the Ollama integration. Configure that integration
with a genuinely local server: the platform check does not prove where a
user-supplied Ollama URL runs. The reference deployment additionally isolates
the inference workload from outbound connections after model provisioning.

The read catalog covers operational HA domains, including sensors, device
controls, weather, calendars, automation states and update states. It does not
fetch camera images, calendar event contents or arbitrary entity attributes.
Existing per-user entity read/control permissions are enforced when HA supplies
a user context. Trusted internal HA contexts, such as satellite interactions,
retain the explicit control allowlist. Read access does not grant write access.
This allowlist applies to these LLM tools. The faster built-in intent path uses
HA's separate Assist exposure settings; audit those independently. Existing
exposure grants to other assistants are not removed by installing this component.

The language-model path is local. Reusing an existing cloud speech-recognition
provider still sends microphone audio to that provider. Select a local STT
service as well if the entire audio pipeline must operate locally. The existing
Piper Russian speech synthesis runs locally.

Supported write operations cover lights, switches, fans, humidifiers, thermostats,
water-heater target temperatures, covers, vacuum cleaners, media transport/volume,
explicitly allowlisted scripts/scenes, input booleans, bounded numeric controls
and selections from reported options. Numeric values must be
finite; percentage values are bounded to 0–100, and temperatures use the device's
reported minimum/maximum and units. A request allows at most eight actions.
Locks, alarms, arbitrary buttons, infrastructure administration and arbitrary
configuration changes are not implemented as write operations. Keep server power,
network ports and unknown outlet loads out of the allowlist.

The local model can still misunderstand a request. Test ambiguous names,
unavailable devices and state-only questions before enabling everyday use. The
tool layer prevents unsupported writes; it does not make language understanding
infallible or replace the physical controls and protection of a heater.

## Validation and rollback

Run the dependency-free policy tests and the runtime tests inside the pinned HA
image used in CI. Runtime tests create a separate temporary HA instance with
synthetic entities; they never call the live home or its database. Test permission
boundaries, native Ollama argument normalization, schema conversion, named-device resolution and actual service dispatch in that isolated instance,
missing statistics, invalid numbers and DST boundaries.

When testing a model outside the native integration, preserve the native tool
result envelope (`data` and `error`) and tool-call sequence. A hand-written
simulator with a different envelope is not an acceptance test for the HA agent.

For live acceptance, first ask state and history questions in Assist's text UI.
Check the returned values against Recorder and entity state. Test a reversible
light command and confirm its state, then check each satellite separately. Do not
use heater activation as a generic acceptance test.

Rollback: select the previous pipeline on both Assistant selectors of each Dot.
Remove the `echomuse_home` package, custom component and its custom sentence file,
validate and restart HA. Restore the prior controller timeout if needed.
Restore only aliases/exposure settings changed by this rollout from the private
journal. Preserve other concurrent HA changes and model storage unless deliberately
retiring the local service.

Reference: [HA LLM APIs](https://developers.home-assistant.io/docs/core/llm/),
[Ollama integration](https://www.home-assistant.io/integrations/ollama/), and
[Qwen3 Instruct](https://ollama.com/library/qwen3:4b-instruct).

## Deployed local home assistant — October 14, 2026

The local route uses Home Assistant 2026.10.0, Ollama 0.40.4 and Qwen3 4B
Instruct (Q4_K_M). The reviewed control list contains 119 household entities;
Russian entity and room aliases support device discovery. Home state and
statistics go to the local model. The inference workload denies outbound
connections after provisioning; the previous external general-question route
has no automatic fallback from this pipeline. Russian synthesis remains local
Piper Denis. Speech recognition still uses the existing cloud FCC service.

The dedicated model runs on an existing two-core/four-thread, 8 GB server, with
one active inference request, a bounded queue, a 5 GiB memory limit and a
256 MiB prompt cache limit. The running model occupied approximately 4 GiB.
This is a functional CPU deployment, not an instant-response benchmark.

Initial validation included 55 policy/source tests and 17 tests in an isolated HA
runtime. Live text checks distinguished on/off and unavailable states without
sending control commands. A monthly energy question invoked FindEntities and
GetStatistics on the cumulative sensor, with the correct calendar interval,
unit and counter change from Recorder. A separate synthetic case used different
lifetime and monthly values to detect accidental substitution. Sensor discovery
therefore exposes metadata rather than numeric snapshots.

During tuning, cached state questions took about 23–27 seconds. The live monthly
Recorder query took 197.6 seconds after a changed prompt and a broad sensor
lookup; it included rebuilding the prompt cache. Avoid changing prompt text on
every request: the GetDateTime tool suppresses HA's automatically appended
seconds-level clock. A broad sensor search can still require substantial CPU
time. These samples are text-service timings, excluding microphone capture,
recognition and playback; they do not establish sustained-load performance.

The first attended test exposed a deadline that those text-only tests did not
exercise. Both Dots correctly transcribed «Какова мощность первого обогревателя».
The controller then cancelled the HA turn 30 seconds after audio ended, before
the model finished. HA showed `run-end` without `intent-end` or `tts-end`; the
controller logged `Timeout waiting for TTS response from HA`. A preceding
attempt had transcribed only `uh`, explaining the unrelated greeting. These
were separate recognition and response-wait failures.

The correction adds the fast native state intent above and raises the shared
controller's response wait to 120 seconds. It does not make this CPU model faster:
uncached multi-step history requests can still exceed that ceiling. Validate a
real satellite turn, including its controller log, before claiming voice success.

After the correction, simultaneous requests in the two actual Dot device
contexts took 0.518 and 0.487 seconds in the intent stage. Both were marked
`processed_locally: true` and returned the current heater power in Russian with
watts pronounced explicitly. Generated audio was fetched in 4.708 and 4.707
seconds total. These are intent-to-audio service measurements, excluding the
microphone, STT and physical playback. Both pipelines and all four Assistant
selectors were rechecked; both satellites and players were available. The
updated suite passed 55 policy/source tests and 19 isolated HA runtime tests,
including native exposure, user permissions, unavailable readings and the
control-capable pipeline's intent filter.

The operator then repeated «Какова мощность первого обогревателя» by pressing
the action button on each Dot and confirmed that **both answered in Russian
without the previous hang**. The first recorded button turn shows 24 ms from
STT result to the TTS URL, followed by a device-reported playback completion;
its complete turn took 17.24 seconds, including captured speech, recognition,
audio generation and playback. This validates that specific attended question
on both Dots, not every possible local-model request.

The final action check used **ControlDevice** to resolve and turn on one lamp.
HA emitted the expected `light.turn_on` event and reported `on`; the test then
sent `light.turn_off` and verified restoration to `off`. This cold-prompt test
took 111.0 seconds. No heater actions were issued by the acceptance tests.
The action interface deliberately combines resolution and execution because
an earlier lookup-first model path could claim success without a service call.

Before assignment, both actual Dot device contexts completed the local-model
math question through intent and Russian TTS, and the resulting audio files
were fetched (6.841 and 2.034 seconds). Two simultaneous native energy-summary
requests also returned audio (3.365 and 3.362 seconds). These service checks did
not play audio on the physical speakers.

At final readback, **both Assistant selectors on each of the two EchoMuse Dots**
used **Local Russian Home**, with `conversation.local_russian_home`, Russian
recognition and local Piper TTS. Both satellites and their native/Music
Assistant players were available and idle. The primary wake word remained
**Hey Jarvis**, with the secondary wake word disabled. The prior FCC pipeline
remains available for rollback. Fresh attended microphone, wake and listening
acceptance is separate from these verified server-side results.
