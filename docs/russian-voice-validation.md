# Russian voice rollout: 2026-10-14

This record distinguishes service verification from physical listening tests.
Use the [operations runbook](russian-voice-operations.md) for installation and
rollback and the [energy guide](energy-assist.md) for supported questions.

The later [local household-assistant rollout](home-control.md#deployed-local-home-assistant--october-14-2026)
now supplies the conversation agent on both Dots. The FCC results below document
the earlier general-question route, which remains available separately.

## Russian speech

The selected voice is **Piper Denis medium**, served through the new Wyoming
integration. HA exposes `tts.local_russian_speech`; the initial pilot pipeline was named
**FCC Russian Local Voice**. “Local Voice” refers to speech synthesis: general
conversation and the existing speech recognition still use their configured
external providers.

The deployed speech image is pinned to
`sha256:b12f823404f2316a16e3c5665e1d210d8b48823d3069554d84fe6594426e2693`.
The running application's 15 source-file hashes matched the reviewed source.
The existing English Nano service was not replaced.

The initial large VM was unsuitable under its observed load. Direct HTTPS
synthesis worked, but even a clean short Wyoming request exceeded the unchanged
30-second deadline. An owned diagnostic process left after a client timeout was
removed; repeating without it still failed. Moving only the new deployment to
the lightly loaded x86 NUC resolved that test without changing the image,
credentials, service address, deadline or CPU limits.

On the NUC, private-CA HTTPS verification and two simultaneous Wyoming syntheses
passed. The requests completed in **4.10 and 6.78 seconds**, each producing about
5.25 seconds of audio. Idle memory was about 201 MiB for TTS and 19 MiB for the
adapter. These are service measurements, not microphone-to-answer latency or
long-term reliability results.

HA integration then generated and served a separate 4.76-second Russian clip.
The proxy returned **MP3, 24 kHz, mono**, verified by downloading the audio and checking its
codec, sample rate, channels and duration with ffprobe. HA can convert the
original WAV; callers must inspect the returned format. A returned URL alone
was not counted as successful audio generation.

## FCC reliability and conversation

The running bridge is **0.1.4** and cloud speech adapter **0.1.2**. The obsolete
runtime code overlay was removed so the image provides the running application.
Two concurrent synthetic ASR requests completed in 2.404 and 2.535 seconds. Two
concurrent cloud TTS requests completed in 4.206 and 4.055 seconds with complete
PCM responses. The configured pools are two ASR and two TTS operations.

The selected model is the explicit
`claude-3-freecc-no-thinking/open_router/nvidia/nemotron-3-ultra-550b-a55b:free`
route for general questions without personal or confidential data. IGW context
is disabled in the bridge. Local energy intents provide energy reports; the
external model is not used to calculate or narrate the household snapshot.
The text bridge still has one active model-request slot.

Four requests through HA's actual conversation API passed: seven plus five
returned twelve (3.513 seconds), the ice-density explanation was correct Russian
(1.629 seconds), one kilowatt was correctly converted to 1,000 watts
(2.350 seconds), and a request for missing household history returned the fixed
unavailable response (0.110 seconds). These are text-only timings, excluding
speech recognition and synthesis. The route and empty fallback list were
verified; the FCC response echoes the configured model alias and does not
independently identify the provider's backend weights.

## Local energy reports

IGW 0.4.2 was deployed with image digest
`sha256:0e80459ede1a35940a77913e574a075e21b86e093ab432eed8c65584219f5f42`.
The change replaced only the existing deployment's image. An isolated canary
passed before promotion; the same checks then passed against the new primary:
authentication, invalid and duplicate locale rejection, trusted HTTPS with
hostname verification, English/Russian response headers, equal typed telemetry,
six fresh metrics and connected MQTT. The old image and private rollback
snapshot remain available. The new primary was ready with zero restarts at
acceptance; this is not a long-term uptime measurement.

The two generated HA files and separate secret references were installed after
a private configuration backup. HA configuration validation and all four
integration reloads passed without restarting HA. All six energy questions
returned local `action_done` responses in both originating device contexts:
**12 successful intent requests**. Two simultaneous intent-to-TTS requests also
returned downloadable audio in **4.116 seconds each**. They explicitly selected
the new local-voice pipeline; they did not change a device's Assistant selector
or play audio on either Dot. These timings exclude wake detection, microphone
capture, speech recognition and physical playback.

After the first unit's migration, the checks were repeated using both actual
EchoMuse device contexts. All **12 local intent responses** passed again and
both generated audio responses were fetched successfully in **5.609 seconds
each**. This confirms the updated HA origins and service path, not audible
playback from the physical speakers.

## Acceptance still to complete

After migration, both Dots used **FCC Russian Local Voice** on both Assistant
selectors; the later local-home rollout replaced that assignment. The
operator initially postponed the new listening test, then connected the first
unit for migration. Its emOS/EchoMuse conversion and distinct HA enrollment
completed with its own verified recovery backups; the old EchoLocal entries
remain available for rollback.

The new Russian voice and the newly migrated first Dot still need attended
button, wake and music checks. Service readiness alone does not establish
physical success. See the [deployment record](deployment-record.md#october-14-2026--first-dot-migration)
and [repeat migration procedure](migration.md#9-migrate-another-existing-echolocal-unit).

## Local-home voice deadline correction

The first attended test of Local Russian Home failed on both Dots. Their heater
power questions were transcribed correctly, but the controller's 30-second
response wait cancelled the model before speech was generated. An earlier
greeting followed an unrelated `uh` transcript. These observations supersede any
inference that the successful text and generated-audio tests proved complete
voice-path operation.

The controller now permits the upstream-supported 120-second wait. Common state
questions use a native read-only intent, avoiding slow model/tool round trips.
The corrected power query completed its intent stage in approximately half a
second for each device context; two simultaneous generated audio responses were
fetched in 4.7 seconds. This is still a service test, with renewed attended
microphone/playback verification requested. Details and limits are in the
[local-home record](home-control.md#deployed-local-home-assistant--october-14-2026).
