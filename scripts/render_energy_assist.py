#!/usr/bin/env python3
"""Render read-only Russian IGW intents for the originating HA Assist session."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

FALLBACK = "Сейчас не удалось получить достоверную энергетическую сводку. Попробуйте позже."
REPORTS = {
    "status": ("EchoEnergyStatus", [
        "[какая] [сейчас] энергетическая сводка",
        "[расскажи] [мне] [про] [нашу] энергетику",
        "[расскажи] [мне] [про] состояние энергосистемы",
    ]),
    "battery": ("EchoEnergyBattery", [
        "сколько [сейчас] заряда [в аккумуляторе]",
        "[какой] [сейчас] заряд (аккумулятора|батареи)",
    ]),
    "solar": ("EchoEnergySolar", [
        "[какая] [сейчас] солнечная мощность",
        "сколько [сейчас] (дают|вырабатывают) солнечные панели",
    ]),
    "solar_today": ("EchoEnergySolarToday", [
        "сколько [энергии] солнце выработало сегодня",
        "[какая] [сегодня] солнечная выработка [за сегодня]",
        "сколько [энергии] выработали солнечные панели [за] сегодня",
    ]),
    "alarms": ("EchoEnergyAlarms", [
        "есть ли аварии [в энергосистеме]",
        "[расскажи] [про] аварии энергосистемы",
    ]),
    "flow": ("EchoEnergyFlow", [
        "что [сейчас] с [электрической] сетью",
        "[расскажи] [про] потоки энергии",
        "куда [сейчас] идёт энергия",
    ]),
}

# Rendered by HA exactly once. Gateway text is data, never a second template.
SPEECH_TEMPLATE = """{%- set requested = report_key | default('') -%}
{%- set response = igw_response | default({}, true) -%}
{%- set body = response.get('content') if response is mapping else none -%}
{%- set reports = body.get('reports') if body is mapping else none -%}
{%- set report = reports.get(requested) if reports is mapping and requested is string else none -%}
{%- set generated = body.get('generated_at') if body is mapping else none -%}
{%- set metrics = body.get('metrics') if body is mapping else none -%}
{%- set text = report.get('text') if report is mapping else none -%}
{%- set brief = report.get('brief_text') if report is mapping else none -%}
{%- if requested == 'status' and brief is string and brief | trim | length > 0 -%}
  {%- set text = brief -%}
{%- endif -%}
{%- set safe = namespace(text=true) -%}
{%- if text is string -%}
  {%- for character in text -%}
    {%- if character < ' ' and character not in '\\n\\t\\r' -%}
      {%- set safe.text = false -%}
    {%- endif -%}
  {%- endfor -%}
{%- endif -%}
{%- if response is mapping and response.get('status') == 200
    and body is mapping and body.get('locale') == 'ru'
    and body.get('schema_version') is integer and body.get('schema_version') == 1
    and body.get('mqtt_connected') is boolean
    and generated is number and generated is not boolean
    and -5 <= as_timestamp(now()) - generated <= maximum_age
    and metrics is mapping
    and 'battery_soc' in metrics and 'solar_power' in metrics and 'solar_today' in metrics
    and requested in ['battery', 'solar', 'solar_today', 'status', 'alarms', 'flow']
    and report is mapping
    and report.get('status') in ['fresh', 'stale', 'unavailable', 'unconfigured']
    and (report.get('status') != 'fresh' or body.get('mqtt_connected') == true)
    and text is string and safe.text and 0 < text | trim | length <= 900 -%}
  {{- text | trim -}}
{%- else -%}
  {{- fallback -}}
{%- endif -%}"""

INSTALL = """# Install Russian Assist energy reports

This package requires IGW's `GET /v1/energy?locale=ru` response, including
`locale: ru`. It works with any existing Russian Assist pipeline; it does not
change its STT, conversation model, TTS or satellite selection.

1. Back up HA's configuration and existing secrets. Copy the rendered package
   and `custom_sentences/ru/igw_energy.yaml` to the corresponding HA directories.
   Enable packages if needed. Do not overwrite another file with the same name.
2. Set `igw_assist_energy_url` in HA's secrets.yaml to the trusted IGW endpoint
   ending in `/v1/energy?locale=ru`. Use verified HTTPS, or the trusted private
   cluster route. Use a direct endpoint without redirects. Set
   `igw_assist_energy_authorization` to `Bearer ` followed by a scoped IGW read
   token. Never use a full HA token or expose the endpoint/token in voice slots.
3. Run HA configuration validation. If REST Command, Script and Intent Script
   are already loaded, reload them and Conversation; otherwise restart HA after
   validation. Keep 'Prefer handling commands locally' enabled in the pipeline.
4. Test the Russian sentences in Assist's text UI first. Verify stale-data and
   gateway-unavailable replies, then test from each satellite. Responses return
   to the originating conversation; these intents do not call Cast or a fixed
   media player and cannot change home state.

The helper script uses parallel mode with four slots and stores no traces. It
returns a generic Russian error for an invalid, wrong-language or old envelope.
Gateway warnings in valid reports are preserved. Reports over 900 characters
are refused rather than truncated. This keeps the current speech pipeline's
bound and avoids dropping warnings. The gateway remains responsible for report
semantics, source freshness, numbers and units. There is no historical database
or LLM inside this package.

Rollback: remove only these two installed files, reload the same integrations
(or restart if required), and remove the two secrets if nothing else uses them.
Existing Google display scripts, pipelines and media routing remain intact.
"""


def configuration(maximum_age: int = 30) -> tuple[dict, dict]:
    """Build config objects without credentials or environment-specific addresses."""
    if type(maximum_age) is not int or not 5 <= maximum_age <= 120:
        raise ValueError("maximum_age must be an integer from 5 to 120 seconds")
    package = {
        "logger": {"logs": {"homeassistant.components.rest_command": "warning"}},
        "rest_command": {"igw_assist_energy_snapshot": {
            "url": "SECRET_URL", "method": "GET", "timeout": 10, "verify_ssl": True,
            "headers": {"Authorization": "SECRET_AUTH", "Accept": "application/json",
                        "Cache-Control": "no-cache, no-store"},
        }},
        "script": {"igw_assist_energy_report": {
            "alias": "IGW Assist energy report (read only)",
            "description": "Return one validated Russian IGW report; no playback or device actions.",
            "mode": "parallel", "max": 4, "max_exceeded": "warning",
            "trace": {"stored_traces": 0},
            "fields": {"report_key": {"required": True,
                "selector": {"select": {"options": list(REPORTS)}}}},
            "variables": {"maximum_age": maximum_age, "fallback": FALLBACK},
            "sequence": [
                {"variables": {"igw_response": {}}},
                {"action": "rest_command.igw_assist_energy_snapshot",
                 "response_variable": "igw_response", "continue_on_error": True},
                {"variables": {"result": {"speech": SPEECH_TEMPLATE}}},
                {"stop": "Return the validated report to the invoking conversation.",
                 "response_variable": "result"},
            ],
        }},
        "intent_script": {},
    }
    sentences = {"language": "ru", "intents": {}}
    for key, (intent, phrases) in REPORTS.items():
        package["intent_script"][intent] = {
            "description": "Read the IGW " + key + " report in Russian.",
            "mode": "parallel",
            "action": [
                {"action": "script.igw_assist_energy_report", "data": {"report_key": key},
                 "response_variable": "report"},
                {"stop": "Return speech in the original Assist session.",
                 "response_variable": "report"},
            ],
            "speech": {"text": "{{ action_response.speech }}"},
        }
        sentences["intents"][intent] = {"data": [{"sentences": phrases}]}
    return package, sentences


def render(output: Path, maximum_age: int = 30) -> None:
    package, sentences = configuration(maximum_age)
    # JSON is a YAML subset. Only these two fixed strings become YAML tags.
    payload = json.dumps(package, ensure_ascii=False, indent=2)
    payload = payload.replace('"SECRET_URL"', "!secret igw_assist_energy_url")
    payload = payload.replace('"SECRET_AUTH"', "!secret igw_assist_energy_authorization")
    output.mkdir(parents=True, exist_ok=False)
    (output / "packages").mkdir()
    (output / "custom_sentences" / "ru").mkdir(parents=True)
    (output / "packages" / "igw_energy_assist.yaml").write_text(payload + "\n", encoding="utf-8")
    (output / "custom_sentences" / "ru" / "igw_energy.yaml").write_text(
        json.dumps(sentences, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "INSTALL.md").write_text(INSTALL, encoding="utf-8")


def main() -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--output", type=Path, required=True, help="New staging directory; never write directly into HA")
    cli.add_argument("--maximum-age", type=int, default=30)
    args = cli.parse_args()
    try:
        render(args.output, args.maximum_age)
    except (OSError, ValueError) as exc:
        cli.exit(1, f"Cannot render Assist configuration: {exc}\n")
    print("Rendered Assist package, Russian sentences and INSTALL.md; no live configuration changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
