# Russian voice rollout: 2026-10-14

This record distinguishes service verification from physical listening tests.
Use the [operations runbook](russian-voice-operations.md) for installation and
rollback and the [energy guide](energy-assist.md) for supported questions.

## Russian speech

The selected voice is **Piper Denis medium**, served through the new Wyoming
integration. HA exposes `tts.local_russian_speech`; the pilot pipeline is named
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

## Acceptance still to complete

At this point in the rollout, the second Dot's two Assistant selectors use the
new voice pipeline. The operator explicitly postponed the new listening test
and requested migration of the first Dot to the same EchoMuse system. That
migration is prepared but has not started because physical USB access is not
currently available; the first unit retains EchoLocal and its previous pipeline.

Physical listening, the first Dot's migration and pipeline assignment, and live
Russian IGW activation remain outstanding. Service readiness alone does not
establish physical success. The first-unit procedure and exact stopping point
are recorded in the [migration runbook](migration.md#9-migrate-another-existing-echolocal-unit).
