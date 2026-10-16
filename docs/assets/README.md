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

## Reproduce the plot

The initial plot used Python 3.14 and matplotlib 3.11.2. Use an isolated Python
environment with matplotlib installed, then run:

```sh
python docs/assets/render_latency.py
```

The script reads only the public JSON values and writes `latency.svg`. For a
local review image, add `--png /path/to/private/preview.png`. No credentials,
network access or running device is required. Matplotlib's SVG text remains
searchable; deterministic IDs and omitted timestamp metadata avoid incidental
diffs. Font geometry can differ across matplotlib/font versions, so visually
review the generated result before committing it.

The initial rendering was reviewed at full size for text fit, legible labels,
the two independent x-axis scales and accessible descriptions. Changing the
data requires updating its source record and scope, not merely changing a bar.
