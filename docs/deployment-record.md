# Deployment record

## October 13, 2026 — controller and pilot preparation

The selected pilot is the second converted Dot. Its live USB identity was
matched to the existing private inventory before any write. The first Dot was
not changed; it was offline during this session, so no comparison result is
claimed.

Read-only inspection confirmed BISCUIT/Puffin hardware, root access, Fire OS 6
(Android 7.1.2 / SDK 25), and EchoLocal 0.0.8. The supported route is emOS;
upstream's FireOS in-place installer rejects this operating-system base.

Completed checks:

- Controller 2.26.0 deployed on a dedicated Kubernetes workload on an existing
  wired Linux host, using the pinned image digest and private persistent data.
  Administrator setup is closed and unauthenticated device API requests fail.
- Strict device approval, on-device wake mode, and the supplied Hey Jarvis
  model are configured. Utterance saving and wake-clip capture are disabled.
- Both original Home Assistant entries, the Assist pipelines, related registry
  entries, and the existing household music routing were backed up privately.
- A tested USB data cable connects the pilot to the maintenance host. TWRP
  3.7.0 and amonet 2 were verified. Both boot images and both system partitions
  match the expected Fire OS 6 / ARM32 layout and required donor files.
- Full boot, recovery, and boot-control partition backups were independently
  read and compared. EchoLocal runtime and Wi-Fi state were preserved. Copies
  on both the maintenance host and operator's Mac have verified hashes.
- The offline emOS v0.10 build uses the pilot's own kernel. A detached X.509
  certificate and partition padding follow its Android boot image. The builder
  now checks those bytes and extracts the same bounded image as upstream's
  wizard, retaining the full escrow and upstream byte-for-byte roundtrip check.
- Firmware v2.18.0, startup script, eight wake assets, and per-device connection
  files were staged with verified hashes and modes. Existing Wi-Fi is unchanged.

## October 13, 2026 — verified installation and first boot

The prepared emOS image was written only to the resolved `boot_a` partition.
An uncached full-partition read matched the image plus the untouched remainder.
`boot_b`, recovery, and boot-control metadata were byte-for-byte unchanged.

The pilot booted emOS, obtained Wi-Fi connectivity from its preserved settings,
and started EchoMuse v2.18.0. USB reported the expected EchoMuse/emOS identity.
The upstream console helper established a working shell without another reset;
its raw-mode setup and input flush avoided stale serial data. Device logs
showed a WSS connection to the intended controller and pending approval.

The exact pilot was approved after its firmware, identity, and authenticated
WSS contact were verified. Mandatory device TLS was then enabled; the
controller restarted and the Dot reconnected successfully. It reports local
wake detection with microphone streaming disabled.

A separate Home Assistant ESPHome entry was created against the controller's
allocated listener. Its new identity does not collide with the old EchoLocal
entry. Both new Assistant selectors explicitly use **FCC Russian Backup**.
The old entries and global pipeline configuration were verified unchanged.

## Attended voice smoke test

A button-triggered Russian question, «Сколько будет два плюс два?», completed
successfully and the operator confirmed the audible answer «четыре».
Controller metadata recorded an `ok` turn lasting 13.473 seconds in total,
zero playback underruns, and a maximum packet gap of 89 ms. These are one
turn's observations, not average latency or a long-term reliability result.
No utterance audio was saved. The device returned to local wake listening,
with WSS and Home Assistant still connected.

A subsequent wake trial at approximately five metres triggered Hey Jarvis
locally (score 0.6282 against a 0.5 threshold). Speech detection opened and
2.16 seconds of audio reached STT, which returned `no` instead of the intended
Russian question. The conversation stage returned empty speech, so no TTS
was requested. This was not a connection failure.

A subsequent controlled Hey Jarvis trial at approximately one metre completed
with the audible answer «шесть», confirmed by the operator. This demonstrates
one successful close-range wake and response, not reliable far-field speech
recognition. The five-metre STT limitation still needs evaluation before
changing microphone or wake thresholds.

## Music routing

The new native ESPHome player was appended to the existing Music Assistant
Home Assistant MediaPlayers provider. The previous player selection and other
provider configurations were preserved. MA imported the player and exported
its queue entity to HA.

Only the second Dot's voice origin and music target were changed. Existing
live automation actions, Plex selection and other room bindings were retained;
private canonical bindings were reconciled with the live configuration. At
this checkpoint the existing dynamic Lovelace list was expected to expose
the new player, and no explicit card was added. The operator later reported
that the card was missing; the explicit dashboard correction is recorded below.

The first attended music request received a voice acknowledgment but no
music playback. Investigation found that Music Assistant's shared
`streams.publish_ip` still advertised an old host address unreachable from
the EchoMuse controller. The actual host-networked Music Assistant node was
reachable.

After private configuration and queue backups and an idle-player check, only
the supported `streams.publish_ip` setting was corrected to the current host
address. The exact previous queue flow then returned HTTP 200 with
`audio/wav` from the controller environment. FFmpeg decoded one second into
96,000 PCM bytes, including 44,346 nonzero samples, and exited successfully
with no diagnostic output. This check did not start speaker playback.

At this stage only stream retrieval and decoding had been verified. A later
direct playback and stop check is recorded below. An attended repeat of
**«играй музыку»** and confirmation of what the physical speaker sounds like
are separate acceptance checks; neither follows from stream decoding alone.

## Maintenance cleanup

The temporary USB ADB container and its selected-device proxy were stopped
and removed after migration. Recovery images and private receipts remain on
both hosts. The Dot stayed connected to the controller and Home Assistant
over WSS, with local wake detection and microphone streaming disabled. The
maintenance host now provides power only; normal operation uses Wi-Fi.

## Later Home Assistant availability incident

Three subsequent music turns correctly recognized **«играй музыку»** but
ended with `tts_error`. HA's HTTP listener was unavailable even from inside
its own runtime, Music Assistant services were no longer registered, and
multiple integrations reported `Session is closed`. This identified a wider
HA availability failure; the trigger for that process state was not yet
established.

After diagnostic snapshots were preserved, only the HA StatefulSet pod was
restarted. An HTTP 200 response returned in approximately 24 seconds. This
proved that the HTTP listener had recovered, but did not by itself establish
that all integration connections and voice services were ready.

The operator also observed an action-button sequence of green, orange, then
off. The matching controller log reported
`Dot button but no HA connection — standing down`. The pinned implementation
uses the `no_ha` outcome, a 0.6-second listening hold, and an orange cue for
this condition. The observation is consistent with a missing HA native API
connection while the controller can still receive the Dot's button event.

Subsequent checks confirmed HA HTTP and authenticated access, loaded ESPHome
and Music Assistant entries, both Assistant selectors still using **FCC
Russian Backup**, and a working MA queue lookup for the new player. The Dot
reported WSS and HA connected, with local wake detection and continuous
microphone streaming disabled.

## Bounded post-recovery music check

A direct MA test targeted only the second Dot for 18 seconds. The native and
MA player states changed to `playing` and then `idle`; 514 PCM periods were
sent, and the first device audio frame followed the request by 3.157 seconds.
The stop was acknowledged and queue item order was unchanged. These results
verify transport and control behavior, not the operator's audible experience
or a fresh voice-to-music request.

The decoder reported six read stalls, with a maximum of 3.154 seconds,
including startup. Playback buffering may absorb such stalls, so these
counters alone do not establish audible interruptions. Sound quality had not
yet been confirmed at this checkpoint; a later listening report is recorded below.

During playback, a wake event scored 0.484 against the lower 0.25 interruption
threshold and ended with `no_speech` after 5.207 seconds. Whether the operator
intentionally spoke at that moment is unknown; the event remains unclassified.
It is not evidence by itself of a false wake activation.

An attended voice-to-music repeat and confirmation of audible playback,
quality, and stopping remain pending at this checkpoint.

## Native music vocabulary correction

A subsequent inspected HA turn transcribed the request as **«Играем музыку»**.
It carried the correct pilot device and satellite identities, with local
handling preferred, but was marked `processed_locally: false`. The FCC
conversation agent then asked which device to use. The native sentence
grammar accepted **«играй музыку»** but omitted the observed **«играем»**
variant, so the native handler had not received the request.

Only the six existing play-sentence patterns were amended to accept this
variant. The live automation was reloaded and remained enabled. Its actions,
guards, scripts, providers, pipelines, and device-to-player mappings were
unchanged. Tests using the installed Hassil parser routed the observed
phrase to the second Dot's native origin handler and preserved explicit-target
recognition without executing media services.

The [canonical generator fix and regression cases](https://github.com/ha-homelab/ha-echo-show-5/pull/51)
track the source correction separately. The isolated HA runtime suite passed
all 16 tests without skips, including the new origin and explicit-target cases.

## Attended voice-to-music confirmation

After these corrections, the operator repeated the action-button request
**«Играй музыку»** and confirmed that music played on the second Dot without
a device-selection question. This confirms one successful attended spoken
request through to audible playback on the intended device.

The earlier direct stop test remains a transport/control check; an attended
spoken stop and reliable wake detection during music still need evaluation.

## October 13, 2026 — audible buffering and dashboard correction

After the successful spoken music request, the operator explicitly reported
audible hiccups and buffering. Sustained playback quality is therefore a known
open issue, not simply an unperformed acceptance check.

A later trace showed 9.141 seconds of upstream decoder starvation, exceeding
the approximately 5.46 seconds of audio held by the Dot's fixed playback
buffer. Wi-Fi checks were healthy during the inspection. Investigation is
focused on delivery through Music Assistant and Plex. This evidence did not
by itself identify the responsible component or establish a fix. It also does
not retroactively classify every earlier decoder stall as an audible interruption.

The operator also reported that the new player was missing from the existing
Lovelace media view. An explicit `custom:mini-media-player` card named
**EchoMuse Dot 002** was inserted first in the first grid of the existing
`/lovelace/media` view, using the new Music Assistant queue entity. A private
before/after comparison and live readback verified that this was the only
dashboard change. No playback services were called while adding the card.
The earlier assumption that the dynamic list was sufficient is superseded
by this explicit card; existing dynamic cards and their filters were retained.

## Pilot queue normalization mitigation

Investigation found dynamic loudness normalization in the source-processing
chain and high CPU pressure on the Music Assistant host. Processing starvation
was suspected; the evidence did not isolate one component as the sole cause.

Only the pilot queue's `volume_normalization` was changed from `global` to
`disabled`, through the supported Music Assistant `config/player_queues/save`
API. The save resumed the same current track. The 25-item queue's order and
hash were preserved, and comparison confirmed that other queue settings,
global configuration, and player configuration were unchanged. Setting this
queue back to `global` restores its inherited normalization policy; it does
not require changing the global setting. The saved queue setting persists;
with normalization disabled, tracks may differ in playback loudness.

The preceding stream had logged 155 source-stall warnings, with a maximum of
9.141 seconds. In one 30-second pre-change window, audio advanced only about
17 seconds. The replacement stream had an initial 3.042-second startup wait
and one 745 ms wait, followed by approximately 53 seconds with no further
starvation warnings. No duck events occurred in that observation window.
An independent 20.44-second WebSocket observation acknowledged approximately
99,243 bytes/second, consistent with 96,000 PCM bytes/second plus overhead.
A later passive snapshot recorded another 3.488-second source stall after
the clean interval, without a disconnect, reconnect, or stop. The change
therefore did not eliminate all source stalls.

These results show an improvement in bounded source delivery, not proof of
zero speaker underruns or sustained audible quality. Music remained playing
at the checkpoint. The operator subsequently confirmed smooth music playback
after the mitigation. This is a successful attended listening result for the
trial; it does not erase the later recorded source stall or establish
long-term playback reliability.

## Maximum-volume inspection

The operator subsequently reported that maximum volume seemed lower than
stock Alexa. Read-only checks found the native HA player, MA-exported player,
MA player, and controller all at 100%, unmuted, with no additional MA volume
cap. The EQ remained Flat and the bass guard and peak limiter remained enabled.
No volume, EQ, or hardware gain setting was changed during this inspection.

The pinned implementation maps 100% to device level 127 at unity gain; forcing
the raw control higher is not a clean amplification path. Stock processing
and the supported but untested Music EQ alternative are explained in the
[controller guide](controller.md#maximum-volume-and-stock-alexa-comparisons).
No controlled stock-versus-EchoMuse loudness measurement was performed.

The operator subsequently accepted the current pilot setup and authorized
publication of the findings. Flat EQ and volume limits remain unchanged;
the playback and far-field test limitations recorded above still apply.

## October 14, 2026 — first Dot migration

The operator connected the first, still-EchoLocal Dot to the maintenance host
and authorized its conversion. A new isolated USB session matched its serial
and Wi-Fi identity before any device write. Live inspection confirmed the
expected Fire OS 6 / Android 7.1.2 / SDK 25, EchoLocal 0.0.8, active slot A,
amonet2 and TWRP 3.7 environment.

Fresh full copies of both boot partitions, recovery, boot-control metadata and
the EchoLocal/Wi-Fi runtime archive passed independent second reads. All five
files were then copied to the Mac and checked against the same hashes. The
new emOS image used this first Dot's own boot backup and dynamically verified
donor system partition. It did not reuse the completed pilot's prepared image
or credentials.

Thirteen firmware, startup, wake and connection files were staged with verified
hashes and permissions; the Wi-Fi configuration remained unchanged. Only
`boot_a` was written. Its full uncached readback matched the new image plus
the preserved partition remainder; the alternate boot partition, recovery and
boot-control bytes remained unchanged. A separate reboot guard rechecked the
boot contents and retained partitions before starting emOS.

USB console inspection confirmed **emOS v0.10**, **EchoMuse v2.18.0**, a running
server and Wi-Fi connectivity. The v0.10 payload reports USB product **emOS**;
the source also contains **emOS console**, so the product string alone must not
override the exact serial, physical USB mapping and verified image. The device
reached the intended controller over WSS and waited for approval. Its separate
credentials and recovery files remain private.

After authenticated first contact, only the new first unit was approved. Its
initial live connection arrived before complete version telemetry; the check
waited for TLS and both expected versions without issuing another approval or
rotating credentials. A distinct ESPHome entry was enrolled in HA. Both
Assistant selectors use **FCC Russian Local Voice**; the primary wake word is
**Hey Jarvis** and the secondary wake word is disabled.

The new native player was appended to Music Assistant's existing selected-player
list. That provider reload exposed a disconnected HA client and temporarily
removed the MA exports. A scoped reload of the HA connection provider and then
`hass_players` restored both Dots without restarting MA or changing credentials,
stream addresses or configured player selections. Only the new first queue's
normalization was disabled to match the second queue.

The first unit's originating-device music routes now target its new MA player.
The private canonical bindings reproduce the live scripts. An **EchoMuse Dot
001** card was added beside the existing **EchoMuse Dot 002** card in Lovelace's
media view. Existing HA entries, pipelines, second-unit routes and its card were
preserved; the original first EchoLocal entry remains available for rollback.

Final read-only checks confirmed both units connected through TLS and HA,
matching firmware/emOS versions, local wake listening without continuous
microphone streaming, matching Assistant/wake selectors, and **57 matching
effective settings**. Persisted device volume is intentionally independent.
No music playback, microphone recording or attended acoustic test was performed
during this first-unit migration. Its button, wake and audible playback checks
remain separate acceptance work.


## October 14, 2026 — local household assistant

Both EchoMuse units now use **Local Russian Home** on both Assistant selectors.
The local Ollama service provides household reasoning, guarded device commands
and Recorder statistics; local Piper provides Russian speech. The existing
cloud recognition provider is retained. The earlier FCC assignments above are
migration checkpoints, not the final active configuration.

See the [local-home deployment record](home-control.md#deployed-local-home-assistant--october-14-2026)
for the verified control/read separation, real lamp restoration, generated
audio for both device contexts, CPU latency limits and remaining attended tests.

The first attended local-home test failed on both devices despite correct
transcription of the heater power question. Controller traces identified its
30-second response deadline cancelling the still-running local model. The
correction registers a native read-only state intent and changes the shared
controller's supported response timeout to 120 seconds. See the same record for
verification and remaining performance limits; the earlier text API checks did
not establish full voice-path success.
