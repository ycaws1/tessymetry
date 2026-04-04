"""Normalize Tesla / Teslemetry webhook bodies to a flat dict for charts and filters."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any


def _unwrap_tesla_value(value: dict[str, Any]) -> Any:
    if not isinstance(value, dict):
        return value
    if "locationValue" in value:
        lv = value["locationValue"]
        if isinstance(lv, dict):
            return {"lat": lv.get("latitude"), "lng": lv.get("longitude")}
        return lv
    for k in ("stringValue", "intValue", "floatValue", "doubleValue", "boolValue"):
        if k in value:
            return value[k]
    if "invalid" in value and value.get("invalid"):
        return None
    return value


def flatten_raw_array(data: list[dict[str, Any]] | None) -> dict[str, Any]:
    if not data:
        return {}
    out: dict[str, Any] = {}
    for item in data:
        key = item.get("key")
        if not key:
            continue
        val = item.get("value")
        if isinstance(val, dict):
            out[str(key)] = _unwrap_tesla_value(val)
        else:
            out[str(key)] = val
    return out


def parse_event_time(created_at: str | None) -> datetime:
    if not created_at:
        return datetime.now(timezone.utc)
    s = created_at.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return datetime.now(timezone.utc)


def splunk_time_to_iso(t: float | int) -> datetime:
    try:
        sec = float(t)
        return datetime.fromtimestamp(sec, tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return datetime.now(timezone.utc)


def json_safe(obj: Any) -> Any:
    if obj is None:
        return None
    if isinstance(obj, (str, int, bool)):
        return obj
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [json_safe(x) for x in obj]
    return str(obj)


def detect_and_normalize(body: dict[str, Any]) -> tuple[str, str, datetime, dict[str, Any], dict[str, Any]]:
    """
    Returns: format, vin, event_created_at, original_slice_for_storage, flattened
    """
    if "event" in body and "source" in body and "time" in body:
        vin = str(body.get("source") or "")
        event_at = splunk_time_to_iso(body["time"])
        inner = body.get("event") or {}
        flat = json_safe(inner) if isinstance(inner, dict) else {}
        return "splunk", vin, event_at, body, flat

    vin = str(body.get("vin") or "")
    created = body.get("createdAt")
    event_at = parse_event_time(created) if isinstance(created, str) else datetime.now(timezone.utc)

    data = body.get("data")
    if isinstance(data, dict):
        flat = json_safe(data)
        return "tesla", vin, event_at, body, flat

    if isinstance(data, list):
        flat = json_safe(flatten_raw_array(data))
        return "raw", vin, event_at, body, flat

    return "tesla", vin, event_at, body, {}
