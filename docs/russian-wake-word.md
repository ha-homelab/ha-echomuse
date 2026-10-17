# Russian wake phrase: «Привет, Мышка»

The requested target is **one active phrase, «Привет, Мышка»**, replacing Hey
Jarvis on both EchoMuse Dots. A second simultaneous classifier is unnecessary.

## Migration and training

The October 16 investigation found Hey Jarvis selected on both devices and no
custom ONNX classifier installed. The empty second Home Assistant selector did
not provide a second detector. Earlier EchoLocal training produced microWakeWord
TFLite files; these cannot be loaded as EchoMuse openWakeWord classifiers.

The replacement workflow reuses consented, locally stored recordings while
training a new classifier against EchoMuse's frozen frontend. See the
[reproducible stages](../training/README.md). Model weights, recordings, features,
credentials and detailed device evidence remain in ignored private storage.

## Deployment contract

- Upload a new, immutable ONNX filename through the Controller's custom model
  upload, or authenticated `POST /api/oww_models/upload` with multipart field
  `model`. Read back the installed model path from `GET /api/oww_models`.
- Read each device's full config and `config_sections` before changing anything.
  Config POST uses read-modify-write; a partial body can be rejected or discard
  unrelated settings on older releases. Only override the wakeword section when
  needed, preserving other sections and values.
- Select the custom path in `owwModel`, keep local detection `owwOnDevice: on`,
  and use the validated `owwThreshold`. Set `bargeInThreshold` no lower than the
  validated threshold until separate music testing supports a different value.
- The Controller installs a missing custom classifier before activating it.
  Check `GET /api/devices/{id}/oww_assets` and the device's runtime logs; compare
  the expected and installed checksums. A saved config alone is insufficient.
- ONNX metadata carries `wake_word: Привет, Мышка` and `language: ru`. On
  metadata-aware controllers Home Assistant displays this phrase. Renaming a
  selector without training a detector never changes recognition.
- Verify both devices separately. Do not enable unattended microphone recording
  for diagnosis. Ask the owner for a short, explicit live test after installation.

Hey Jarvis may remain as an inert stock file because EchoMuse provisions a stock
asset set. That does not make it active. The selected custom model is the only
detector. Rollback uses the saved previous configuration, not a firmware reflash.

## Initial release acceptance

The following results describe the initial release. The later
[user-authorized trial](#successor--user-authorized-trial-deployment) was installed
on both Dots; its independent room-distance test remains pending. For the latest
connectivity check, see the [operational follow-up](#operational-follow-up--october-17-2026).

On October 16, 2026, both Dots received `privet_myshka_20261016_cal.onnx` and
selected **«Привет, Мышка»** in the primary Home Assistant wake selector. The
second selector remains unused. File checksums and Controller switch logs were
verified for each device. Local detection remains enabled; wake-clip recording
remains disabled. The owner confirmed on October 16 that Dot 002 recognizes
«Привет, Мышка» in a live spoken test. Audiocenter (Dot 001) has the same model
and settings and passed installation/runtime checks; its live spoken test is
deferred until the owner can access it. Do not treat those technical checks as
human acoustic confirmation for Dot 001.

The model was selected at optimizer step 11,000 of a 16,000-step run. Validation
recognized **7/8 owner positives** and **390/400 synthetic positives**, with no
events on **266 negative clips** and **1 event in 10.70 hours** of separate
speech/music/background features. One quiet owner validation recording remains
a miss; this is a documented controlled trial, not perfect recall.

After freezing the model and threshold, the separate final test recognized
**8/8 owner positives** and **391/400 synthetic positives**, with **0/266 negative
clip events**, no events in **3,601.99 seconds** of continuous held-out
LibriSpeech, and none in five 30-second synthetic silence/noise/hum controls.
These finite tests do not establish an absence of false activations in a home,
nor do Mac microphone recordings establish room-distance performance on Echo.

The selected raw score threshold was 0.999. EchoMuse clamps configured wake
thresholds to 0.975, so installing that raw model with its selected number would
silently change the detector's operating point. The deployed export subtracts
`logit(0.999)` from its final affine bias and uses **0.5** for both wake and
barge-in thresholds. This preserves the decision boundary. All **535,911**
checked validation, final-test and background windows retained the same binary
decision after calibration. The original frozen model is preserved privately.

Earlier experimental candidates were rejected and never deployed. In particular,
the first preparation heuristic could label trailing room noise as part of a
quiet owner utterance. The accepted run replaces all affected owner-positive
features with speech-end-aligned features; it does not mix the defective
features back in. Local ASR timestamps provide timing only, while participant
labels remain unchanged.

## Further owner training

The [attended Dot recorder](../training/recorder/README.md) replaces timed chat
prompts with a physical sequence: tap to prepare, wait for two blue ring flashes,
say «Привет, Мышка», tap to stop. The Mac page also provides **Record** and
**Stop & save** on one button, allowing room-distance recordings without walking
to the Dot. A new take requires a new tap or click. Audio is captured
before the ready cue and downloaded privately to the Mac. New recordings must
be inspected and split by session before training; the deployed October 16
model is not automatically replaced when recording finishes.

### First room-distance follow-up

The first follow-up used 12 newly recorded Echo training takes and eight
separate close-range validation takes. Its selected checkpoint recognized all
eight new validation phrases and seven of eight earlier owner validation
phrases. Validation also retained zero events on 266 negative clips and one
event in 10.70 hours of background features.

After that checkpoint and threshold were frozen, eight fresh phrases recorded
from the sofa, approximately three metres away, produced **4/8 detections**.
The previously deployed model detected **1/8** on the same batch. This is an
improvement, but it fails the required room-distance acceptance gate. The older
regression set also fell to 7/8 owner detections and produced one negative-clip
event. **The follow-up was rejected and was not deployed.** Both Dots retained
the initial model at that stage.

All eight room-distance recordings had continuous audio with no missing
frames. Local ASR sometimes confused the target with similar-sounding words;
those transcripts are diagnostic evidence, not replacement training labels.
For the next experiment, this now-exposed room-distance batch is promoted to
training in a new private manifest with its original split and failed-test
provenance retained. The original recordings, frozen checkpoint and failed
report remain unchanged. A new, independently recorded final session is
required before claiming the next model passed; replay of these eight training
examples cannot establish that.

### Successor — user-authorized trial deployment

The next experiment added those eight room-distance takes to training and
reclassified the previously opened Mac test as development validation, with
explicit provenance. It trains a wider, 256-unit classifier using only the two
aligned windows after each phrase ends. Earlier positive windows could precede
the final syllable; the shorter phrase «Привет, мышь» was one observed confusion.

The selected checkpoint at step 15,000 is wrapped with
[`confirm_oww.py`](../training/confirm_oww.py). It requires agreement between the
current input and a view shifted by one embedding. The shifted view repeats
the oldest embedding at the boundary: this is an approximation within the
existing model interface, **not a firmware consecutive-frame counter**. It
adds classifier computation. The deployment checks below cover initial device
operation, not long-term performance or recognition during music playback.

At raw threshold 0.98, the frozen candidate recognizes **23/24 development
owner phrases**: 8/8 new close Echo recordings and 15/16 earlier Mac recordings.
It recognizes 798/800 synthetic positives, with zero events on 532 negative
clips and three events in 10.70 hours of background features. These are
development results, not an independent final-test claim. The room-distance
training clips are not counted as held-out evidence.

Exported ONNX decisions match the reference implementation. Calibration shifts
the final logits by `logit(0.98)` and uses threshold 0.5, preserving all 536,415
checked validation/background decisions. The private release is
`privet_myshka_dab4a660248f_cal.onnx`; the hash-based filename prevents overwriting
the previous release. Its SHA-256 is
`778acee4c4d4d612da7d39020e75887fc0fb18f821dab8dba9d4279130c3da9c`.

On October 16, 2026, the owner explicitly requested installation on both Dots
before the deferred independent room test. **The release was installed and
verified on both devices as a user-authorized trial.** Each was updated
separately, with its previous configuration saved privately before the change. Installed file checksums,
Controller activation events, and active local inference were verified on both.
The runtime samples reported ready detectors with processed frames and zero
inference errors or dropped frames. These short observations are not a soak test.

At deployment readback, both primary HA selectors were **«Привет, Мышка»**, both
secondary selectors were `no_wake_word`, and wake/barge-in thresholds were **0.5**.
Local detection was enabled, microphone streaming and wake-clip capture were off, and unrelated
per-device configuration was compared with each saved backup. The earlier model
file remains installed for rollback. Restore that device's saved configuration
and recheck the primary HA selector to revert; no firmware reflash is needed.

The frozen candidate also produced zero events in 3,601.99 seconds of the
existing continuous-speech regression recording and zero in five 30-second
synthetic silence/noise/hum controls. These controls are not a measurement of
false activations in the actual room.

The owner deferred the next recording session. Eight fresh phrases from the
normal sofa position are still required for independent acoustic acceptance;
the deployment request does not turn training examples into test evidence.
Evaluate them only against the frozen candidate, verify calibrated-model
decision parity on that session, and retain a failed result rather than tuning
against it while continuing to call it independent. No new recording or attended
voice test was performed during this deployment.

### Operational follow-up — October 17, 2026

At **02:42 UTC on October 17**, Dot 001 was offline, with no reachable remote
management or USB recovery path available for inspection. Its successful
installation and local-inference checks above describe the earlier deployment;
they do not establish that the device is online now. A new runtime check on
Dot 001 requires its connection to return.

Dot 002's model was healthy in the follow-up check. Transient transport
reconnections were still under investigation; their cause had not been
established, and they must not be attributed to the model merely because they
were observed after deployment. Neither this operational check nor the earlier
installation checks replace the pending independent room-distance voice test.
