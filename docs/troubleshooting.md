# Troubleshooting by failed stage

Record the physical Dot, approximate time, exact spoken phrase, distance, room
noise and first visible failure. Keep the identifying details and transcripts
private. Read logs before restarting anything; ring colors alone do not locate
a fault, and customized ring scenes may change their appearance.

## The controller cannot see the Dot

Check power stability and cable fit, the Wi-Fi lease and the controller's device
connection. A saved configuration or old HA entity is not evidence that the
device is online. If the device has no network access, the
[USB serial recovery path](device-access.md#usb-console-and-recovery) is the next
diagnostic channel; emOS does not answer old `adb shell` commands. Do not flash
again merely because ADB disappeared after a successful emOS boot.

## The button lights briefly, then gives an error cue

A connected Dot can still lack an HA voice connection. Check the current
ESPHome **voice** integration and its allocated controller port. The separate
BLE proxy being healthy does not prove voice availability. The pinned controller
can log `Dot button but no HA connection — standing down` in this case.

If both native and MA players are available but `assist_satellite` is unavailable,
inspect the voice entry, pipeline and turn logs specifically. Do not present
music or BLE health as evidence that the satellite is healthy. See the
[controller incident guide](controller.md#diagnose-a-button-that-briefly-lights-and-stops).

## It wakes without speech, or misses the wake phrase

First check which model is actually active. Both pilot Dots now select the new
openWakeWord [«Привет, Мышка» model](russian-wake-word.md); Hey Jarvis is their
earlier stock baseline. The old EchoLocal TFLite file is not compatible with
this detector. The second HA wake selector does not add
a simultaneous model in Controller 2.26.0. Then separate quiet-room, TV, music
and normal-voice trials. Record intended wake attempts and false activations
with test duration; do not call an unlabelled wake event a false positive.

Keep acoustic echo cancellation enabled. Check normal and playback thresholds
separately; playback uses its own barge-in threshold. Raising or lowering them
trades misses against false triggers and cannot repair a wrong or poor model.
Use the action button to test the rest of the pipeline independently. Do not
collect unattended household audio to tune a custom model.

## It hears the question but spins and stays silent

Inspect the Assist trace: did recognition finish, did the native intent match,
did the model finish, and was a real audio payload fetched? FCC quota or provider
failures remain possible while recognition uses the cloud. Switching the
conversation agent to local does not replace the recognition stage.

The local CPU model exceeded the original controller wait in recorded tests.
The documented configuration uses the supported `EM_TTS_WAIT_TIMEOUT=120`.
Increasing a diagnostic API timeout alone does not change that device-facing
limit, and increasing either does not make inference faster. Native state and
music intents bypass slow model turns. See [home-control limits](home-control.md)
and the [streaming measurements](architecture.md#measured-streaming-behavior).

## The answer has the wrong voice or stops partway through

Check both Assistant selectors, the selected HA pipeline and Wyoming's
advertised voice. The current Russian voice is `piper-ru-irina`; Denis is the
earlier baseline. Reload the Wyoming entry after a speech-service capability
change. Verify actual audio bytes, format and duration instead of only the
existence of a TTS URL. For early speech, the conversation agent, TTS adapter
and controller all need streaming support. Test interruption separately from
an unexpected playback truncation.

## It cannot find a room or turns off the wrong kind of device

Inspect the entity's HA area, friendly name and aliases, then the reviewed
control list. A kitchen lamp connected through a switch still needs an explicit
lighting mapping; assigning all kitchen outlets to “lights” risks switching
appliances. Test discovery and read-only state first. Retain confirmation and
target guards rather than asking the language model to guess a device. The
[home-control guide](home-control.md) describes the recorded kitchen correction.

## Music is acknowledged but silent, buffering or will not stop

Check origin-based native routing and the current MA queue target. Then verify
the actual queue stream from the controller's network context and the underlying
Plex source file. An available catalog item can still return HTTP 404.

The documented repairs corrected stream addressing, added supported native
phrases, adjusted only the affected queue's normalization and removed an
unavailable source. They do not justify a blanket buffer increase. Short
**stop / стоп** commands now route to the originating music queue; the wake
phrase and command are separate steps. Follow the full
[music troubleshooting runbook](music-troubleshooting.md) and verify by ear.

## Home Assistant reports expired Bluetooth proxy authentication

The Noise key has no scheduled expiry. Check the exact BLE entry, controller
endpoint and proxy identity, then confirm its saved key. The unpatched 2.26.0
controller can change that endpoint to plaintext when active Connections is
disabled or unavailable; HA may stop reconnecting and retain a repair even
after encryption returns. Do not toggle Connections to refresh slots, rotate
keys speculatively, or replace a current entry with a duplicate. Use the
[same-entry authentication recovery procedure](bluetooth-proxy.md#authentication-expired-in-home-assistant)
and verify subscription plus fresh forwarded advertisements afterward.

## Several Bluetooth entries look like the same speaker

Inspect their integration, endpoint and active scanner identity. An old EchoLocal
Bluetooth record, the new EchoMuse proxy and a consumer such as iBeacon Tracker
are different objects. A repeated display name inside one card is not an extra
radio. After private backup and reference checks, remove truly obsolete
EchoLocal entries through HA; keep the current voice and BLE entries.

After migrating a Dot away from EchoMuse, its disabled controller proxy can
also remain visible. Retire that Dot's old controller identity before removing
its HA records, because approved offline devices still advertise discovery.
Follow the [migration cleanup procedure](bluetooth-proxy.md#retire-an-echomuse-identity-after-migrating-a-dot),
including its backup and hard-delete side effects. Keep proxies belonging to
other physical Dots.

No new iBeacon entities does not by itself indicate proxy failure. Verify fresh
advertisements first, then the consumer's supported beacon format and discovery
rules. Read [Bluetooth and iBeacon diagnostics](bluetooth-proxy.md).

## Recover with the smallest effective change

Save the failed-stage evidence and existing settings. Reload only the affected
integration or service when the evidence warrants it. Verify the other Dot after
any shared controller, HA, speech or music-provider change. Restore a saved
setting or pinned service image before considering firmware recovery.

Public issue reports should contain versions, sanitized error names, reproduction
steps and the distinction between API success and audible results. Exclude raw
logs, URLs with credentials, device inventories, tokens and household recordings.
