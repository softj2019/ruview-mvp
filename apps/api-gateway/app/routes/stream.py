"""
WebSocket streaming API endpoints — Phase 4-8
WS /api/v1/stream/pose relays the signal-adapter pose stream to clients.
"""

import asyncio
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
import websockets
from fastapi import APIRouter, Depends, Header, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter()

SIGNAL_ADAPTER_URL = os.getenv("SIGNAL_ADAPTER_URL", "http://localhost:8001")
# Convert http(s):// → ws(s):// for WebSocket upstream
_WS_BASE = SIGNAL_ADAPTER_URL.replace("https://", "wss://").replace("http://", "ws://")


# ---------------------------------------------------------------------------
# Auth helper (same pattern as pose.py)
# ---------------------------------------------------------------------------

async def verify_api_key(authorization: str | None = Header(None)):
    api_key = os.getenv("RUVIEW_API_KEY")
    if not api_key:
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    if authorization[7:] != api_key:
        raise HTTPException(status_code=403, detail="Invalid API key")


# ---------------------------------------------------------------------------
# In-memory stream state (process-level singleton)
# ---------------------------------------------------------------------------

class _StreamState:
    def __init__(self):
        self.connected_clients: Dict[str, WebSocket] = {}
        self.start_time: float = time.time()
        self.frame_count: int = 0
        self.last_frame_ts: Optional[float] = None
        self.current_fps: float = 0.0
        self._fps_window: List[float] = []

    def register(self, client_id: str, ws: WebSocket):
        self.connected_clients[client_id] = ws

    def unregister(self, client_id: str):
        self.connected_clients.pop(client_id, None)

    def record_frame(self):
        now = time.time()
        self._fps_window.append(now)
        # Keep only last 30 timestamps for fps calculation
        cutoff = now - 1.0
        self._fps_window = [t for t in self._fps_window if t >= cutoff]
        self.current_fps = len(self._fps_window)
        self.last_frame_ts = now
        self.frame_count += 1

    @property
    def client_count(self) -> int:
        return len(self.connected_clients)

    @property
    def uptime(self) -> float:
        return time.time() - self.start_time


_state = _StreamState()


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class StreamStatusResponse(BaseModel):
    is_active: bool
    connected_clients: int
    current_fps: float
    last_frame_at: Optional[str]
    uptime_seconds: float
    frame_count: int


class FpsRequest(BaseModel):
    fps: int = Field(..., ge=1, le=60, description="목표 FPS")


# ---------------------------------------------------------------------------
# WebSocket relay — pose stream
# ---------------------------------------------------------------------------

@router.websocket("/pose")
async def ws_pose_stream(
    websocket: WebSocket,
    zone_ids: Optional[str] = Query(None, description="쉼표 구분 존 ID"),
    min_confidence: float = Query(0.5, ge=0.0, le=1.0),
    max_fps: int = Query(20, ge=1, le=60),
    token: Optional[str] = Query(None),
):
    """WS /api/v1/stream/pose — signal-adapter 포즈 스트림 릴레이."""
    await websocket.accept()

    # Optional token auth
    api_key = os.getenv("RUVIEW_API_KEY")
    if api_key and not token:
        await websocket.send_json({"type": "error", "message": "Authentication token required"})
        await websocket.close(code=1008)
        return
    if api_key and token and token != api_key:
        await websocket.send_json({"type": "error", "message": "Invalid token"})
        await websocket.close(code=1008)
        return

    client_id = str(uuid.uuid4())
    _state.register(client_id, websocket)

    upstream_ws_url = f"{_WS_BASE}/ws/events"
    frame_interval = 1.0 / max_fps

    # Send connection confirmation
    await websocket.send_json({
        "type": "connection_established",
        "client_id": client_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "config": {
            "zone_ids": zone_ids.split(",") if zone_ids else None,
            "min_confidence": min_confidence,
            "max_fps": max_fps,
        },
    })

    logger.info("WS pose client %s connected (max_fps=%s)", client_id, max_fps)

    async def _relay():
        """Connect to signal-adapter WS and relay frames to this client."""
        try:
            async with websockets.connect(upstream_ws_url, ping_interval=20) as upstream:
                last_sent = 0.0
                async for raw in upstream:
                    now = time.time()
                    if now - last_sent < frame_interval:
                        continue
                    try:
                        msg = json.loads(raw) if isinstance(raw, str) else raw
                    except json.JSONDecodeError:
                        continue

                    # Confidence filter when payload contains persons
                    if isinstance(msg, dict) and "persons" in msg:
                        msg["persons"] = [
                            p for p in msg["persons"]
                            if p.get("confidence", 1.0) >= min_confidence
                        ]

                    _state.record_frame()
                    last_sent = now

                    try:
                        await websocket.send_json(msg)
                    except Exception:
                        break  # client disconnected

        except (OSError, websockets.exceptions.WebSocketException) as exc:
            logger.warning("Upstream WS unavailable for client %s: %s", client_id, exc)
            try:
                await websocket.send_json({
                    "type": "upstream_unavailable",
                    "message": "signal-adapter WebSocket is currently unreachable",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            except Exception:
                pass

    relay_task = asyncio.create_task(_relay())

    try:
        while True:
            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                data = json.loads(raw)
                msg_type = data.get("type")
                if msg_type == "ping":
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                elif msg_type == "update_config":
                    # Acknowledge config updates (dynamic fps not yet wired into relay)
                    new_fps = data.get("config", {}).get("max_fps")
                    if new_fps:
                        frame_interval = 1.0 / max(1, min(60, int(new_fps)))
                    await websocket.send_json({
                        "type": "config_updated",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
            except asyncio.TimeoutError:
                # Send keep-alive ping
                try:
                    await websocket.send_json({
                        "type": "ping",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                except Exception:
                    break
            except (WebSocketDisconnect, json.JSONDecodeError):
                break
            except Exception as exc:
                logger.error("WS message handling error: %s", exc)
                break
    finally:
        relay_task.cancel()
        _state.unregister(client_id)
        logger.info("WS pose client %s disconnected", client_id)


# ---------------------------------------------------------------------------
# HTTP management endpoints
# ---------------------------------------------------------------------------

@router.get("/status", response_model=StreamStatusResponse)
async def stream_status():
    """GET /api/v1/stream/status — 스트림 상태 (연결 수, fps, 마지막 프레임)."""
    return StreamStatusResponse(
        is_active=True,
        connected_clients=_state.client_count,
        current_fps=round(_state.current_fps, 2),
        last_frame_at=(
            datetime.fromtimestamp(_state.last_frame_ts, tz=timezone.utc).isoformat()
            if _state.last_frame_ts
            else None
        ),
        uptime_seconds=round(_state.uptime, 1),
        frame_count=_state.frame_count,
    )


@router.post("/fps")
async def set_fps(request: FpsRequest, _auth=Depends(verify_api_key)):
    """POST /api/v1/stream/fps — 목표 FPS 제어 (signal-adapter 에도 전달 시도)."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"{SIGNAL_ADAPTER_URL}/api/stream/fps",
                json={"fps": request.fps},
            )
            upstream_ok = resp.is_success
    except httpx.RequestError:
        upstream_ok = False

    return {
        "fps": request.fps,
        "upstream_updated": upstream_ok,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
