#!/usr/bin/env python3
"""Render the public process illustrations with the Python standard library.

These are conceptual diagrams and acceptance targets, not live status views.
Run from any directory; the four source-only SVGs are written beside this file.
"""
from html import escape
from pathlib import Path

PALETTE = {
    "violet": ("#6d4ad1", "#f0ebff"),
    "teal": ("#087f78", "#e2f6f1"),
    "blue": ("#2563a6", "#e8f1ff"),
    "amber": ("#a85a06", "#fff2d9"),
    "rose": ("#af3e68", "#ffebf2"),
    "slate": ("#4b6178", "#edf2f7"),
}


class Diagram:
    def __init__(self, height, title, description, eyebrow, subtitle):
        self.height = height
        self.parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="{height}" '
            f'viewBox="0 0 1280 {height}" role="img" aria-labelledby="title desc">',
            f'<title id="title">{escape(title)}</title><desc id="desc">{escape(description)}</desc>',
            '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" '
            + 'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
            + '<path d="M0 0 L10 5 L0 10 Z" fill="#758399"/></marker></defs>',
            '<style>text{font-family:Arial,Helvetica,sans-serif} '
            + '.edge{fill:none;stroke:#758399;stroke-width:2.5;marker-end:url(#arrow)}</style>',
        ]
        self.rect(0, 0, 1280, height, "#f7f9fd", radius=24)
        self.rect(0, 0, 1280, 9, "#6d4ad1", radius=0)
        self.text(60, 49, eyebrow, 14, "#6d4ad1", bold=True)
        self.text(60, 96, title, 35, bold=True)
        self.text(60, 132, subtitle, 18, "#4b6178")

    def rect(self, x, y, width, height, fill, stroke=None, radius=18):
        border = f' stroke="{stroke}" stroke-width="1.5"' if stroke else ""
        self.parts.append(f'<rect x="{x}" y="{y}" width="{width}" height="{height}" '
                          f'rx="{radius}" fill="{fill}"{border}/>')

    def text(self, x, y, value, size=18, color="#172b4d", bold=False):
        weight = ' font-weight="700"' if bold else ""
        self.parts.append(f'<text x="{x}" y="{y}" font-size="{size}" '
                          f'fill="{color}"{weight}>{escape(value)}</text>')

    def lines(self, x, y, values, size=18, color="#304a64", gap=26):
        for offset, value in enumerate(values):
            self.text(x, y + offset * gap, value, size, color)

    def edge(self, path):
        self.parts.append(f'<path class="edge" d="{path}"/>')

    def card(self, x, y, width, height, color, label, title, lines):
        accent, tint = PALETTE[color]
        self.rect(x, y, width, height, "#ffffff", "#d9e2ee")
        self.rect(x + 1, y + 1, width - 2, 47, tint, radius=17)
        self.text(x + 22, y + 30, label, 14, accent, bold=True)
        self.text(x + 22, y + 82, title, 24, bold=True)
        self.lines(x + 22, y + 116, lines, size=18)

    def save(self, name):
        self.text(60, self.height - 24, "EchoMuse project guide · recorded baseline, not live device status", 14, "#4b6178")
        target = Path(__file__).resolve().parent / name
        target.write_text("\n".join(self.parts + ["</svg>"]) + "\n", encoding="utf-8")
        return target


def journey():
    d = Diagram(960, "From stored Echo to a room assistant",
                "Six ordered stages: identify the Dot 2, preserve recovery, prepare the controller, "
                "migrate over USB, enroll current HA endpoints, and verify audible results. "
                "Stop before migration if identity or recovery cannot be verified.",
                "01 / CONVERSION JOURNEY", "Process overview · Echo Dot 2 / RS03QR · follow the full runbook before writing flash")
    d.edge("M420 285 H456")
    d.edge("M820 285 H856")
    d.edge("M1040 395 V438 H240 V480")
    d.edge("M420 590 H456")
    d.edge("M820 590 H856")
    steps = [
        (60, 175, "violet", "1 / IDENTIFY", "Confirm the hardware", ["Read the model and installed OS.", "Check the partition layout.", "Result: the runbook matches.", "Other Echo models: stop here."]),
        (460, 175, "amber", "2 / PRESERVE", "Keep a way back", ["Use a tested USB data cable.", "Save this device’s recovery copy.", "Check that the backup is readable.", "No verified recovery: do not flash."]),
        (860, 175, "blue", "3 / PREPARE", "Start the controller", ["Keep persistent data and its CA.", "Prepare the pinned emOS image.", "Keep per-device credentials private.", "Result: host and recovery ready."]),
        (60, 480, "rose", "4 / MIGRATE", "Install, then approve", ["Follow the exact USB procedure.", "Boot emOS and EchoMuse.", "Approve the authenticated device.", "Result: controller link established."]),
        (460, 480, "violet", "5 / ENROLL", "Connect Home Assistant", ["Add the current voice endpoint.", "Assign the Assist pipeline.", "Add music and BLE if required.", "Result: current entities in HA."]),
        (860, 480, "teal", "6 / VERIFY", "Listen and compare", ["Check voice on the same Dot.", "Compare home values with HA.", "Check music, stop and reconnect.", "Result: an attended test record."]),
    ]
    for x, y, color, label, title, lines in steps:
        d.card(x, y, 360, 220, color, label, title, lines)
    d.text(490, 463, "Continue with this device’s own image and recovery copy", 16, "#4b6178")
    d.rect(60, 748, 1160, 132, "#e2f6f1")
    d.text(84, 786, "TARGET RESULT", 14, "#087f78", bold=True)
    d.text(84, 821, "Ordinary USB power + Wi-Fi for everyday use", 27, bold=True)
    d.text(84, 853, "Voice answers · reviewed home controls · statistics · optional music and Bluetooth", 19)
    return d.save("conversion-journey.svg")


def request_flow():
    d = Diagram(980, "What happens after “Hey Jarvis”",
                "Wake detection is local. The recorded FCC service transcribes audio in the cloud. "
                "Home Assistant routes the request to native intents or the local Ollama home tools. "
                "Local Silero synthesis returns audio to the originating Dot. Streaming can overlap generation.",
                "02 / VOICE REQUEST", "Conceptual service flow · physical transport runs through the controller · not a timing diagram")
    d.edge("M420 257 H456")
    d.edge("M820 257 H856")
    d.edge("M1040 335 V368 H640 V405")
    d.edge("M1040 368 V405")
    d.edge("M640 600 V670")
    d.edge("M1040 600 V670")
    d.edge("M460 745 H424")
    d.card(60, 175, 360, 160, "violet", "1 / ON THE DOT", "Wake and capture", ["Local wake model or action button.", "Audio goes to the selected pipeline."])
    d.card(460, 175, 360, 160, "amber", "2 / CLOUD IN THE RECORDED SETUP", "Speech to text", ["FCC receives the spoken request.", "Its transcript returns to HA."])
    d.card(860, 175, 360, 160, "blue", "3 / HOME ASSISTANT", "Route the request", ["Prefer supported native commands.", "Use the local model when needed."])
    d.card(460, 405, 360, 195, "teal", "3A / NATIVE INTENT", "A matching command", ["Resolve the exposed entity or area.", "Handle supported local intents.", "Return a result or a clear error."])
    d.card(860, 405, 360, 195, "violet", "3B / LOCAL OLLAMA + HOME TOOLS", "A broader question", ["Read permitted states or statistics.", "Control only reviewed targets.", "Reject ambiguous device matches."])
    d.rect(60, 405, 360, 195, "#fff2d9")
    d.text(82, 443, "A CUE IS ONLY A CUE", 14, "#a85a06", bold=True)
    d.lines(82, 484, ["A light or wake sound confirms", "the trigger, not the transcript,", "a successful action or an", "answer heard in the room."], size=18)
    d.card(460, 670, 760, 160, "teal", "4 / LOCAL SYNTHESIS", "Silero through the Wyoming adapter", ["A complete sentence can become audio while more text is generated.", "Streamed text, streamed TTS and device playback must all cooperate."])
    d.card(60, 670, 360, 160, "rose", "5 / ORIGINATING DOT", "Play the answer", ["Fetch and play the HA audio.", "Verify completeness by listening."])
    d.rect(60, 867, 1160, 53, "#f0ebff")
    d.text(82, 900, "During playback: say “Hey Jarvis”, wait for the cue, then give the next request.", 20)
    return d.save("voice-request.svg")


def acceptance():
    d = Diagram(970, "What a working result looks like",
                "Six acceptance targets cover audible voice, home actions, statistics, music, optional Bluetooth "
                "and recovery. These are checks to perform, not green status indicators or new test results.",
                "03 / ACCEPTANCE TARGETS", "Run on each Dot separately · these cards are a checklist, not a report that every check passed")
    cards = [
        (60, 175, "violet", "VOICE", "A complete spoken answer", ["Press the action button and ask.", "Then repeat with the wake phrase.", "PASS WHEN: the same Dot gives", "an intelligible, complete answer."]),
        (460, 175, "teal", "HOME ACTIONS", "Only the chosen device", ["Choose one known light or switch.", "Check its area and allowed targets.", "PASS WHEN: only the intended", "device changes, confirmed in HA."]),
        (860, 175, "blue", "STATISTICS", "A value with context", ["Ask for a state or time interval.", "Compare units and source in HA.", "PASS WHEN: the answer matches", "the state or Recorder statistics."]),
        (60, 470, "rose", "MUSIC", "Audio and queue agree", ["Play, cross a track boundary, stop.", "Use the originating Dot’s queue.", "PASS WHEN: playback stays clear", "and the intended queue stops."]),
        (460, 470, "amber", "BLUETOOTH / OPTIONAL", "BLE data reaches HA", ["Enroll the separate BLE endpoint.", "Check scanner and advertisements.", "PASS WHEN: HA receives BLE data;", "a tracker may still have no device."]),
        (860, 470, "slate", "RECONNECT AND RECOVERY", "A repeatable restart", ["Keep this device’s backup private.", "Test an attended power cycle.", "PASS WHEN: links recover and", "a new voice request succeeds."]),
    ]
    for x, y, color, label, title, lines in cards:
        d.card(x, y, 360, 230, color, label, title, lines)
    d.rect(60, 754, 1160, 140, "#172b4d")
    d.text(84, 791, "KEEP THREE SEPARATE RECEIPTS", 14, "#b7d8ff", bold=True)
    d.text(84, 831, "Configuration saved     →     Protocol verified     →     Heard by a person", 24, "#ffffff", bold=True)
    d.text(84, 865, "Record version, device, conditions and outcome. An offline device cannot pass an audible test.", 18, "#dbe8fa")
    return d.save("acceptance-targets.svg")


def bluetooth():
    d = Diagram(780, "A tracker is a consumer, not another proxy",
                "A beacon broadcasts advertisements. The Dot radio receives them, the controller exposes an "
                "encrypted BLE proxy endpoint and Home Assistant Bluetooth distributes the observations to "
                "iBeacon Tracker or other integrations. The voice endpoint is enrolled separately.",
                "04 / BLUETOOTH ROLES", "Follow the data from a nearby transmitter to a Home Assistant entity")
    d.edge("M290 270 H326")
    d.edge("M580 270 H616")
    d.edge("M900 270 H936")
    d.edge("M1080 370 V444")
    d.card(60, 180, 230, 190, "amber", "TRANSMITTER", "BLE beacon", ["Broadcasts", "advertisements.", "No pairing implied."])
    d.card(330, 180, 250, 190, "violet", "PHYSICAL RADIO", "Echo Dot", ["Receives nearby", "BLE advertisements.", "Radio coverage matters."])
    d.card(620, 180, 280, 190, "teal", "CONTROLLER ENDPOINT", "BLE proxy", ["Separate assigned port", "and Noise encryption key.", "Enroll with ESPHome."])
    d.card(940, 180, 280, 190, "blue", "HA ROUTING", "Bluetooth", ["Receives observations", "from configured scanners.", "Feeds integrations."])
    d.card(850, 448, 370, 202, "rose", "CONSUMER INTEGRATION", "iBeacon Tracker", ["Recognizes supported beacon data.", "Can create tracking entities.", "Does not add another radio."])
    d.rect(60, 448, 730, 202, "#f0ebff")
    d.text(84, 488, "COUNT THE RIGHT THING", 14, "#6d4ad1", bold=True)
    d.lines(84, 528, ["One Dot can expose voice and BLE endpoints: two different jobs.", "A BLE consumer is software using received observations.", "Adding iBeacon Tracker alone does not create a nearby beacon.", "Remove obsolete entries only after the replacement works."], size=18, gap=29)
    d.text(60, 709, "Troubleshoot in order: transmitter → radio → proxy connection → HA observations → consumer support.", 18)
    return d.save("bluetooth-roles.svg")


if __name__ == "__main__":
    for render in (journey, request_flow, acceptance, bluetooth):
        print(render().name)
