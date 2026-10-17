# Early speech, interruption, wake feedback, announcements and timers

These instructions apply to EchoMuse Controller 2.26.0 and device firmware
2.18.0. They do not require another firmware flash or a USB connection. The
controller and Home Assistant must be reachable while the Dot has normal power.

## Configure each Dot

In the EchoMuse Controller, open the device's configuration and enable:

- **Stream reply** (`streamReply`) in playback settings.
- **Barge-in** (`bargeInEnabled`) in wake-word settings.
- **Wake sound** (`wakeSound`), with `wakeSoundLevel: medium` initially.

Save and read back each device's effective configuration. Per-device overrides
are scoped by section: retain unrelated values when saving an override. An
offline device can have saved settings without having received them yet.

Barge-in listens for the configured wake phrase while speech is playing. Both
pilot Dots now use **«Привет, Мышка»**: say the phrase, wait for wake feedback,
then give the next request. Arbitrary background speech is not a stop command.
The current [Russian-model trial](russian-wake-word.md) uses **0.5** for both
normal and playback thresholds; the earlier stock model used 0.25 for playback.
Do not carry a previous model's threshold into a new model without validation,
or lower it merely to make interruption easier after false activations. Keep
acoustic echo cancellation enabled so the device does not wake on its own
speech. The new model's room-distance and music tests are still pending. Verify
interruption by ear with a long answer before judging range.

The wake cue is a short two-tone confirmation of a detected wake word. It does
not mean recognition, a home-control action, or a generated answer succeeded.

## Make early speech work through Home Assistant

A device switch alone is insufficient. All three parts must support streaming:

1. The selected conversation agent must produce streamed text. The deployed
   **Local Russian Home** Ollama agent supports it.
2. The selected TTS integration must advertise streamed synthesis. The local
   Russian Wyoming adapter supports this starting with version **0.2.0**. It
   renders complete sentences while more text arrives, keeping **Irina** as
   the selected voice. See the [speech service runbook](https://github.com/4alvit/google-home-voice-stats/blob/feat/russian-tts2-pilot/docs/russian-speech.md).
3. EchoMuse must have **Stream reply** enabled and be able to fetch HA's TTS URL.

After updating the TTS server, reload **Local Russian Speech** under
**Settings → Devices & services → Wyoming Protocol**. In
**Settings → Voice assistants**, retain the local conversation agent, Russian
language, local TTS entity and `piper-ru-irina` voice. Prefer handling commands
locally remains enabled. Household data is not sent to an external model as a
fallback.

Early speech begins after a complete sentence is available and synthesized.
It cannot remove the model's delay before its first sentence. A short answer
may finish generating before audio begins. Sentence boundaries and synthesis
speed can also produce gaps; streaming is not a guarantee of gapless narration.

## Announcements

The existing ESPHome voice integration exposes `assist_satellite.announce`.
There is no additional EchoMuse announcement toggle to install. In HA's
**Developer tools → Actions**, use the current EchoMuse Assist satellite, not
an obsolete EchoLocal entity:

```yaml
action: assist_satellite.announce
target:
  entity_id: assist_satellite.REPLACE_WITH_CURRENT_ECHOMUSE_SATELLITE
data:
  message: "Проверка объявления."
  preannounce: true
```

Use the same action in an automation for a particular household event. Select
both current satellite entities when a message should play in both rooms.
Announcements use the satellite's selected TTS pipeline. An offline target
cannot play a message; an action's mere existence does not prove playback.
`assist_satellite.start_conversation` and `ask_question` are separate supported
actions when an announcement should be followed by listening.

## Timers

Timer support is already advertised by this controller. HA owns the countdown
and sends events to the originating satellite over the ESPHome voice connection.
No separate `timer` helper, Alexa account, cloud timer service or new integration
is required. Keep local intent handling enabled.

Working Russian forms include:

- «Поставь таймер на пять минут».
- «Поставь таймер проверка на пять минут».
- «Сколько осталось на таймере проверка».
- «Отмени таймер проверка».

Put the timer name before its duration. The tested longer construction ending
in «с именем проверка» did not match the timer-start intent. When testing through
an API, provide the current satellite's HA device context; a context-free text
chat does not identify which speaker should ring.

When a timer expires, EchoMuse plays its bundled timer sound and pulses amber.
Tap the action button to dismiss it, or say the wake phrase and then speak.
An already-ringing timer is dismissed locally because HA has removed the
finished countdown. Controller 2.26.0 caps an unanswered alarm at 15 minutes.
This is a network-dependent Assist timer, not a standalone offline alarm clock.

## Verification and rollback

Test short local commands, a long generated answer, interruption, a short timer,
and an announcement on each physically available Dot. Confirm music resumes
correctly after an announcement. Separate API/configuration checks from listening
tests; saved settings on an offline Dot are not a successful physical test.

Turn off **Stream reply** to restore complete-answer playback. Turn off the wake
sound independently if unwanted. Restore the saved per-device configuration to
undo all three settings. Reverting TTS code additionally requires reloading the
Wyoming integration so HA refreshes its advertised capabilities.

## Deployment checks — October 14, 2026

Both Dots have `streamReply`, `bargeInEnabled`, and `wakeSound` enabled in
persisted configuration. Wake sound level is medium; acoustic echo cancellation
is enabled. Dot 2 received the configuration live. Dot 1 was offline, so its
application and acoustic checks are pending reconnection.

The updated local TTS adapter passed 23 targeted tests. A separate test instance
using the real Irina model served two concurrent streaming requests: first PCM
arrived after 2.22 and 4.74 seconds, before the test sent either final sentence.
The deployed application files matched the built source snapshot, and HA's
Wyoming integration was reloaded with streaming advertised. These figures are
service timings, not microphone-to-speaker latency.

A Russian named timer was created, queried and cancelled in Dot 2's device
context. The controller logged both the start and cancellation, with zero
remaining active test timers. No unattended expiring alarm was left behind.

An HA `assist_satellite.announce` action with a preannouncement tone completed
on Dot 2 in 7.63 seconds, and the satellite returned to idle. This confirms the
protocol's playback-completion acknowledgement; the operator did not provide a
listening confirmation in this check. Acoustic wake feedback, interruption and
an expiring timer still require an attended check.

A real HA run using the local conversation agent advertised streaming and
delivered its first MP3 audio payload after 20.275 seconds; `intent-end` arrived
after 53.753 seconds. The response was six Russian sentences. The complete
stream was fetched successfully. This proves server-side overlap, not an
attended acoustic test; the initial model delay remains. Following the
announcement test, both the native Dot 2 player and its Music Assistant wrapper
were playing.
