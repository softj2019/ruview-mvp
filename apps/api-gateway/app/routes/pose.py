"""
Pose estimation API endpoints — Phase 4-7
Proxies requests to signal-adapter (localhost:8001).
"""

import os
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter()

SIGNAL_ADAPTER_URL = os.getenv("SIGNAL_ADAPTER_URL", "http://localhost:8001")


# ---------------------------------------------------------------------------
# Auth helper — mirrors signal-adapter verify_api_key pattern
# ---------------------------------------------------------------------------

async def verify_api_key(authorization: str | None = Header(None)):
    """Bearer token check. Skipped when RUVIEW_API_KEY is not set."""
    api_key = os.getenv("RUVIEW_API_KEY")
    if not api_key:
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    if authorization[7:] != api_key:
        raise HTTPException(status_code=403, detail="Invalid API key")


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class PoseAnalyzeRequest(BaseModel):
    zone_ids: Optional[List[str]] = Field(None, description="Zones to analyze (all if omitted)")
    confidence_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    max_persons: Optional[int] = Field(None, ge=1, le=50)
    include_keypoints: bool = True
    include_segmentation: bool = False


class PersonPose(BaseModel):
    person_id: str
    confidence: float
    bounding_box: Dict[str, float]
    keypoints: Optional[List[Dict[str, Any]]] = None
    segmentation: Optional[Dict[str, Any]] = None
    zone_id: Optional[str] = None
    activity: Optional[str] = None
    timestamp: datetime


class PoseAnalyzeResponse(BaseModel):
    timestamp: datetime
    frame_id: str
    persons: List[PersonPose]
    zone_summary: Dict[str, int]
    processing_time_ms: float
    metadata: Dict[str, Any] = {}


class ModelLoadRequest(BaseModel):
    model_name: str = Field(..., description="Model identifier to load")
    config: Optional[Dict[str, Any]] = None


class ModelUnloadRequest(BaseModel):
    model_name: str = Field(..., description="Model identifier to unload")


# ---------------------------------------------------------------------------
# Internal proxy helper
# ---------------------------------------------------------------------------

async def _proxy_get(path: str, params: dict | None = None) -> Any:
    """Forward a GET request to signal-adapter and return parsed JSON."""
    url = f"{SIGNAL_ADAPTER_URL}{path}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)
    except httpx.RequestError as exc:
        logger.error("signal-adapter unreachable at %s: %s", url, exc)
        raise HTTPException(status_code=503, detail="signal-adapter unavailable")


async def _proxy_post(path: str, body: dict | None = None) -> Any:
    """Forward a POST request to signal-adapter and return parsed JSON."""
    url = f"{SIGNAL_ADAPTER_URL}{path}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=body or {})
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)
    except httpx.RequestError as exc:
        logger.error("signal-adapter unreachable at %s: %s", url, exc)
        raise HTTPException(status_code=503, detail="signal-adapter unavailable")


# ---------------------------------------------------------------------------
# Pose endpoints
# ---------------------------------------------------------------------------

@router.post("/analyze", response_model=PoseAnalyzeResponse)
async def analyze_pose(request: PoseAnalyzeRequest):
    """POST /api/v1/pose/analyze — CSI 데이터 포즈 분석."""
    try:
        data = await _proxy_post("/api/pose/analyze", request.model_dump())
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("pose analyze error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    # Normalise / provide sensible defaults when signal-adapter omits fields
    now = datetime.now(timezone.utc)
    data.setdefault("timestamp", now.isoformat())
    data.setdefault("frame_id", str(uuid.uuid4()))
    data.setdefault("persons", [])
    data.setdefault("zone_summary", {})
    data.setdefault("processing_time_ms", 0.0)
    data.setdefault("metadata", {})

    # Coerce timestamp string → datetime for Pydantic
    if isinstance(data["timestamp"], str):
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])

    for p in data["persons"]:
        if isinstance(p.get("timestamp"), str):
            p["timestamp"] = datetime.fromisoformat(p["timestamp"])
        p.setdefault("bounding_box", {"x": 0, "y": 0, "w": 0, "h": 0})
        p.setdefault("confidence", 0.0)
        p.setdefault("person_id", str(uuid.uuid4()))

    return PoseAnalyzeResponse(**data)


@router.get("/zone-occupancy/{zone_id}")
async def zone_occupancy(zone_id: str):
    """GET /api/v1/pose/zone-occupancy/{zone_id} — 존별 점유율."""
    data = await _proxy_get(f"/api/pose/zones/{zone_id}/occupancy")
    data.setdefault("zone_id", zone_id)
    data.setdefault("current_occupancy", 0)
    data.setdefault("persons", [])
    data.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
    return data


@router.get("/zones-summary")
async def zones_summary():
    """GET /api/v1/pose/zones-summary — 전체 존 요약."""
    data = await _proxy_get("/api/pose/zones/summary")
    data.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
    data.setdefault("total_persons", 0)
    data.setdefault("zones", [])
    data.setdefault("active_zones", 0)
    return data


@router.get("/activities")
async def get_activities(
    zone_id: Optional[str] = Query(None, description="존 ID 필터"),
    limit: int = Query(10, ge=1, le=100),
):
    """GET /api/v1/pose/activities — 최근 활동 목록."""
    params: dict = {"limit": limit}
    if zone_id:
        params["zone_id"] = zone_id
    data = await _proxy_get("/api/pose/activities", params=params)
    data.setdefault("activities", [])
    data.setdefault("total_count", len(data.get("activities", [])))
    data.setdefault("zone_id", zone_id)
    return data


@router.post("/calibrate")
async def calibrate(
    background_tasks: BackgroundTasks,
    _auth=Depends(verify_api_key),
):
    """POST /api/v1/pose/calibrate — 캘리브레이션 시작 (Bearer 인증 필요)."""
    data = await _proxy_post("/api/pose/calibrate")
    data.setdefault("status", "started")
    data.setdefault("estimated_duration_minutes", 5)
    data.setdefault("message", "Calibration process started")
    return data


@router.get("/calibration-status")
async def calibration_status(_auth=Depends(verify_api_key)):
    """GET /api/v1/pose/calibration-status — 캘리브레이션 상태."""
    data = await _proxy_get("/api/pose/calibration/status")
    data.setdefault("is_calibrating", False)
    data.setdefault("progress_percent", 0)
    data.setdefault("last_calibration", None)
    return data


@router.get("/stats")
async def pose_stats(
    hours: int = Query(24, ge=1, le=168, description="분석할 시간 범위"),
):
    """GET /api/v1/pose/stats — 포즈 통계."""
    data = await _proxy_get("/api/pose/stats", params={"hours": hours})
    data.setdefault("statistics", {})
    return data


# ---------------------------------------------------------------------------
# Model management — separate router, mounted at /api/v1/models in main.py
# ---------------------------------------------------------------------------

models_router = APIRouter()


@models_router.get("")
async def list_models():
    """GET /api/v1/models — 모델 목록."""
    data = await _proxy_get("/api/models")
    data.setdefault("models", [])
    return data


@models_router.post("/load")
async def load_model(request: ModelLoadRequest, _auth=Depends(verify_api_key)):
    """POST /api/v1/models/load — 모델 로드."""
    data = await _proxy_post("/api/models/load", request.model_dump())
    data.setdefault("status", "loaded")
    return data


@models_router.post("/unload")
async def unload_model(request: ModelUnloadRequest, _auth=Depends(verify_api_key)):
    """POST /api/v1/models/unload — 모델 언로드."""
    data = await _proxy_post("/api/models/unload", request.model_dump())
    data.setdefault("status", "unloaded")
    return data


@models_router.get("/active")
async def active_models():
    """GET /api/v1/models/active — 활성 모델."""
    data = await _proxy_get("/api/models/active")
    data.setdefault("active_models", [])
    return data
