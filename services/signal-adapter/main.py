import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

try:
    from .ws_manager import ConnectionManager
    from .csi_processor import CSIProcessor
    from .event_engine import EventEngine
    from .supabase_client import get_supabase
except ImportError:
    from ws_manager import ConnectionManager
    from csi_processor import CSIProcessor
    from event_engine import EventEngine
    from supabase_client import get_supabase

load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))

manager = ConnectionManager()
csi_processor = CSIProcessor()
event_engine = EventEngine()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("[signal-adapter] Starting up...")
    yield
    # Shutdown
    print("[signal-adapter] Shutting down...")


app = FastAPI(
    title="RuView Signal Adapter",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "signal-adapter"}


@app.websocket("/ws/events")
async def websocket_events(websocket: WebSocket):
    """Broadcast processed events to frontend clients."""
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Client can send commands (e.g., subscribe to specific zones)
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.post("/api/csi/ingest")
async def ingest_csi(payload: dict):
    """Receive raw CSI data from RuView sensing server."""
    processed = csi_processor.process(payload)
    events = event_engine.evaluate(processed)

    for event in events:
        await manager.broadcast(event.model_dump_json())

    # Store to Supabase
    sb = get_supabase()
    if sb and events:
        sb.table("events").insert(
            [e.model_dump() for e in events]
        ).execute()

    return {"processed": len(events)}
