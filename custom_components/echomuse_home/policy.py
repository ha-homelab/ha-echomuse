"""Bounded, deterministic policy shared by the local home tools and tests."""
from datetime import datetime, timedelta
import math
import re

DOMAIN = "echomuse_home"
READ_DOMAINS = frozenset({
    "sensor", "binary_sensor", "light", "switch", "climate", "cover", "fan",
    "humidifier", "water_heater", "media_player", "vacuum", "lock", "siren",
    "alarm_control_panel", "weather", "sun", "scene", "script", "automation",
    "button", "number", "select", "input_boolean", "input_number", "input_select",
    "counter", "timer", "update", "calendar", "assist_satellite",
})
ATTRIBUTES = frozenset({
    "unit_of_measurement", "device_class", "state_class", "temperature",
    "current_temperature", "current_humidity", "humidity", "hvac_action",
    "hvac_modes", "min_temp", "max_temp", "target_temp_step", "brightness",
    "color_mode", "current_position", "percentage", "volume_level",
    "is_volume_muted", "battery_level", "supported_features", "speed_count",
    "options", "min", "max", "step", "preset_modes", "preset_mode",
    "min_humidity", "max_humidity", "target_humidity",
})
WORDS = {
    "обогрев": "heater", "хитер": "heater", "отоплен": "heater",
    "кухн": "kitchen", "спальн": "bedroom", "гостин": "living",
    "столов": "dining", "гараж": "garage", "ванн": "bathroom",
    "коридор": "hallway", "свет": "light", "ламп": "lamp",
    "розет": "switch", "штор": "curtain", "пылесос": "vacuum",
    "температур": "temperature", "влажност": "humidity", "мощност": "power",
    "энерги": "energy", "заряд": "battery", "солнеч": "solar",
    "напряжен": "voltage", "двер": "door", "окн": "window",
    "перв": "one", "втор": "two", "трет": "three", "четверт": "four",
    "вентилятор": "fan", "подсвет": "backlight", "воздух": "air",
    "очистител": "purifier", "движен": "motion", "протеч": "moisture",
    "аккумулятор": "battery", "занавес": "curtain", "термостат": "thermostat",
    "потреблен": "energy", "сегодня": "today", "вчера": "yesterday",
    "1": "one", "2": "two", "3": "three", "4": "four",
}
STOP_WORDS = {"в", "на", "у", "с", "со", "и", "the", "in", "of", "для", "все", "всех"}


def tokens(value):
    """Normalize search words, including common Russian inflections."""
    result = []
    for word in re.findall(r"[\w]+", str(value).lower().replace("ё", "е").replace("_", " ")):
        if word in STOP_WORDS:
            continue
        result.append(next((v for k, v in WORDS.items() if word == k or (len(k) > 1 and word.startswith(k))), word))
    return set(result)


def score(query, names):
    wanted = tokens(query)
    available = tokens(" ".join(names).replace("_", " "))
    if not wanted:
        return 1
    matched = sum(any(a == w or (len(w) >= 4 and a.startswith(w)) for a in available) for w in wanted)
    return matched * 10 if matched == len(wanted) else 0


def control_request(entity_id, operation, value, attributes):
    """Return one supported HA service call. Never accept arbitrary services."""
    domain = entity_id.split(".", 1)[0]
    service = None
    data = {"entity_id": entity_id}
    if operation in {"turn_on", "turn_off"} and domain in {"light", "switch", "fan", "humidifier", "climate", "input_boolean"}:
        service = operation
    elif operation == "set_brightness" and domain == "light":
        data["brightness_pct"] = bounded_number(value, 0, 100)
        service = "turn_on"
    elif operation == "set_temperature" and domain in {"climate", "water_heater"}:
        lower, upper = attributes.get("min_temp"), attributes.get("max_temp")
        if lower is None or upper is None:
            raise ValueError("Device temperature bounds are unavailable")
        data["temperature"] = bounded_number(value, lower, upper)
        service = "set_temperature"
    elif operation == "set_hvac_mode" and domain == "climate":
        if not isinstance(value, str) or value not in attributes.get("hvac_modes", []):
            raise ValueError("Select a supported HVAC mode")
        data["hvac_mode"] = value
        service = "set_hvac_mode"
    elif operation == "set_value" and domain in {"number", "input_number"}:
        lower, upper = attributes.get("min"), attributes.get("max")
        if lower is None or upper is None:
            raise ValueError("Device numeric bounds are unavailable")
        data["value"] = bounded_number(value, lower, upper)
        service = "set_value"
    elif operation == "select_option" and domain in {"select", "input_select"}:
        if not isinstance(value, str) or value not in attributes.get("options", []):
            raise ValueError("Select one of the reported options")
        data["option"] = value
        service = "select_option"
    elif operation == "set_humidity" and domain == "humidifier":
        data["humidity"] = bounded_number(value, attributes.get("min_humidity", 0), attributes.get("max_humidity", 100))
        service = "set_humidity"
    elif operation in {"open", "close", "stop"} and domain == "cover":
        service = operation + "_cover"
    elif operation == "set_position" and domain == "cover":
        data["position"] = bounded_number(value, 0, 100)
        service = "set_cover_position"
    elif operation == "set_percentage" and domain == "fan":
        data["percentage"] = bounded_number(value, 0, 100)
        service = "set_percentage"
    elif domain == "vacuum" and operation in {"start", "pause", "stop", "return_to_base"}:
        service = operation
    elif domain == "media_player" and operation in {"pause", "stop", "play"}:
        service = "media_" + operation
    elif domain == "media_player" and operation == "set_volume":
        service = "volume_set"
        data["volume_level"] = bounded_number(value, 0, 100) / 100
    elif domain in {"scene", "script"} and operation == "activate":
        service = "turn_on"
    if service is None:
        raise ValueError("Unsupported operation for this device")
    return domain, service, data


def bounded_number(value, lower, upper):
    if type(value) not in (int, float) or not math.isfinite(value) or not lower <= value <= upper:
        raise ValueError(f"Value must be a finite number from {lower} to {upper}")
    return value


def period_bounds(period, now, start=None, end=None):
    """Calendar periods use HA's timezone, including DST, never a fixed offset."""
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "today":
        return midnight, now
    if period == "yesterday":
        return midnight - timedelta(days=1), midnight
    if period == "last_24_hours":
        # Timestamp arithmetic preserves 24 elapsed hours across DST changes.
        return datetime.fromtimestamp(now.timestamp() - 86400, now.tzinfo), now
    if period == "this_week":
        return midnight - timedelta(days=midnight.weekday()), now
    if period == "this_month":
        return midnight.replace(day=1), now
    if period == "custom":
        a, b = datetime.fromisoformat(start), datetime.fromisoformat(end)
        if a.tzinfo is None:
            a = a.replace(tzinfo=now.tzinfo)
        if b.tzinfo is None:
            b = b.replace(tzinfo=now.tzinfo)
        if a >= b or b > now or b - a > timedelta(days=366):
            raise ValueError("Custom period must be in the past and at most 366 days")
        return a, b
    raise ValueError("Unsupported statistics period")
