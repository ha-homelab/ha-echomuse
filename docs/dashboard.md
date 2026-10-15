# EchoMuse controls in the existing Media dashboard

EchoLocal's `custom:echolocal-satellite-card` does not manage an EchoMuse
satellite. After migration, replace those cards rather than changing their
device IDs. The historical EchoLocal entities may remain in the registry for
rollback, but they are not the new player or voice satellite.

## Choose the current entities

For each physical Dot, inspect **Settings → Devices & services → ESPHome** and
the corresponding Music Assistant player:

- Use the **Music Assistant media player** for music transport, queue and volume
  controls. Check its registry platform is `music_assistant` and its unique ID
  refers to that Dot's current native ESPHome player.
- Use the **current ESPHome assist satellite** for voice status.
- Use the current device's **Microphone Muted** binary sensor, **Assistant**
  selector and **Wake word** selector. Omit **Wake word 2** for the current
  controller: it supports only one active wake model.

Do not infer the player solely from its display name or a suffix such as `_2`.
In this deployment `_2` distinguishes the MA wrapper from the native player,
but another installation can allocate different entity IDs. Old Alexa Media
Player and EchoLocal entities are not substitutes for the new MA wrapper.

## Update the existing view

1. Export the current Lovelace configuration to private backup storage.
2. Open the existing **Media** view. Locate both obsolete EchoLocal cards and
   any duplicate music cards for the migrated units.
3. Build one EchoMuse section containing a player and voice controls for each
   Dot. The [single-Dot card example](../examples/lovelace/echomuse-dot.yaml)
   can be copied once per device after replacing every placeholder. It uses
   the Mini Media Player custom card already installed in this deployment.
4. Add an optional link to the private controller dashboard for diagnostics
   and the root Console. Keep the real address out of public examples.
5. Save, reload the dashboard and verify that every referenced entity exists.
   Confirm the MA wrapper and native player agree on playback state.

Voice status and microphone mute are readouts. Assistant and wake-word rows
change the corresponding selectors. These controls do not flash firmware or
replace HA integrations. Hidden power controls avoid implying that the music
card can switch off the physical Dot's USB power.

## Why the second wake word is empty

The deployed EchoMuse Controller 2.26.0 advertises `max_active_wake_words=1` and
only its currently configured model through the ESPHome API. HA may still expose
a second selector, but it does not enable a second simultaneous wake phrase.
The live choices were `no_wake_word` and `hey jarvis`, with the second selector
set to `no_wake_word`. The card therefore omits that unsupported control.

Change the actual model in the **EchoMuse Controller** dashboard. This version
offers **Hey Jarvis**, **Alexa**, **Hey Mycroft** and **Hey Rhasspy**, or a compatible
custom openWakeWord ONNX model. These are alternatives for the one active model.
The HA selector turns detection of that selected model on or off; it is not the
full model catalog. A custom Russian phrase requires a compatible trained model
and validation on the device. A model used by the previous EchoLocal deployment
is not automatically installed or validated by the emOS/EchoMuse migration.

## Distinguish stale cards from an offline device

An obsolete card can show unavailable while the new EchoMuse player works.
Replace its references using the registry mapping above. Conversely, when
the current native player, MA wrapper and satellite are unavailable and the
EchoMuse controller also reports disconnected, a dashboard edit cannot restore
the device's power or Wi-Fi. Keep the real unavailable state visible; stale
selector values are not proof that the Dot is connected.

## Deployment check — October 14, 2026

The existing Media view contained two current EchoMuse music cards **and** a
separate obsolete EchoLocal satellite section. Both old satellite cards were
removed, and the current players and voice controls were consolidated into one
EchoMuse section. Other dashboard cards were retained. A private before-copy
was saved, and the full configuration was read back after saving.

All twelve initial entity references existed. A follow-up check confirmed the
one-active-model limit, so both unsupported second-wake-word rows were removed,
leaving ten references without changing wake settings. Dot 2's native and MA players reported
playing, its voice satellite was idle, and its microphone was unmuted. Dot 1
was disconnected in both HA and the controller; the operator could not power
it on for this check. Its new card is configured but physical reconnection
remains unverified. The browser required a fresh HA login, so this update's
verification was configuration/API based rather than a rendered UI check.
