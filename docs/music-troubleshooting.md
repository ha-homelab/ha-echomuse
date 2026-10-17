# Diagnose music interruptions

Treat command routing, source availability, audio delivery and device connectivity
as separate checks. A spoken confirmation or a `playing` entity state does not
prove that the speaker is receiving continuous audio.

## Establish where playback stops

1. Check the Assist trace. A supported music command should be handled by the
   native household route and target the originating Dot's Music Assistant
   player. See the [native-command correction](deployment-record.md#october-14-2026--music-request-falling-through-to-the-model).
2. Compare the current native ESPHome player, its MA wrapper and the controller's
   connected state. Use the [current dashboard entities](dashboard.md), not the
   retired EchoLocal entries.
3. Inspect controller logs for `Media SOURCE stall`, send failures and connection
   timeouts. A source-stall entry means the decoder did not supply audio in time;
   it does not identify whether Plex, MA, transport or decoding caused that delay.
   A WebSocket keepalive timeout is a separate device-link failure.
4. Check MA logs around the same timestamp and track boundary. Preserve the queue
   and player configuration privately before changing them.
5. Verify the actual source file. Plex metadata and MA's `available` flag can both
   be present while a Plex file request returns HTTP 404. A small authenticated
   HTTP Range request to each selected media part distinguishes a missing file
   from a valid catalog entry. Keep source URLs, authentication and media names
   private. An initial Range success does not validate the entire track.

## A short stop command asks what to stop

The observed utterance was transcribed correctly as `stop`, but the original
native grammar required `stop music`. The unmatched short command reached the
conversation model, which asked whether to stop a light or heater. This was
command routing, not a misheard wake phrase.

The [native voice package](https://github.com/ha-homelab/ha-echo-show-5/pull/59)
now handles `stop`, `стоп`, `stop music` and `останови музыку` locally. It stops
only the originating satellite's registered Music Assistant player; an explicit
registered target can override the origin. `pause` and `пауза` remain separate
pause commands. No household-control service is inferred from a bare stop.
Unknown origins request a target without acting. Unavailable players report
unavailability, and already-idle players produce an already-stopped reply.

Keep **Prefer handling commands locally** enabled on the pipeline. Reload
scripts and conversation-trigger automations after installing the package.
For a normal voice check on the pilot Dots, say **«Привет, Мышка»**, wait for its
wake cue, then say **stop** or **стоп**. This [Russian-model trial](russian-wake-word.md)
replaced Hey Jarvis on October 16; its music-interruption test is still pending.
The repaired route also works within an existing conversation; another wake
word is not required while the assistant is already listening.

On October 14, replaying the recognized `stop` in the affected conversation was
handled locally in 0.352 seconds. Both current Dot 2 player entities changed
from playing to idle. A subsequent `стоп` returned an already-stopped response
in 0.026 seconds. The test left music stopped and excluded microphone recognition
and spoken-answer latency. The first Dot remained offline; its HA routing was
updated, but its physical test awaits reconnection. Wake thresholds and firmware
were unchanged.

## Repair a missing source without changing the library

Remove a confirmed missing track from the private native-command seed list and
the affected playback queue. Do not delete library entries or files just to
repair a queue. Preserve the remaining order and back up both configurations.
Update the canonical private bindings as well as the live HA package so a later
render does not reintroduce the broken item. Validate HA configuration and reload
only scripts when only their media lists changed.

MA 2.10.2 ignores deletion of an item at or before the already-buffered position;
the command can return successfully without removing it. Always read the queue
back. If a rebuild is needed, save the current item and position, stop the affected
queue, clear it, add the filtered list without starting playback, verify its order,
then resume the saved valid item at its position. This causes a brief intentional
interruption. Back up shuffle/repeat settings and account for them before rebuilding;
the observed queue was not shuffled.

## Avoid unmeasured buffering changes

Normalization was already disabled on the affected Dot. The observed MA `minimal`
buffer preset represented 60 seconds, not an unbuffered stream. Increasing global
memory limits or buffers without identifying the failing stage is not a verified
repair. Check resource pressure, source response times and device-link health first.

After each change, observe complete tracks and transitions, compare logs and obtain
an audible check. Keep server-side delivery evidence separate from the operator's
listening result. An offline Dot requires a later physical check even when its
dashboard references and command bindings are correct.

## Deployment observation — October 14, 2026

The second Dot's 25-item default queue contained one track whose metadata returned
HTTP 200 but whose file returned HTTP 404. MA still marked it available and logged
failed retrievals. Small Range requests succeeded for the other 24 sources; all
25 probes completed individually in under 0.2 seconds during this test.

The missing source was excluded from the canonical private seed and all three
generated endpoint scripts. HA configuration validation passed. The second Dot's
queue was rebuilt with the remaining 24 items in the same order and resumed at
the saved item and position. No Plex files or library records were deleted.

Earlier controller logs also contained source stalls up to 7.5 seconds and one
device-link keepalive timeout followed by reconnection. Removing the missing file
addresses a confirmed source failure; it does not by itself explain every audible
interruption or establish long-term playback reliability.

After the queue repair, the operator confirmed that music played smoothly on
the second Dot. The first Dot was disconnected and could not be powered on for
this check, so this is not listening acceptance for both devices.

Seven subsequent samples over 150 seconds kept the second player available and
playing, including an automatic track transition. The controller log since the
restart contained a 2.7-second initial decode wait and one 664 ms source read
stall, with no new device-link timeouts or send failures. No new Plex 404 was
logged in that interval. These bounded observations support the attended result
without claiming uninterrupted playback under all conditions.
