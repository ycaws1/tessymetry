"""
Streamlit dashboard for Tessymetry telemetry (reads Supabase directly).

Run from project root:
  streamlit run streamlit_app.py

Requires the same env vars as the FastAPI app (.env with SUPABASE_URL and SUPABASE_SECRET_KEY).
"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.telemetry_data import fetch_events_chronological, fetch_vins

# --- shared helpers (aligned with app/routes/api.py) ---

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
)


def _to_float(v: Any) -> float | None:
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        try:
            return float(v.strip())
        except ValueError:
            return None
    return None


@st.cache_data(ttl=15, show_spinner="Loading vehicles…")
def load_vins() -> list[str]:
    return fetch_vins()


@st.cache_data(ttl=15, show_spinner="Loading events…")
def load_events(vin: str, limit: int) -> list[dict[str, Any]]:
    return fetch_events_chronological(vin, limit)


def events_to_dataframe(rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    meta = pd.DataFrame(
        [
            {
                "id": r.get("id"),
                "vin": r.get("vin"),
                "event_created_at": r.get("event_created_at"),
                "received_at": r.get("received_at"),
                "format": r.get("format"),
            }
            for r in rows
        ]
    )
    flat = pd.json_normalize([r.get("flattened") or {} for r in rows])
    if not flat.empty:
        flat.columns = [f"field_{c}" for c in flat.columns]
    out = pd.concat([meta.reset_index(drop=True), flat.reset_index(drop=True)], axis=1)
    out["payload_json"] = [json.dumps(r.get("payload"), ensure_ascii=False)[:2000] for r in rows]
    return out


def numeric_columns(df: pd.DataFrame) -> list[str]:
    cols: list[str] = []
    for c in df.columns:
        if c.startswith("field_") and df[c].apply(lambda x: _to_float(x) is not None).any():
            key = c.removeprefix("field_")
            cols.append(key)
    ordered = [k for k in _PREFERRED_NUMERIC_KEYS if k in cols]
    for k in sorted(cols):
        if k not in ordered:
            ordered.append(k)
    return ordered


def main() -> None:
    st.set_page_config(page_title="Tessymetry", layout="wide")
    st.title("Tessymetry")
    st.caption("Telemetry from Supabase (`telemetry_events`)")

    try:
        from app.config import get_settings

        get_settings()
    except Exception as e:
        st.error(
            "Could not load configuration. Create a `.env` with `SUPABASE_URL` and "
            "`SUPABASE_SECRET_KEY` (or `SUPABASE_SERVICE_ROLE_KEY`), then restart."
        )
        st.code(str(e))
        return

    vins = load_vins()
    if not vins:
        st.warning("No rows in `telemetry_events` yet. Send webhook data first.")
        return

    with st.sidebar:
        st.header("Filters")
        vin = st.selectbox("Vehicle (VIN)", vins, index=0)
        limit = st.slider("Max events to load", min_value=50, max_value=10000, value=2000, step=50)
        if st.button("Refresh data"):
            st.cache_data.clear()
            st.rerun()

    rows = load_events(vin, limit)
    if not rows:
        st.info("No events for this VIN.")
        return

    df = events_to_dataframe(rows)
    df["event_created_at"] = pd.to_datetime(df["event_created_at"], utc=True, errors="coerce")
    df["received_at"] = pd.to_datetime(df["received_at"], utc=True, errors="coerce")

    latest = rows[-1]
    st.subheader("Latest event")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Events loaded", len(rows))
    c2.metric("Format", str(latest.get("format", "—")))
    c3.metric("Event time (UTC)", str(latest.get("event_created_at", "—"))[:19])
    c4.metric("Received (UTC)", str(latest.get("received_at", "—"))[:19])

    with st.expander("Latest flattened fields (full JSON)", expanded=False):
        st.json(latest.get("flattened") or {})

    nums = numeric_columns(df)
    tab_chart, tab_table, tab_raw = st.tabs(["Time series", "Full table", "Raw payloads"])

    with tab_chart:
        if not nums:
            st.info("No numeric fields found in `flattened` for charting.")
        else:
            default_pick = [k for k in nums if k in _PREFERRED_NUMERIC_KEYS][:4]
            if not default_pick:
                default_pick = nums[:4]
            picked = st.multiselect("Metrics to plot", nums, default=default_pick)
            if picked:
                fig = go.Figure()
                for name in picked:
                    col = f"field_{name}"
                    y = df[col].map(_to_float)
                    fig.add_trace(
                        go.Scatter(
                            x=df["event_created_at"],
                            y=y,
                            name=name,
                            mode="lines",
                            connectgaps=False,
                        )
                    )
                fig.update_layout(
                    height=480,
                    margin=dict(l=40, r=20, t=40, b=40),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02),
                    xaxis_title="event_created_at (UTC)",
                )
                st.plotly_chart(fig, use_container_width=True)

    with tab_table:
        display_df = df.drop(columns=["payload_json"], errors="ignore")
        st.dataframe(display_df, use_container_width=True, height=520)
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download CSV (truncated payload column)",
            data=csv,
            file_name=f"tessymetry_{vin}_{len(df)}.csv",
            mime="text/csv",
        )

    with tab_raw:
        st.caption("Full `payload` JSON per event (expanders: newest first).")
        for i, r in enumerate(reversed(rows)):
            with st.expander(f"{r.get('event_created_at')} — {r.get('id')}", expanded=(i == 0)):
                st.json(r.get("payload"))


if __name__ == "__main__":
    main()
