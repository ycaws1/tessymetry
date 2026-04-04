from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.database import get_supabase

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["api"])

# Fields commonly streamed; used to order legend / default series selection.
_PREFERRED_NUMERIC_KEYS = (
    "VehicleSpeed",
    "Soc",
    "BatteryLevel",
    "Odometer",
    "InsideTemp",
    "OutsideTemp",
    "PackVoltage",
    "PackCurrent",
    "LifetimeEnergyUsed",
    "EstBatteryRange",
    "IdealBatteryRange",
)


def _to_float(v: Any) -> float | None:
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        try:
            return float(v.strip())
        except ValueError:
            return None
    return None


@router.get("/vehicles")
async def list_vehicles() -> dict:
    try:
        supabase = get_supabase()
        res = (
            supabase.table("telemetry_events")
            .select("vin")
            .order("received_at", desc=True)
            .limit(5000)
            .execute()
        )
    except Exception as e:
        logger.exception("vehicles query failed: %s", e)
        raise HTTPException(status_code=502, detail="Database error") from e

    rows = res.data or []
    vins = sorted({r["vin"] for r in rows if r.get("vin")})
    return {"vins": vins}


@router.get("/telemetry/{vin}")
async def telemetry_series(
    vin: str,
    limit: int = Query(default=300, ge=1, le=2000),
) -> dict:
    try:
        supabase = get_supabase()
        res = (
            supabase.table("telemetry_events")
            .select("event_created_at,flattened")
            .eq("vin", vin)
            .order("event_created_at", desc=True)
            .limit(limit)
            .execute()
        )
    except Exception as e:
        logger.exception("telemetry query failed: %s", e)
        raise HTTPException(status_code=502, detail="Database error") from e

    rows = list(reversed(res.data or []))
    series_keys: set[str] = set()

    for r in rows:
        flat = r.get("flattened") or {}
        if not isinstance(flat, dict):
            continue
        for k, v in flat.items():
            if _to_float(v) is not None:
                series_keys.add(str(k))

    ordered_keys = [k for k in _PREFERRED_NUMERIC_KEYS if k in series_keys]
    for k in sorted(series_keys):
        if k not in ordered_keys:
            ordered_keys.append(k)

    points: list[dict[str, Any]] = []
    for r in rows:
        flat = r.get("flattened") or {}
        if not isinstance(flat, dict):
            flat = {}
        t = r.get("event_created_at")
        values: dict[str, float] = {}
        for k in ordered_keys:
            if k in flat:
                fv = _to_float(flat[k])
                if fv is not None:
                    values[k] = fv
        points.append({"t": t, "values": values})

    return {
        "vin": vin,
        "series_keys": ordered_keys,
        "points": points,
        "count": len(points),
    }


@router.get("/latest/{vin}")
async def latest_snapshot(vin: str) -> dict:
    try:
        supabase = get_supabase()
        res = (
            supabase.table("telemetry_events")
            .select("event_created_at,flattened,format,received_at,payload")
            .eq("vin", vin)
            .order("event_created_at", desc=True)
            .limit(1)
            .execute()
        )
    except Exception as e:
        logger.exception("latest query failed: %s", e)
        raise HTTPException(status_code=502, detail="Database error") from e

    if not res.data:
        raise HTTPException(status_code=404, detail="No data for VIN")

    row = res.data[0]
    return {
        "vin": vin,
        "event_created_at": row.get("event_created_at"),
        "received_at": row.get("received_at"),
        "format": row.get("format"),
        "flattened": row.get("flattened") or {},
        "payload": row.get("payload"),
    }
