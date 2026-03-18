import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .routes import devices, zones, events, health

load_dotenv(os.path.join(os.path.dirname(__file__), "../../../.env"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[api-gateway] Starting up...")
    yield
    print("[api-gateway] Shutting down...")


app = FastAPI(
    title="RuView API Gateway",
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

app.include_router(health.router, tags=["health"])
app.include_router(devices.router, prefix="/api/devices", tags=["devices"])
app.include_router(zones.router, prefix="/api/zones", tags=["zones"])
app.include_router(events.router, prefix="/api/events", tags=["events"])


# WebSocket relay - forwards events from signal-adapter to frontend
connected_clients: list[WebSocket] = []


@app.websocket("/ws/monitor")
async def websocket_monitor(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Relay to all other clients
            for client in connected_clients:
                if client != websocket:
                    try:
                        await client.send_text(data)
                    except Exception:
                        pass
    except WebSocketDisconnect:
        connected_clients.remove(websocket)
