"""Shared Supabase reads for the Streamlit dashboard."""

from __future__ import annotations

from typing import Any

from app.database import get_supabase


def fetch_vins(*, row_limit: int = 8000) -> list[str]:
    client = get_supabase()
    res = (
        client.table("telemetry_events")
        .select("vin")
        .order("received_at", desc=True)
        .limit(row_limit)
        .execute()
    )
    rows = res.data or []
    return sorted({r["vin"] for r in rows if r.get("vin")})


def fetch_events_chronological(vin: str, limit: int) -> list[dict[str, Any]]:
    """Oldest → newest for time-series charts."""
    client = get_supabase()
    res = (
        client.table("telemetry_events")
        .select("id,vin,event_created_at,received_at,format,payload,flattened")
        .eq("vin", vin)
        .order("event_created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return list(reversed(res.data or []))
