# Documentation figures

These repo-native assets belong to the documentation and contain no household
identifiers, captured audio or private endpoint addresses. Each SVG includes a
title and a text description. The linked prose provides a full text equivalent.

- **[architecture.svg](architecture.svg)** — hand-authored vector diagram of the
  pinned deployment and its separate voice, music and BLE paths. Described in
  [architecture](../architecture.md); based on the controller, Bluetooth and
  voice runbooks. The cloud recognition branch is explicit.
- **[migration.svg](migration.svg)** — hand-authored vector summary of the
  [migration checkpoints](../migration.md), with the verified hardware scope
  and stop conditions. It intentionally contains no block-device commands.
- **[latency.svg](latency.svg)** — matplotlib plot of the aggregate measurements
  in [latency-data.json](latency-data.json), transcribed from the
  [October 14 voice-feature record](../voice-features.md#deployment-checks--october-14-2026).
  There is one HA run and one pair of concurrent service requests. The two
  scopes have different time origins and scales; no percentile or paired
  non-streaming comparison can be derived from them.
- **[conversion-journey.svg](conversion-journey.svg)** — six ordered conversion
  stages, the stop conditions before flashing, and the intended everyday result.
- **[voice-request.svg](voice-request.svg)** — conceptual request routing,
  including the recorded cloud-recognition boundary and local answer path.
- **[acceptance-targets.svg](acceptance-targets.svg)** — observable pass
  conditions for six feature areas; these are not a live status report.
- **[bluetooth-roles.svg](bluetooth-roles.svg)** — the difference between a
  physical radio, a proxy endpoint and an iBeacon consumer integration.
- **[reply-timeline.svg](reply-timeline.svg)** — a second view of the *same*
  recorded HA run, showing the interval from first MP3 to `intent-end`. It adds
  no new experiment, acoustic timing or baseline comparison.

The [visual guide](../visual-guide.md) gives text equivalents for all five new
figures and links each process stage to its detailed runbook. Numbered steps,
roles and pass conditions carry meaning independently of color. The process
illustrations use a light canvas and contrasting text for GitHub's light and
dark themes; no external fonts, scripts, embedded images or web requests are used.

## Reproduce the process illustrations

The four process figures use only the Python standard library:

```sh
python3 docs/assets/render_process.py
```

Edit their labels and layout in `render_process.py`, regenerate the SVGs and
visually inspect the result. Keep the text equivalent in `visual-guide.md`
synchronized. Arrows describe conceptual order, not network packets or duration.

## Reproduce the plot

The initial plot used Python 3.14 and matplotlib 3.11.2. Use an isolated Python
environment with matplotlib installed, then run:

```sh
python docs/assets/render_latency.py
python docs/assets/render_reply_timeline.py
```

Both plot scripts read only the public JSON values. They write `latency.svg`
and `reply-timeline.svg`, respectively. For a local review image, add
`--png /path/to/private/preview.png` to either command. No credentials,
network access or running device is required. Matplotlib's SVG text remains
searchable; deterministic IDs and omitted timestamp metadata avoid incidental
diffs. Font geometry can differ across matplotlib/font versions, so visually
review the generated result before committing it.

The initial rendering was reviewed at full size for text fit, legible labels,
the two independent x-axis scales and accessible descriptions. Changing the
data requires updating its source record and scope, not merely changing a bar.
