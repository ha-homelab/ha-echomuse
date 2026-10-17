# Train a Russian wake phrase for EchoMuse

This local workflow targets **«Привет, Мышка»** as the only active wake phrase.
EchoMuse consumes an openWakeWord ONNX classifier with input `[batch, 16, 96]`.
The old EchoLocal microWakeWord TFLite classifier is incompatible. Existing
consented WAV recordings can be reused; the model itself must be retrained.

Training and recordings stay on the operator's Mac. Use ignored `private/`
directories for all outputs, including features and model weights. Do not publish
personal models or recordings with this repository. The downloaded negative
feature dataset is **CC BY-NC-SA 4.0**, independently of this repository's code
license; see the [dataset card](https://huggingface.co/datasets/davidscripka/openwakeword_features).

## Data and stages

The importer reads the existing EchoLocal collection's manifest and preserves
its train/validation/test sessions. It does not relabel participant recordings
using ASR. Every augmentation remains with its original source. Synthetic speech
uses four Russian Piper voices; shared synthetic voices across partitions do not
demonstrate recognition of an unseen human speaker.

The initial recipe uses 24 owner positives and 36 owner negatives for training,
8 positives and 16 negatives for validation, and a separate 8 positives and 16
negatives for the final test. The 6,500 synthetic sources retain their original
80/10/10 split. Training adds resampling, gain, artificial room echoes and noise;
these are simulations, not additional real recordings. The frozen English speech
embedding is an upstream limitation for Russian; measure results rather than
assuming language support.

1. Create a private environment and install `training/requirements.txt`.
2. Supply the exact `melspectrogram.onnx` and `embedding_model.onnx` used by the
   deployed devices. Record hashes; never substitute a different frontend.
3. Download a bounded, deterministic subset of training negatives and the
   separate validation feature array. The initial 100,000 training windows
   represent about 35.6 hours; `--expand` adds 900,000 disjoint windows, reaching
   about 355.6 hours. The validation array represents about 10.7 hours.
4. Prepare training and validation data, then train. Selection uses validation
   only, including complete-clip peak scores and false-event counts with a
   1.5-second refractory period. Do not train on the validation feature array.
5. Freeze the selected model hash and threshold before preparing/evaluating the
   final test. A final test result is immutable. Failed tests require a new
   independent acceptance set before claiming a newly tuned candidate passed.
6. Calibrate the exported score if its threshold exceeds EchoMuse's 0.975
   configuration ceiling. Verify decision parity, then upload the accepted ONNX
   model, change the device wake model, and verify its
   installed checksum and runtime status on each Dot. Keep the previous config
   privately for rollback. This is a model change; no USB reflash is required.
7. Check the phrase by speaking naturally near each device, then at normal room
   distance and during music. Offline recall is not live acoustic acceptance.

Feature preparation reuses only complete caches whose source recordings,
manifest, frontend models, preparation code and output hashes still match the
saved receipt. A changed input, old receipt without output hashes, or interrupted
run is rejected. Use a fresh private work directory and prepare features again;
do not copy old features into it or overwrite the receipt to bypass this check.
Freezing also requires the training recipe's recorded source-manifest hash.

## Commands

Set these paths to your private work directory, previous project, and exact
deployed feature models. Do not put credentials into these commands.

```bash
WORK="$PWD/private/myshka-oww-run"
LEGACY="/path/to/ha-echo-dot"
ASSETS="/path/to/deployed/oww-assets"
uv venv --python 3.11 "$WORK/.venv"
uv pip install --python "$WORK/.venv/bin/python" -r training/requirements.txt
PYTHON="$WORK/.venv/bin/python"
"$PYTHON" training/fetch_oww_negatives.py --work "$WORK"
"$PYTHON" training/fetch_oww_negatives.py --work "$WORK" --expand
"$PYTHON" training/prepare_oww.py --work "$WORK" --legacy "$LEGACY" --assets "$ASSETS" --split train
"$PYTHON" training/prepare_oww.py --work "$WORK" --legacy "$LEGACY" --assets "$ASSETS" --split val
"$PYTHON" training/align_oww_owner.py --work "$WORK" --assets "$ASSETS" --negative-only
"$PYTHON" training/align_oww_owner.py --work "$WORK" --assets "$ASSETS" \
  --alignments "$LEGACY/private/mac-owner-training-20261003/train-asr-v1"
"$PYTHON" training/train_oww.py --work "$WORK" --candidate candidate-1 \
  --steps 16000 --negative-weight 100 --learning-rate 0.0001 \
  --owner-extra "$WORK/features-owner-wide" --owner-aligned "$WORK/features-owner-aligned"
```

Read `candidate-1/selected.json` and `export.json`. A model file existing is not
proof of acceptable recognition. Quiet human positives require speech-end
alignment: a percentage of peak amplitude can mistake room noise after the
phrase for its ending. Existing local ASR timestamps establish timing only;
the participant supplies the labels. The aligned owner files replace the
earlier owner-positive features; they are not appended alongside bad alignment.

For expanded validation sets, `--selection-owner-recall` sets the minimum recall
used when ranking fallback candidates (default `0.875`). Set it before opening
the fresh final test, and inspect old/new recording cohorts separately so an
aggregate gain cannot hide a regression. This option does not relax the
independent freeze gates below.

The optional `--completed-phrase-only` experiment retains only the last two
windows from each four-window aligned positive group. Those windows end after
the estimated phrase ending; earlier windows can precede the final syllable.
This is useful when a classifier confuses the full phrase with a shorter
prefix such as «Привет, мышь». It leaves negative examples and source splits
unchanged. Re-evaluate recall and false activations; this flag alone does not
establish that suffix discrimination improved.

An additional experiment, `confirm_oww.py`, exports a classifier that requires
agreement between two overlapping views of the input. It evaluates the trained
head on the current 16 embeddings and a view shifted by one embedding, repeating
the oldest embedding at the boundary. The lower score wins. This approximates
temporal confirmation within the existing `[batch, 16, 96]` interface; it is
**not** a real seventeenth frame or a firmware two-frame counter. It adds
classifier computation and can reduce recall, so validate it independently.

```bash
"$PYTHON" training/confirm_oww.py --work "$WORK" \
  --source-candidate candidate-1 --candidate confirmed --threshold 0.98
```

The threshold above is an example, not a universal setting. The exporter checks
its ONNX decisions against two separate evaluations of the original model on
all validation and background windows. It writes a new candidate; it does not
overwrite the source. Fine-tune from the original raw checkpoint if needed,
not from this exported wrapper. Freeze, test and calibrate the new candidate
using the same acceptance rules as an ordinary classifier. Calibration shifts
the logits before the final sigmoid and supports either head layout.
Release filenames include the frozen raw model's hash prefix, so uploading a
successor does not reuse the currently deployed model's filename.

Before the final test, use `freeze_oww.py` to create an immutable `freeze.json`.
The default gate requires all owner validation positives, no owner/hard-negative
validation activations, and at most 0.3 validation events/hour. A controlled
trial with lower owner recall requires an explicit `--minimum-owner-recall`
and explanatory `--note`; that limit must remain visible in the result.

```bash
"$PYTHON" training/freeze_oww.py --work "$WORK" --candidate candidate-1
"$PYTHON" training/prepare_oww.py --work "$WORK" --legacy "$LEGACY" --assets "$ASSETS" --split test
"$PYTHON" training/evaluate_oww.py --work "$WORK" --candidate candidate-1 --legacy "$LEGACY" --assets "$ASSETS"
"$PYTHON" training/calibrate_oww.py --work "$WORK" --candidate candidate-1
```

The final report covers held-out owner and synthetic clips, an hour of held-out
continuous LibriSpeech, and synthetic silence/noise/hum controls. It is not a
room-noise soak. Keep all reports and the environment lock privately. For
deployment details and observed results, see [Russian wake phrase](../docs/russian-wake-word.md).

## Record new samples on the Dot

Use the [attended button-and-ring recorder](recorder/README.md) to collect the
actual device wake stream. It prepares audio before the blue ready cue and
saves each take when the owner presses the action button or **Stop & save**
on the Mac. Use the Mac button from the normal listening position so that
walking to the speaker does not change the recording distance. Keep training,
validation and final-test sessions separate. For later runs, previously opened
test data is regression coverage; reserve a fresh session for independent
acceptance and open it only after freezing the new candidate.
