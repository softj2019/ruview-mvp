"""
Mock CSI data generator for development without ESP32 hardware.
Simulates realistic CSI data patterns including:
- Presence detection (subtle amplitude variations)
- Motion detection (larger amplitude changes)
- Fall events (sudden spike + drop pattern)
- Breathing/heart rate modulation
"""
import math
import random
import time
from datetime import datetime, timezone
from uuid import uuid4


class MockCSIGenerator:
    """Generate realistic mock CSI data streams."""

    def __init__(self, num_subcarriers: int = 64, num_devices: int = 2):
        self.num_subcarriers = num_subcarriers
        self.num_devices = num_devices
        self.devices = [
            {
                "id": f"esp32-node-{i+1}",
                "name": f"Node #{i+1}",
                "mac": f"0C:B8:15:F5:6F:{14+i:02X}",
                "x": 200 + i * 300,
                "y": 200 + (i % 2) * 200,
            }
            for i in range(num_devices)
        ]
        self._tick = 0
        self._scenario = "idle"
        self._scenario_start = 0
        self._scenarios = ["idle", "presence", "motion", "fall", "breathing"]
        self._scenario_duration = {"idle": 100, "presence": 200, "motion": 150, "fall": 30, "breathing": 250}

    def set_scenario(self, scenario: str):
        if scenario in self._scenarios:
            self._scenario = scenario
            self._scenario_start = self._tick

    def auto_cycle(self):
        elapsed = self._tick - self._scenario_start
        duration = self._scenario_duration.get(self._scenario, 100)
        if elapsed >= duration:
            self._scenario = random.choice(self._scenarios)
            self._scenario_start = self._tick

    def generate_frame(self, device_idx: int = 0) -> dict:
        self._tick += 1
        self.auto_cycle()
        device = self.devices[device_idx % self.num_devices]
        t = self._tick * 0.02  # 50Hz sampling

        # Base CSI amplitude with noise
        amplitude = []
        phase = []
        for sc in range(self.num_subcarriers):
            base = 30.0 + 5.0 * math.sin(sc * 0.1)
            noise = random.gauss(0, 0.5)

            if self._scenario == "presence":
                base += 2.0 * math.sin(t * 0.3 + sc * 0.05)
            elif self._scenario == "motion":
                base += 8.0 * math.sin(t * 2.0 + sc * 0.1) * random.uniform(0.8, 1.2)
            elif self._scenario == "fall":
                elapsed = self._tick - self._scenario_start
                if elapsed < 5:
                    base += 15.0 * (elapsed / 5.0)
                elif elapsed < 15:
                    base -= 10.0 * ((elapsed - 5) / 10.0)
                else:
                    base += 1.0 * math.sin(t * 0.2)
            elif self._scenario == "breathing":
                base += 1.5 * math.sin(t * 0.25 * math.pi)  # ~15 BPM
                base += 0.3 * math.sin(t * 1.2 * math.pi)   # ~72 BPM heart

            amplitude.append(round(base + noise, 3))
            phase.append(round(math.atan2(
                math.sin(t + sc * 0.2 + noise * 0.1),
                math.cos(t + sc * 0.2)
            ), 4))

        rssi = -45.0 + random.gauss(0, 3)
        if self._scenario == "idle":
            rssi = -60.0 + random.gauss(0, 2)

        return {
            "device_id": device["id"],
            "mac": device["mac"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "csi_data": [complex(a * math.cos(p), a * math.sin(p)) for a, p in zip(amplitude, phase)],
            "rssi": round(rssi, 1),
            "noise_floor": round(-95.0 + random.gauss(0, 1), 1),
            "channel": random.choice([1, 6, 11]),
            "scenario": self._scenario,
        }

    def generate_device_status(self) -> list[dict]:
        return [
            {
                "id": d["id"],
                "name": d["name"],
                "mac": d["mac"],
                "status": "online",
                "x": d["x"],
                "y": d["y"],
                "signalStrength": round(-45 + random.gauss(0, 5), 1),
                "lastSeen": datetime.now(timezone.utc).isoformat(),
                "firmwareVersion": "0.5.0-mock",
            }
            for d in self.devices
        ]

    def generate_zones(self) -> list[dict]:
        return [
            {
                "id": "zone-living-room",
                "name": "Living Room",
                "polygon": [
                    {"x": 50, "y": 50}, {"x": 400, "y": 50},
                    {"x": 400, "y": 350}, {"x": 50, "y": 350}
                ],
                "status": "active" if self._scenario != "idle" else "inactive",
                "presenceCount": 1 if self._scenario in ("presence", "motion", "breathing") else 0,
                "lastActivity": datetime.now(timezone.utc).isoformat(),
            },
            {
                "id": "zone-bedroom",
                "name": "Bedroom",
                "polygon": [
                    {"x": 420, "y": 50}, {"x": 750, "y": 50},
                    {"x": 750, "y": 350}, {"x": 420, "y": 350}
                ],
                "status": "inactive",
                "presenceCount": 0,
                "lastActivity": None,
            },
            {
                "id": "zone-hallway",
                "name": "Hallway",
                "polygon": [
                    {"x": 50, "y": 370}, {"x": 750, "y": 370},
                    {"x": 750, "y": 450}, {"x": 50, "y": 450}
                ],
                "status": "inactive",
                "presenceCount": 0,
                "lastActivity": None,
            },
        ]
