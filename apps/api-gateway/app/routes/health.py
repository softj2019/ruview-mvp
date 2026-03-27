import os

import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()

SIGNAL_ADAPTER_URL = os.getenv("SIGNAL_ADAPTER_URL", "http://localhost:8001")


@router.get("/health")
async def health_check():
    return {"status": "ok", "service": "api-gateway"}


@router.get("/ready")
async def readiness_probe():
    """Readiness probe — 200 when signal-adapter is reachable, 503 otherwise."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{SIGNAL_ADAPTER_URL}/health")
            if resp.is_success:
                return {"status": "ready", "signal_adapter": "ok"}
            detail = f"signal-adapter returned HTTP {resp.status_code}"
    except httpx.RequestError as exc:
        detail = f"signal-adapter unreachable: {exc}"

    return JSONResponse(
        status_code=503,
        content={"status": "not_ready", "detail": detail},
    )
