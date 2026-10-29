# Guarded, one-way announcements

The optional announcement services in the existing `echomuse_home` integration
accept **already rendered audio**. They do not synthesize speech, open a SIP
call, start Assist, or request microphone audio. Ordinary calls continue to use
the one SIP extension assigned to each physical device.

This is the `0.4.0b2` integration-source beta. Offline protocol and HA
adapter checks do not establish acoustic quality or installation on a device.
Use the capability query to distinguish an installed guarded endpoint from
stock firmware. No fallback to an unguarded announcement is enabled.
Version b2 adds explicit, capability-gated music ducking; the default remains
the original idle-only `skip` policy.

## Previous b1 deployment check — October 29, 2026

The four services are active after one coordinated Home Assistant restart.
Both TECHO5 Dots, running the experimental `v1.0.40-myshka.1.alpha.1` daemon,
returned the expected protocol, a boot identifier and all five capabilities
through this adapter. Three additional capability probes per Dot succeeded.
Their voice/media entities were idle and their existing SIP accounts ready.
No announcement, call, recording or test playback was started by these checks.
Acoustic acceptance remains pending.

The live installation used a hash-checked, targeted overlay on the existing
`0.2.0` component: service registration, announcement modules, service metadata
and version were updated while existing household intent/policy behavior was
preserved. The published `0.4.0b1` source package also contains the repository's
other changes; this deployment does not claim to have activated those changes.
The [Dot validation record](https://github.com/ha-homelab/ha-techo5-dot/blob/codex/guarded-announcements-20261029/docs/guarded-announcement-validation.md)
records the binary, source pins and maintenance boundaries.

## Requirements

- Home Assistant 2026.10 with `echomuse_home` configured as described in
  [local home control](home-control.md). No extra integration is required.
- A registered `assist_satellite` entity supplied by an encrypted ESPHome
  connection.
- Native device support for `cisco-announcement-v1`, with all five capabilities
  below explicitly true. The native actions must return JSON responses.
- A rendered audio file that the satellite can fetch, with at most 120 seconds
  of decoded audio. The native endpoint enforces that limit and the deadline.

The caller should generate Baya audio once through its configured
`tts.local_russian_speech` / `silero-ru-default` route, retain the resulting file
for the request lifetime, and submit that file. The conversation pipeline does
not select or change this announcement's voice. A `media-source://tts/...` URI
would request new synthesis and is rejected; local pre-rendered media sources,
Home Assistant paths, and HTTP(S) audio URLs on trusted Home Assistant origins
are accepted.

Prefer a relative path such as `/api/tts_proxy/<asset>` when the caller's HA API
address differs from HA's configured internal address. The standard HA
`async_process_play_media_url` helper makes it absolute and adds authentication
when needed. The allowed origins are HA's configured `internal_url`,
`external_url`, and the current result of HA's standard `get_url` selection.
An origin is the exact scheme, hostname and effective port (default 80/443).
The adapter checks absolute URLs before resolution, media-source results before
signing, and the final URL afterward. Other origins, including other private
LAN servers, are rejected. It never infers trust from an IP address being private,
the caller's API base URL, or a hostname suffix. Resolution does not synthesize
speech and does not fetch or play the file.

Install the updated integration files during a coordinated maintenance window.
An already running HA process does not load changed Python files merely because
they were copied. Do not restart a shared HA instance without coordination.

## Service contract

All services use `SupportsResponse.ONLY`. REST clients call
`POST /api/services/echomuse_home/<service>?return_response` with their normal
Home Assistant authentication and read the returned `service_response` object.
Submission and status are separate; a successful HTTP response is not evidence
that audio finished.

`announcement_capabilities` accepts one `entity_id` and returns:

```json
{
  "protocol": "cisco-announcement-v1",
  "atomic_idle_guard": true,
  "dedup": true,
  "owned_cancel": true,
  "honest_completion": true,
  "deadline_enforced": true,
  "duck_music": true,
  "boot_id": "device-boot-identifier"
}
```

The five booleans are forwarded only from a matching native protocol response
with a nonempty boot identifier. Missing support, malformed replies and
unavailable transport result in false capabilities. A caller must require all
five to be true before submission.

`duck_music` is an optional extension to the same protocol. It is false unless
the device explicitly advertises support, the base five guarantees are true,
and its dedicated `guarded_announcement_submit_duck` action supports JSON
responses. Missing, duplicate or nonresponsive native action definitions do
not qualify. Old b1 endpoints can continue to serve the default `skip` policy.

`announcement_submit` accepts:

```json
{
  "entity_id": "assist_satellite.example",
  "request_id": "announce-0123456789abcdef0123456789abcdef-201",
  "media_id": "/local/announcements/example.wav",
  "expires_at": 1793304100,
  "preannounce": false,
  "busy_policy": "skip"
}
```

The example deadline must be replaced with a fresh integer Unix timestamp in
UTC. It must be in the future and at most 180 seconds away. Request IDs contain
32 lowercase hexadecimal characters and a three-digit endpoint suffix. Generate
a new random ID for each new message; preserve the same ID for retries.
`preannounce` can only be false. `busy_policy` is either `skip` (the default)
or `duck_music`. The latter requires `duck_music: true`; unsupported requests
return `skipped` with `reason: duck_music_unavailable` without falling back to
another action or interrupting an existing activity.

### Music ducking

Use `"busy_policy": "duck_music"` with the same submit fields to ask the device
to continue eligible music at a reduced level while speaking. The dedicated
native action uses its owned music-duck lease; completion or cancellation
releases only that lease. Music is not replaced with the announcement file.
This policy does not grant permission to interrupt SIP calls, Assist, alarms
or other incompatible foreground activity, and does not bypass Do Not Disturb.

The attenuation comes from the device's existing **Music ducking** setting
(`media_duck_level` in its native HA entities; configuration `media.duck_db`).
The exposed range is **−40 to −3 dB**, in 1 dB steps, with default **−15 dB**.
More negative values make the music quieter. There is no per-request gain or
volume override in this service. The dedicated duck action keeps the stream
running even when the ordinary conversation setting is configured to pause
music; ordinary conversation behavior is unchanged.

Software tests cover protocol gating and ownership, not perceived loudness or
every music source. Acoustic quality, audible restoration and coexistence with
real music require a separately authorized listening check.

`announcement_status` and `announcement_stop` accept exactly `entity_id` and
`request_id`. They never synthesize or submit audio. Stop addresses the matching
native announcement only; it does not call a generic media stop or hang up SIP.
Status and owned cancellation remain available when a capabilities probe or
the local dispatch ledger is unavailable. They do not authorize new playback;
the native stop action must still match the exact request ID.

Responses contain the same `request_id`, `status`, and an optional machine-readable
`reason`. A validated device receipt also includes `boot_id`. Status is one of:

- `accepted`: native ownership was accepted; audio may still be fetching.
- `playing`: playback has started according to the native endpoint.
- `completed`: the native endpoint reported successful completion.
- `skipped`: busy, policy, deadline or capability checks prevented acceptance.
- `failed`: a known processing failure occurred.
- `stopped`: the owned announcement was stopped before completion.
- `unknown`: delivery or completion cannot be confirmed. This is not success
  and must not trigger automatic playback under a new ID.

## Ownership and completion

The device performs the atomic activity check against calls, Assist, media and
Do Not Disturb. `skip` requires idle media; `duck_music` permits eligible music
only through the dedicated native path. HA state snapshots alone cannot provide that guarantee. A
new legitimate interaction can preempt the owned announcement according to the
native contract. The HA adapter does not cancel an existing Assist pipeline.

Only native JSON action responses from the entity's own ESPHome runtime are
accepted as receipts. Global event-bus messages, idle state transitions and
completion of a generic `media_player.play_media` call are not used as proof.
The adapter rejects a response with the wrong request ID, protocol or boot ID.

Each service has a five-second response deadline; individual transport and media
resolution operations have two-second bounds. Device playback continues
asynchronously. If a response is lost, query status using the same request ID.
The device's expiry remains authoritative even if the caller disconnects.

Before dispatch, HA durably stores a fingerprint of the original `media_id`,
deadline and policy, keyed by device and request ID. The original b1 fingerprint
format is retained exactly for `skip`; `duck_music` adds its own policy
discriminator. Retrying an old skip request after upgrading remains a status
query. Reusing an ID with a different policy is a conflict in either direction.
The ledger stores no message text, audio URL,
authentication signature or recording. Repeated submissions query native status
instead of resending, including after an HA restart. A changed payload under the
same ID is rejected. This also avoids replay when resolving a media source
produces a different temporary signed URL on the second attempt.

The ledger retains expired IDs for seven days, holds at most 1,024 records,
and refuses additional dispatch when full. A corrupt/unwritable ledger blocks
new dispatch. It never silently resets the replay history. Native deduplication
is still required because a caller can reach the native API independently.

## Native bridge

The adapter resolves the target through HA's entity registry and its ESPHome
configuration entry. It does not construct a service name from untrusted input.
The native actions are:

- `guarded_announcement_capabilities(request_id: string)`
- `guarded_announcement_submit(request_id: string, media_id: string, expires_at: string)`
- `guarded_announcement_submit_duck(request_id: string, media_id: string, expires_at: string)` — optional b2 duck path
- `guarded_announcement_status(request_id: string)`
- `guarded_announcement_stop(request_id: string)`

Native `expires_at` is the decimal representation of the same Unix timestamp.
Every native JSON response must include `request_id`, `protocol`, and `boot_id`.
Capabilities include the five booleans; all other replies include `status`.
Native capability flags can be JSON booleans or the literal strings `true` and
`false`. A capabilities probe uses a fresh random request ID with suffix `000`;
it does not reserve or play an announcement.

Control services enforce the requesting HA user's entity-control permission;
status and capabilities enforce entity-read permission. Internal HA automation
contexts retain HA's normal trusted-system behavior.

## Quiet verification

The following tests use fakes and never contact a speaker:

```sh
python3 -m unittest discover -s tests -p test_announcement_protocol.py -v
python3 -m unittest discover -s tests -p runtime_announcements.py -v
```

The second command requires a compatible Home Assistant Python environment.
It covers real HA imports and schema behavior with fake registry, transport and
storage dependencies. Real audio quality, end-of-playback audibility and
preemption under acoustic conditions require a separately authorized listening
test. A software capability response does not replace that test.
