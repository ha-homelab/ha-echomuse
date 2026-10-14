# Russian energy reports in Assist

The renderer creates six read-only Russian intents for Home Assistant. Each
intent requests an authoritative Inverter Gateway report and returns speech to
the invoking conversation. It does not target a fixed speaker, call Cast, change
energy settings or depend on an LLM for numbers.

## Requirements

- IGW with `GET /v1/energy?locale=ru`, schema version 1 and `locale: ru` in its
  response. See the [IGW energy API](https://github.com/victron-venus/inverter-gateway/blob/main/docs/energy-api.md).
- An existing Russian HA Assist pipeline with local intent handling enabled.
- A direct trusted IGW endpoint and scoped read-only token. Use verified HTTPS
  or an explicitly trusted private cluster route; do not use redirects or
  credential-bearing URLs.

The package uses REST Command, Script, Intent Script and Conversation, all
built into HA. A TTS model or USB connection to the Dot is not part of installation.
The same intents work with EchoLocal, EchoMuse or another Assist satellite.

## Render and install

Run from this repository, choosing a new private staging directory:

```sh
python3 scripts/render_energy_assist.py --output private/energy-assist
```

Read the generated `INSTALL.md`. Back up the HA configuration, then copy:

- `packages/igw_energy_assist.yaml` into HA's packages directory;
- `custom_sentences/ru/igw_energy.yaml` into HA's matching directory.

Add `igw_assist_energy_url` and `igw_assist_energy_authorization` to HA's
`secrets.yaml`. The URL ends in `/v1/energy?locale=ru`; authorization is `Bearer `
followed by the scoped IGW read token. These values stay private. Do not copy
them into the generated package or this repository.

Run HA configuration validation. Reload REST Command, Script, Intent Script
and Conversation if already loaded; otherwise restart HA after validation.
Existing Google display scripts remain separate. Test in Assist's text UI
before speaking to a satellite.

Example requests:

- «Какая сейчас энергетическая сводка?»
- «Сколько заряда в аккумуляторе?»
- «Сколько сейчас дают солнечные панели?»
- «Сколько солнце выработало сегодня?»
- «Есть ли аварии?»
- «Что с сетью?»

The last question returns the complete power-flow report, including the grid,
when those sources are configured. It does not switch grid power.

## Validation and limits

The package rejects HTTP failures, malformed envelopes, wrong locale, an old
response, a future timestamp beyond five seconds, unsafe control characters,
and a fresh report claiming MQTT is disconnected. Gateway report warnings remain intact. Missing data is
not converted to zero. IGW owns numeric accuracy and per-source freshness.

The response-age limit defaults to 30 seconds and can be rendered between 5
and 120 seconds. HTTP timeout is 10 seconds. The private helper permits four
parallel calls, keeps no script traces and does not queue stale requests.
The status intent prefers IGW's brief report. Replies over 900 characters are
refused instead of truncated, preserving the existing speech boundary and
avoiding partial warnings. This package does not add historical energy data.

On failure the response is: «Сейчас не удалось получить достоверную
энергетическую сводку. Попробуйте позже.»

## Tests

The renderer requires only the Python standard library. Its tests use the
hash-locked `requirements-dev.txt`:

```sh
uv venv .venv --python 3.11
uv pip sync --python .venv/bin/python --require-hashes requirements-dev.txt
.venv/bin/python -m unittest discover -s tests
```

CI also executes `tests/runtime_energy_assist.py` in a pinned HA image without
network access. Those tests instantiate an isolated HA instance with a fake
gateway, exercise the real intent/script engine and sentence recognizer, and
verify simultaneous responses and failure handling. They do not operate the
live home or prove microphone/TTS quality.

To roll back, remove only the two installed files and reload the same
integrations. Remove their secrets only if unused elsewhere. No pipeline,
speaker firmware or Google display configuration needs to be reverted.
