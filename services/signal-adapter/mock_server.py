"""
Mock simulation server - runs standalone for frontend development.
Provides WebSocket stream + REST endpoints with simulated CSI data.

Usage:
    python -m services.signal-adapter.mock_server
    # or
    cd services/signal-adapter && python mock_server.py
"""
import asyncio
import json
import os
import sys

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# Add parent paths for imports
sys.path.insert(0, os.path.dirname(__file__))

from mock_generator import MockCSIGenerator
from csi_processor import CSIProcessor
from event_engine import EventEngine
from ws_manager import ConnectionManager

load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))

app = FastAPI(title="RuView Mock Server", version="0.1.0-mock")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

generator = MockCSIGenerator(num_subcarriers=64, num_devices=2)
processor = CSIProcessor()
engine = EventEngine()
manager = ConnectionManager()

# Background task reference
_broadcast_task = None


async def broadcast_loop():
    """Generate and broadcast mock events at ~10Hz."""
    while True:
        for i in range(generator.num_devices):
            raw = generator.generate_frame(i)
            # Convert complex to list for JSON
            raw_json = {**raw}
            raw_json["csi_data"] = [
                [c.real, c.imag] if isinstance(c, complex) else c
                for c in raw["csi_data"]
            ]

            processed = processor.process(raw_json)
            events = engine.evaluate(processed)

            for event in events:
                msg = json.dumps({
                    "type": "event",
                    "payload": event.model_dump(),
                    "timestamp": event.timestamp,
                })
                await manager.broadcast(msg)

            # Signal update
            signal_msg = json.dumps({
                "type": "signal",
                "payload": {
                    "device_id": raw["device_id"],
                    "time": raw["timestamp"][-12:-1],
                    "rssi": raw["rssi"],
                    "snr": round(raw["rssi"] - raw["noise_floor"], 1),
                    "csi_amplitude": round(sum(processed.amplitude) / max(len(processed.amplitude), 1), 2),
                    "motion_index": round(processed.motion_index, 3),
                    "scenario": raw.get("scenario", "unknown"),
                },
                "timestamp": raw["timestamp"],
            })
            await manager.broadcast(signal_msg)

        await asyncio.sleep(0.1)  # 10Hz


@app.on_event("startup")
async def startup():
    global _broadcast_task
    _broadcast_task = asyncio.create_task(broadcast_loop())


@app.on_event("shutdown")
async def shutdown():
    if _broadcast_task:
        _broadcast_task.cancel()


@app.get("/health")
async def health():
    return {"status": "ok", "service": "mock-server", "mode": "simulation"}


@app.get("/api/devices")
async def list_devices():
    return {"data": generator.generate_device_status()}


@app.get("/api/zones")
async def list_zones():
    return {"data": generator.generate_zones()}


@app.get("/api/scenario")
async def get_scenario():
    return {"scenario": generator._scenario, "tick": generator._tick}


@app.post("/api/scenario/{scenario}")
async def set_scenario(scenario: str):
    generator.set_scenario(scenario)
    return {"scenario": generator._scenario}


@app.websocket("/ws/events")
async def websocket_events(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Send initial state
        await websocket.send_text(json.dumps({
            "type": "init",
            "payload": {
                "devices": generator.generate_device_status(),
                "zones": generator.generate_zones(),
            },
        }))
        while True:
            data = await websocket.receive_text()
            # Handle commands from frontend
            try:
                cmd = json.loads(data)
                if cmd.get("type") == "set_scenario":
                    generator.set_scenario(cmd.get("scenario", "idle"))
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
