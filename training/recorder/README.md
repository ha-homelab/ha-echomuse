# Attended Echo microphone recording

This optional extension adds a bounded recording session to **EchoMuse
Controller 2.26.0**. Both the physical button and the Mac page use the same recorder state machine.
It captures the Dot's actual 16 kHz mono PCM wake stream,
not the Mac microphone and not the beam-locked speech-to-text turn stream.
The detector is temporarily put in diagnostic streaming mode only for a take.
The saved wake phrase and ordinary settings are restored after each take.

Saving and closing share one finalization lock. A button-finished take is saved
from an immutable audio snapshot before a concurrent close completes; closing
first discards unfinished audio. This prevents empty labelled takes and a closed
session returning to the armed state.

The pinned overlay also checks a completion marker in wake-model inventory
probes. A lost or truncated shell reply means **unknown inventory**, so
reconciliation defers instead of attempting to reinstall apparently missing
models. A successfully completed empty inventory still triggers normal setup.

## Owner workflow

1. Open the local recorder page on the Mac and select **Training · 12 takes**.
2. Click **Start session**. Two dim amber segments mean the session is armed;
   the recording has not started.
3. Tap the Dot's physical action button (the button with a dot), or press
   **Record** on the Mac page when testing from a distance. Preparation
   begins. Wait; do not speak yet.
4. After at least six contiguous 80 ms audio frames reach the recorder, two
   opposite ring segments flash blue twice. Capture is already running. Say
   **«Привет, Мышка»** in your ordinary voice. The blue segments remain lit.
5. Tap the same physical button, or press **Stop & save** on the Mac, to finish. The recording is saved; a brief
   green signal confirms controller storage. The page separately confirms
   that the file was downloaded and checksum-verified on the Mac.
6. Tap again or press **Record** when ready for the next take. Nothing starts automatically.
   Vary natural intonation, distance and orientation. Keep the same phrase
   for the whole batch. There are no re-record or next-phrase buttons.
7. After the batch, take a break. Record **Validation · 8 takes** and
   **Final test · 8 takes** as separate sessions, preferably with different
   positions/background conditions. Do not use final-test audio for tuning.

A maximum-length take is **discarded**, not silently labelled positive. Tap
within 12 seconds after the ready cue. Preparation has an eight-second limit.
A muted microphone, lost stream, lost connection, or page heartbeat absent for
20 seconds ends the session. The full session has a ten-minute limit. Saved
completed takes remain available. Reloading/closing the page does not resume
recording; start a fresh session after the old lease expires.
Reloading the Mac page displays the most recent completed batch saved there.
This history display does not resume capture or renew a recording lease.
Control requests are bound to the page's session ID, so a stale tab cannot
start/stop a take or renew the lease of a different session.

## Data and training

Each saved WAV includes the preparation pre-roll. Its JSON sidecar records
`ready_offset_seconds`, duration, contiguous frame count, split, source,
stop reason and SHA-256. Preserve that pre-roll: the wake detector needs
streaming context. Inspect alignment and speech quality before adding the new
session to a training manifest. The cue timestamp is not a speech-end label.
Button/room noise must not be mistaken for the end of the phrase.

Files first go to `training-recordings/<session>/` next to the controller's
SQLite database. The local page downloads and verifies completed files under
the explicitly supplied private output directory on the Mac. Both locations
are private household audio. This extension does not upload to an external
service, invoke HA/STT/TTS, delete completed recordings, or retrain automatically.
Delete controller copies separately after verifying the Mac backup if desired.
Do not commit recordings, receipts, credentials or generated overlays.

Only one session per device is allowed. Its normal assistant turns are reserved
for the recorder until completion. Start while the Dot is idle and no music or
timer is playing; avoid sending announcements/configuration updates during a
batch. Other Dots retain their normal operation. For a quiet dataset, keep them
out of hearing range if they would answer the same wake phrase.

Import the training and validation batches into a **new** work manifest,
preserving each batch's selected split. Keep the fresh final-test session
outside that manifest; open it only with the frozen-model evaluator below:

```sh
python3 training/recorder/import_session.py \
  --base-manifest private/previous-run/sources.json \
  --session-dir private/dot-wake-recordings/TRAIN_SESSION \
  --session-dir private/dot-wake-recordings/VALIDATION_SESSION \
  --output private/new-run/sources.json
```

The importer rejects incomplete batches, changed audio, missing frames and
reused recordings. It deliberately leaves `speech_end` unset. Derive training
alignment locally and review it; do not use the button press as speech end.
Then follow the [training and frozen-evaluation stages](../README.md).

## Installation

This is a local extension, **not an upstream EchoMuse feature**. The patcher
checks the exact upstream source hashes; the deployer also checks the pinned
container image digest. Do not carry it forward to a different upstream release
without review. A controller restart is needed to install/remove the overlay;
no Dot firmware update or USB connection is needed.

Copy `em_controller.py` and `em_api.py` out of the matching running container
into an ignored directory, then generate the overlay:

```sh
python3 training/recorder/patch_controller.py \
  --source private/recorder/source --output private/recorder/overlay
python3 training/recorder/deploy_overlay.py \
  --overlay private/recorder/overlay --receipt private/recorder/deployment
```

The deployer uses the current `kubectl` context, namespace `echomuse`, deployment
`echomuse-controller`, container `controller`. Options override these names.
`--ssh-host <configured-host>` instead runs `sudo -n k3s kubectl` through SSH.
For a reviewed update of an existing recorder overlay, add `--replace-existing`.
It saves the previous deployment privately, creates an immutable ConfigMap, and
mounts three source files into that one deployment. Wait for rollout readiness.
For rollback, remove the `training-recorder` volume and its three mounts from
the deployment; retain the original image and other configuration. Wait for
readiness before deleting the unused ConfigMap. No database schema changes are
made. A device reconnect loads its persisted ordinary settings.

Start the Mac companion (standard Python library only):

```sh
python3 training/recorder/local_server.py \
  --credentials private/controller/credentials.private.json \
  --device '<controller-device-id>' --label 'Training Dot' \
  --output private/dot-wake-recordings --port 8769
```

The credential file contains `url`, `username`, and `password` for an existing
Controller administrator. It stays on the Mac; the browser gets no Controller
token. The listener binds only to `127.0.0.1`; use exactly that host in the URL.
The UI validates Host/Origin and requires a random anti-CSRF token for actions.
The Controller's new `/api/training/` routes require its existing administrator
authentication. An HTTP controller URL should be used only on a trusted LAN or
through an SSH tunnel; HTTPS is preferred when configured.

## Verification and limits

`python3 -m unittest discover -s tests -p test_training_recorder.py` exercises
ready-cue ordering, manual stop/storage, frame-gap rejection, preparation
failure, hardware mute, heartbeat expiry and maximum-length rejection using
synthetic frames. These tests do not assert that LEDs are physically visible
or that a human recording has usable speech. The first owner session verifies
those acoustic/physical details; inspect its WAVs before training a successor
to the currently deployed model.

### First live session — October 16, 2026

The owner completed all 12 training takes on Dot 002 using the physical action
button. All files were downloaded and checksum-verified on the Mac, with no
sequence gaps. The recorder received 0.48 seconds of audio before issuing
each ready cue. The existing model detected 10 of these 12 phrases in offline
replay. This is a baseline on the new training set, not an independent quality
score for a retrained model. After completion, both Dots reported local
listening with continuous streaming disabled.

The owner then recorded eight separate validation takes near the Dot and
eight final-test takes from the sofa, approximately three metres from its
normal room position. The last batch used the Mac button to start and stop
each take without approaching the microphone. Final-test audio was kept out
of the training manifest and unopened during candidate selection. All 28
completed takes were saved on the Mac; the device returned to local listening
after each batch. The close validation and room-distance final set represent
different conditions and should be reported separately.

That separation describes the first follow-up experiment. Its sofa test failed,
and those eight exposed recordings were subsequently promoted to training with
their original split and failed-test provenance preserved. They are no longer
an independent test of the successor. The owner authorized deploying that
successor as a trial; a new eight-take room-distance session remains pending.
See the [experiment and deployment record](../../docs/russian-wake-word.md).

For a subsequent fine-tuning experiment, retain the original synthetic and
negative examples and initialize from the **raw** previous `selected.pt`
checkpoint. These parameters are a starting experiment, not an accepted
deployment recipe:

```sh
python3 training/train_oww.py --work private/new-run --candidate fine-tuned \
  --initialize-from private/previous-run/candidate/selected.pt \
  --owner-extra private/new-run/features-owner-wide \
  --owner-aligned private/new-run/features-owner-aligned \
  --steps 8000 --negative-weight 100 --learning-rate 0.00003
```

The recipe records both the initial checkpoint hash and source-manifest hash.
Do not feed the score-calibrated export back into training. Freeze only after
the validation gates pass. A fresh final session can stay outside the training
manifest entirely and be opened once for the frozen model:

```sh
python3 training/recorder/evaluate_session.py \
  --candidate private/new-run/fine-tuned \
  --session-dir private/dot-wake-recordings/FINAL_SESSION \
  --assets private/frontend-assets
```

When the entire final session stays outside the manifest, run
`evaluate_oww.py --controls-only` for the frozen model's noise and continuous
speech checks. Calibrate with `--reference-splits val background`, then verify
the new final session also retains identical decisions after calibration.
These options do not turn training or previously exposed regression clips
into an independent final test.

This extra final check measures positive recall only. It does not replace the
separate negative, continuous-speech, calibration-parity or deployment checks.
If it fails, retain that failed report. An exposed final batch may inform a
new experiment only with explicit provenance and a fresh independent final
session; never present reuse of those examples as an independent test.
