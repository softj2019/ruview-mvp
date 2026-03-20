import asyncio
import json
import os
import struct
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

try:
    from .ws_manager import ConnectionManager
    from .csi_processor import CSIProcessor, ProcessedCSI
    from .event_engine import EventEngine
    from .supabase_client import get_supabase
except ImportError:
    from ws_manager import ConnectionManager
    from csi_processor import CSIProcessor, ProcessedCSI
    from event_engine import EventEngine
    from supabase_client import get_supabase


load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))

UDP_HOST = os.getenv("CSI_UDP_HOST", "0.0.0.0")
UDP_PORT = int(os.getenv("CSI_UDP_PORT", os.getenv("ESP_TARGET_PORT", "5005")))
DEFAULT_ZONE = {
    "id": "zone-main",
    "name": "Main Zone",
    "polygon": [
        {"x": 80, "y": 80},
        {"x": 720, "y": 80},
        {"x": 720, "y": 420},
        {"x": 80, "y": 420},
    ],
    "status": "active",
    "presenceCount": 0,
    "lastActivity": None,
}
DEVICE_POSITIONS = [
    (140, 120),
    (660, 120),
    (140, 380),
    (660, 380),
    (400, 120),
    (400, 380),
]
CSI_MAGIC = 0xC5110001
VITALS_MAGIC = 0xC5110002


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def to_event_payload(event) -> dict[str, Any]:
    return {
        "id": event.id,
        "type": event.type,
        "severity": event.severity,
        "zone": event.zone,
        "deviceId": event.device_id,
        "confidence": event.confidence,
        "timestamp": event.timestamp,
        "metadata": event.metadata,
    }


def avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


class SignalAdapterRuntime:
    def __init__(self) -> None:
        self.manager = ConnectionManager()
        self.csi_processor = CSIProcessor()
        self.event_engine = EventEngine()
        self.devices: dict[str, dict[str, Any]] = {}
        self.zones: list[dict[str, Any]] = [dict(DEFAULT_ZONE)]
        self.transport = None

    def device_key(self, node_id: int) -> str:
        return f"node-{node_id}"

    def device_position(self, node_id: int) -> tuple[int, int]:
        return DEVICE_POSITIONS[(node_id - 1) % len(DEVICE_POSITIONS)]

    def ensure_device(self, node_id: int, ip: str | None = None) -> dict[str, Any]:
        device_id = self.device_key(node_id)
        if device_id not in self.devices:
            x, y = self.device_position(node_id)
            self.devices[device_id] = {
                "id": device_id,
                "name": f"ESP32 Node {node_id}",
                "mac": ip or "",
                "status": "online",
                "x": x,
                "y": y,
                "signalStrength": None,
                "lastSeen": iso_now(),
                "firmwareVersion": "RuView operational",
            }
        return self.devices[device_id]

    async def broadcast(self, message_type: str, payload: dict[str, Any]) -> None:
        await self.manager.broadcast(
            json.dumps(
                {
                    "type": message_type,
                    "payload": payload,
                    "timestamp": iso_now(),
                }
            )
        )

    async def broadcast_devices(self) -> None:
        await self.broadcast("device_update", {"devices": list(self.devices.values())})

    async def broadcast_zones(self) -> None:
        await self.broadcast("zone_update", {"zones": self.zones})

    async def handle_processed(self, processed: ProcessedCSI) -> None:
        events = self.event_engine.evaluate(processed)

        signal_payload = {
            "device_id": processed.device_id,
            "time": processed.timestamp[11:19] if len(processed.timestamp) >= 19 else processed.timestamp,
            "rssi": round(processed.rssi, 1),
            "snr": round(processed.rssi - processed.noise_floor, 1),
            "csi_amplitude": round(avg(processed.amplitude), 2),
            "motion_index": round(processed.motion_index, 3),
        }
        await self.broadcast("signal", signal_payload)

        for event in events:
            await self.broadcast("event", to_event_payload(event))

        sb = get_supabase()
        if sb and events:
            sb.table("events").insert([e.model_dump() for e in events]).execute()

    async def handle_csi_frame(self, data: bytes, addr: tuple[str, int]) -> None:
        if len(data) < 20:
            return

        node_id = data[4]
        n_subcarriers = struct.unpack_from("<H", data, 6)[0]
        rssi = struct.unpack_from("<b", data, 16)[0]
        noise_floor = struct.unpack_from("<b", data, 17)[0]
        iq_bytes = data[20:]

        device = self.ensure_device(node_id, addr[0])
        device["status"] = "online"
        device["mac"] = addr[0]
        device["signalStrength"] = rssi
        device["lastSeen"] = iso_now()

        pairs = min(n_subcarriers, len(iq_bytes) // 2)
        csi_data = [
            complex(
                struct.unpack_from("<b", iq_bytes, index * 2)[0],
                struct.unpack_from("<b", iq_bytes, index * 2 + 1)[0],
            )
            for index in range(pairs)
        ]

        processed = self.csi_processor.process(
            {
                "device_id": device["id"],
                "timestamp": iso_now(),
                "csi_data": csi_data,
                "rssi": float(rssi),
                "noise_floor": float(noise_floor),
            }
        )

        self.zones[0]["lastActivity"] = processed.timestamp
        self.zones[0]["presenceCount"] = len(
            [item for item in self.devices.values() if item["status"] == "online"]
        )

        await self.broadcast_devices()
        await self.broadcast_zones()
        await self.handle_processed(processed)

    async def handle_vitals_frame(self, data: bytes, addr: tuple[str, int]) -> None:
        if len(data) < 24:
            return

        node_id = data[4]
        flags = data[5]
        breathing_bpm = struct.unpack_from("<H", data, 6)[0] / 100.0
        heart_rate = struct.unpack_from("<f", data, 8)[0]
        rssi = struct.unpack_from("<b", data, 12)[0]
        n_persons = data[13]
        motion_energy = struct.unpack_from("<f", data, 16)[0]
        presence_score = struct.unpack_from("<f", data, 20)[0]

        device = self.ensure_device(node_id, addr[0])
        device["status"] = "online"
        device["signalStrength"] = rssi
        device["lastSeen"] = iso_now()

        self.zones[0]["presenceCount"] = max(self.zones[0]["presenceCount"], n_persons)
        self.zones[0]["lastActivity"] = iso_now()
        await self.broadcast_devices()
        await self.broadcast_zones()

        metadata = {
            "breathing_bpm": breathing_bpm,
            "heart_rate": heart_rate,
            "motion_energy": motion_energy,
            "presence_score": presence_score,
            "flags": flags,
        }

        if flags & 0x02:
            event_payload = {
                "id": f"{node_id}-{int(datetime.now().timestamp() * 1000)}",
                "type": "fall_suspected",
                "severity": "critical",
                "zone": "zone-main",
                "deviceId": self.device_key(node_id),
                "confidence": min(max(motion_energy / 5.0, 0.6), 0.99),
                "timestamp": iso_now(),
                "metadata": metadata,
            }
            await self.broadcast("event", event_payload)

    async def route_datagram(self, data: bytes, addr: tuple[str, int]) -> None:
        if len(data) < 4:
            return

        magic = struct.unpack_from("<I", data, 0)[0]
        if magic == CSI_MAGIC:
            await self.handle_csi_frame(data, addr)
        elif magic == VITALS_MAGIC:
            await self.handle_vitals_frame(data, addr)


runtime = SignalAdapterRuntime()


class UDPProtocol(asyncio.DatagramProtocol):
    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self.loop = loop

    def datagram_received(self, data: bytes, addr) -> None:
        self.loop.create_task(runtime.route_datagram(data, addr))


@asynccontextmanager
async def lifespan(app: FastAPI):
    loop = asyncio.get_running_loop()
    transport, _ = await loop.create_datagram_endpoint(
        lambda: UDPProtocol(loop),
        local_addr=(UDP_HOST, UDP_PORT),
    )
    runtime.transport = transport
    print(f"[signal-adapter] Starting up on UDP {UDP_HOST}:{UDP_PORT}...")
    yield
    print("[signal-adapter] Shutting down...")
    if runtime.transport is not None:
        runtime.transport.close()


app = FastAPI(
    title="RuView Signal Adapter",
    version="0.2.0",
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
    return {
        "status": "ok",
        "service": "signal-adapter",
        "mode": "hardware",
        "udp_host": UDP_HOST,
        "udp_port": UDP_PORT,
        "devices": len(runtime.devices),
    }


@app.get("/api/devices")
async def list_devices():
    return {"data": list(runtime.devices.values())}


@app.get("/api/zones")
async def list_zones():
    return {"data": runtime.zones}


@app.get("/api/scenario")
async def get_scenario():
    return {"scenario": "hardware-live", "mode": "hardware", "supported": False}


@app.post("/api/scenario/{scenario}")
async def set_scenario(scenario: str):
    raise HTTPException(status_code=409, detail=f"Scenario switching is disabled in hardware mode: {scenario}")


@app.websocket("/ws/events")
async def websocket_events(websocket: WebSocket):
    await runtime.manager.connect(websocket)
    try:
        await websocket.send_text(
            json.dumps(
                {
                    "type": "init",
                    "payload": {
                        "devices": list(runtime.devices.values()),
                        "zones": runtime.zones,
                    },
                    "timestamp": iso_now(),
                }
            )
        )
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        runtime.manager.disconnect(websocket)


@app.post("/api/csi/ingest")
async def ingest_csi(payload: dict):
    processed = runtime.csi_processor.process(payload)
    await runtime.handle_processed(processed)
    return {"processed": 1}
