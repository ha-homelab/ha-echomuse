#!/usr/bin/env python3
"""Render only the published aggregate measurements; no live access required.

Run with Python and matplotlib installed. Outputs latency.svg beside this file.
Pass --png /path/to/preview.png for an optional local visual-review image.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--png", type=Path)
    args = parser.parse_args()
    directory = Path(__file__).resolve().parent
    data = json.loads((directory / "latency-data.json").read_text())
    matplotlib.rcParams.update({
        "svg.fonttype": "none",
        "svg.hashsalt": "ha-echomuse-latency",
        "font.family": "DejaVu Sans",
        "font.size": 12,
        "text.color": "#172b4d",
        "axes.labelcolor": "#425e78",
        "xtick.color": "#425e78",
        "ytick.color": "#172b4d",
    })
    fig, axes = plt.subplots(2, 1, figsize=(12, 7.6))
    fig.set_facecolor("#f5f8fc")
    fig.subplots_adjust(top=0.76, bottom=0.18, left=0.22, right=0.93, hspace=1.4)
    fig.text(0.05, 0.95, "ECHOMUSE / RECORDED MEASUREMENTS", size=11, weight="bold", color="#486680")
    fig.text(0.05, 0.89, "Streaming starts before the answer is complete", size=22, weight="bold")
    fig.text(0.05, 0.845, "October 14, 2026 · two different test scopes · no acoustic latency claim", size=12, color="#425e78")

    ha = data["ha_run"]
    values = [ha["first_mp3_payload"], ha["intent_end"]]
    axes[0].barh([1, 0], values, height=0.48, color=["#0e8178", "#466a9c"])
    axes[0].set_yticks([1, 0], ["First MP3 payload", "Intent end"])
    axes[0].set_xlim(0, 65)
    axes[0].set_xticks([0, 10, 20, 30, 40, 50, 60])
    axes[0].set_xlabel("Seconds from the same HA run start", labelpad=8)
    axes[0].set_title("A. One real HA run · six Russian sentences", loc="left", size=13, weight="bold", pad=16)
    for y, value in zip([1, 0], values):
        axes[0].text(value + 0.8, y, f"{value:.3f} s", va="center", size=12, weight="bold")

    pcm = data["service_test"]["first_pcm"]
    axes[1].barh([1, 0], pcm, height=0.48, color=["#0e8178", "#0e8178"])
    axes[1].set_yticks([1, 0], ["Request A", "Request B"])
    axes[1].set_xlim(0, 6)
    axes[1].set_xticks([0, 1, 2, 3, 4, 5, 6])
    axes[1].set_xlabel("Seconds to first PCM · concurrent service requests", labelpad=8)
    axes[1].set_title("B. Irina service only · first audio before final text was sent", loc="left", size=13, weight="bold", pad=16)
    for y, value in zip([1, 0], pcm):
        axes[1].text(value + 0.1, y, f"{value:.2f} s", va="center", size=12, weight="bold")

    for ax in axes:
        ax.set_facecolor("#f5f8fc")
        ax.spines[["top", "right", "left"]].set_visible(False)
        ax.spines["bottom"].set_color("#cbd7e6")
        ax.tick_params(axis="y", length=0, pad=12)
        ax.grid(axis="x", color="#dfe7f0", linewidth=0.8)
        ax.set_axisbelow(True)
    fig.text(0.05, 0.082, "Source: docs/voice-features.md · reproducible values: docs/assets/latency-data.json", size=10, color="#425e78")
    fig.text(0.05, 0.044, "Separate scales. No paired baseline, percentile estimate, or measured microphone-to-speaker timing.", size=10, color="#425e78")
    target = directory / "latency.svg"
    fig.savefig(target, format="svg", metadata={"Date": None, "Creator": "ha-echomuse aggregate latency renderer"})
    svg = target.read_text()
    svg = re.sub(r"<!DOCTYPE.*?>\s*", "", svg, flags=re.DOTALL)
    svg = svg.replace("<svg ", '<svg role="img" aria-labelledby="title desc" ', 1)
    closing = svg.index(">", svg.index("<svg ")) + 1
    description = (
        '<title id="title">Recorded EchoMuse streaming measurements</title>'
        '<desc id="desc">One HA run delivered first MP3 at 20.275 seconds and reached intent end at 53.753 seconds. '
        'A separate concurrent Irina service test delivered first PCM at 2.22 and 4.74 seconds. '
        'The test scopes differ and do not measure audible response latency.</desc>'
    )
    target.write_text(svg[:closing] + description + svg[closing:])
    if args.png:
        fig.savefig(args.png, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)


if __name__ == "__main__":
    main()
