from __future__ import annotations

import json
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from postgrest.exceptions import APIError

from app.database import get_supabase
from app.flatten import detect_and_normalize

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["webhook"])


def _authorization_token(authorization: str | None) -> str | None:
    """Teslemetry may send `Bearer <token>` or the raw secret as the header value."""
    if not authorization:
        return None
    s = authorization.strip()
    if s.lower().startswith("bearer "):
        return s[7:].strip()
    return s


async def verify_webhook_auth(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    from app.config import get_settings

    secret = get_settings().webhook_secret
    if not secret:
        return
    token = _authorization_token(authorization)
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Missing Authorization header (use Bearer <secret> or paste secret as the header value).",
        )
    if token != secret:
        raise HTTPException(status_code=403, detail="Invalid webhook token")


@router.post("/teslemetry")
async def receive_teslemetry(
    request: Request,
    _: Annotated[None, Depends(verify_webhook_auth)],
) -> dict:
    raw = await request.body()
    try:
        body = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.warning("Invalid JSON webhook body: %s", e)
        raise HTTPException(status_code=400, detail="Body must be JSON") from e

    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="JSON object expected")

    fmt, vin, event_at, payload, flattened = detect_and_normalize(body)
    if not vin:
        raise HTTPException(status_code=422, detail="Could not determine VIN from payload")

    row = {
        "vin": vin,
        "event_created_at": event_at.isoformat(),
        "format": fmt,
        "payload": payload,
        "flattened": flattened,
    }

    try:
        supabase = get_supabase()
        res = supabase.table("telemetry_events").insert(row).execute()
    except APIError as e:
        logger.error(
            "Supabase insert failed: %s (code=%s details=%s hint=%s)",
            e.message,
            e.code,
            e.details,
            e.hint,
        )
        raise HTTPException(
            status_code=502,
            detail=e.message or "Storage error",
        ) from e
    except Exception as e:
        logger.exception("Supabase insert failed: %s", e)
        raise HTTPException(status_code=502, detail="Storage error") from e

    inserted = res.data[0] if res.data else {}
    logger.info(
        "Webhook received: vin=%s format=%s event_id=%s",
        vin,
        fmt,
        inserted.get("id"),
    )
    return {"ok": True, "id": inserted.get("id"), "vin": vin, "format": fmt}
