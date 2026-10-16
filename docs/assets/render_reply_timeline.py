#!/usr/bin/env python3
"""Plot one recorded HA response timeline; no inferred acoustic timings."""
import argparse
from html import escape
import json
from pathlib import Path
import re

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--png", type=Path, help="Optional local visual-review image")
    args = parser.parse_args()
    directory = Path(__file__).resolve().parent
    data = json.loads((directory / "latency-data.json").read_text())
    run = data["ha_run"]
    first, end = run["first_mp3_payload"], run["intent_end"]
    if data["unit"] != "seconds" or not 0 < first < end:
        raise ValueError("Expected ordered response milestones in seconds")
    overlap = end - first
    matplotlib.rcParams.update({"font.family": "DejaVu Sans", "font.size": 12,
                                "svg.fonttype": "none", "svg.hashsalt": "echomuse-reply-timeline"})
    fig, ax = plt.subplots(figsize=(12, 5.9))
    fig.set_facecolor("#f7f9fd")
    fig.subplots_adjust(left=.08, right=.95, bottom=.27, top=.61)
    ax.set_facecolor("#f7f9fd")
    fig.text(.06, .92, "05 / ONE RECORDED RESPONSE", size=11, weight="bold", color="#6d4ad1")
    fig.text(.06, .83, "Audio arrives before generation finishes", size=24, weight="bold", color="#172b4d")
    fig.text(.06, .76, f'{data["recorded_date"]} · one HA run · {run["response_sentences"]} Russian sentences', size=12, color="#4b6178")
    ax.barh([0], [first], height=.36, color="#bda9ee", edgecolor="#6d4ad1")
    ax.barh([0], [overlap], left=[first], height=.36, color="#a6e3d7", edgecolor="#087f78")
    ax.text(first / 2, 0, "Before first payload", ha="center", va="center", color="#30235f", size=12)
    ax.text(first + overlap / 2, 0, "Audio delivery overlaps generation", ha="center", va="center", color="#075850", size=12)
    for value, label, color in ((0, "Run starts", "#4b6178"),
                                (first, f"First MP3\n{first:.3f} s", "#6d4ad1"),
                                (end, f"Intent end\n{end:.3f} s", "#087f78")):
        ax.vlines(value, -.22, .38, color=color, linewidth=1.5)
        ax.text(value, .47, label, ha="center", va="bottom", size=12, weight="bold", color=color)
    ax.set_xlim(-1, 59)
    ax.set_ylim(-.6, .85)
    ax.set_yticks([])
    ax.set_xticks(range(0, 60, 10))
    ax.tick_params(axis="x", colors="#4b6178")
    ax.set_xlabel("Seconds from the same HA run start", color="#4b6178", labelpad=12)
    ax.spines[["top", "left", "right"]].set_visible(False)
    ax.spines["bottom"].set_color("#becbdc")
    fig.text(.06, .13, f"{overlap:.3f} s of observed overlap — not a measured speedup against a non-streaming run.", size=12, color="#172b4d", weight="bold")
    fig.text(.06, .072, "Receipt of an MP3 payload does not establish when sound was heard. No paired baseline or percentile estimate.", size=10, color="#4b6178")
    target = directory / "reply-timeline.svg"
    fig.savefig(target, metadata={"Date": None, "Creator": "ha-echomuse measured reply timeline"})
    svg = re.sub(r"<!DOCTYPE.*?>\s*", "", target.read_text(), flags=re.DOTALL)
    svg = svg.replace("<svg ", '<svg role="img" aria-labelledby="title desc" ', 1)
    index = svg.index(">", svg.index("<svg ")) + 1
    desc = (f"One recorded HA run received its first MP3 payload at {first:.3f} seconds and "
            f"reached intent end at {end:.3f} seconds, an overlap of {overlap:.3f} seconds. "
            "These events do not measure acoustic latency or improvement against a baseline.")
    svg = svg[:index] + '<title id="title">Recorded response timeline</title><desc id="desc">' + escape(desc) + '</desc>' + svg[index:]
    target.write_text("\n".join(line.rstrip() for line in svg.splitlines()) + "\n")
    if args.png:
        fig.savefig(args.png, dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    main()
