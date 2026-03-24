"""
mmWave Integration Bridge — ESP32-C6 + MR60BHA2 sensor fusion.

Phase 5-5: Framework for fusing mmWave radar vitals with CSI-derived vitals.

Expects UDP packets from ESP32-C6 + MR60BHA2 on configurable port (default 5006).
Parses mmWave data: heart_rate, breathing_rate, distance, target_count, presence.
Kalman fusion: mmWave 80% + CSI 20% for HR/BR when mmWave is connected.
Falls back to CSI-only when mmWave hardware is not connected.

Ref: ruvnet mmwave_fusion_bridge.py
"""
import asyncio
import struct
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MmWaveVitals:
    """Parsed mmWave vital signs from MR60BHA2."""
    heart_rate: float = 0.0
    breathing_rate: float = 0.0
    distance: float = 0.0
    target_count: int = 0
    presence: bool = False
    timestamp: float = 0.0


class MmWaveKalmanFilter:
    """1-D Kalman filter for mmWave + CSI vital sign fusion.

    Default weights: mmWave 80%, CSI 20%.
    mmWave radar provides more accurate vitals than CSI because it
    directly measures chest displacement rather than inferring it
    from WiFi signal perturbation.
    """

    def __init__(self, mmwave_weight: float = 0.8, csi_weight: float = 0.2):
        self.mmwave_weight = mmwave_weight
        self.csi_weight = csi_weight
        # Kalman state
        self.x = 0.0       # fused estimate
        self.p = 1.0       # estimate uncertainty
        self.q = 0.3       # process noise
        self.r_mw = 0.5    # mmWave measurement noise
        self.r_csi = 3.0   # CSI measurement noise (higher = less trusted)

    def fuse(self, mmwave_val: float | None, csi_val: float | None) -> float:
        """Fuse mmWave and CSI measurements.

        If only one source available, use it directly with appropriate noise.
        If both available, weighted Kalman fusion.
        """
        # Predict step
        self.p += self.q

        if mmwave_val is not None and csi_val is not None:
            # Both available: weighted fusion
            measurement = self.mmwave_weight * mmwave_val + self.csi_weight * csi_val
            r = self.r_mw * self.mmwave_weight + self.r_csi * self.csi_weight
        elif mmwave_val is not None:
            measurement = mmwave_val
            r = self.r_mw
        elif csi_val is not None:
            measurement = csi_val
            r = self.r_csi
        else:
            return self.x  # No measurement, return prediction

        # Update step
        k = self.p / (self.p + r)
        self.x = self.x + k * (measurement - self.x)
        self.p = (1.0 - k) * self.p

        return self.x


class MmWaveBridge:
    """Bridge for ESP32-C6 + MR60BHA2 mmWave radar sensor.

    Listens for UDP packets containing mmWave vital signs data.
    Provides Kalman-fused vitals combining mmWave (80%) and CSI (20%).

    Packet format (expected from ESP32-C6 firmware):
        Magic (4 bytes): 0x4D573031 ("MW01")
        heart_rate (float32 LE)
        breathing_rate (float32 LE)
        distance (float32 LE)
        target_count (uint8)
        presence (uint8, 0 or 1)
        reserved (2 bytes)
        Total: 20 bytes

    When mmWave hardware is not connected, all methods return CSI-only values.
    """

    MMWAVE_MAGIC = 0x4D573031  # "MW01"
    PACKET_SIZE = 20

    def __init__(self, udp_port: int = 5006, udp_host: str = "0.0.0.0"):
        self.udp_port = udp_port
        self.udp_host = udp_host
        self._connected = False
        self._last_data: MmWaveVitals = MmWaveVitals()
        self._last_receive_time: float = 0.0
        self._packet_count: int = 0
        self._transport: Any = None
        self._running = False

        # Kalman filters for HR and BR fusion
        self._hr_kalman = MmWaveKalmanFilter(mmwave_weight=0.8, csi_weight=0.2)
        self._br_kalman = MmWaveKalmanFilter(mmwave_weight=0.8, csi_weight=0.2)

    @property
    def is_connected(self) -> bool:
        """Check if mmWave sensor is sending data (received within last 5s)."""
        if self._last_receive_time == 0:
            return False
        return (time.monotonic() - self._last_receive_time) < 5.0

    def parse_packet(self, data: bytes) -> MmWaveVitals | None:
        """Parse a mmWave UDP packet.

        Returns MmWaveVitals if valid, None if packet is invalid.
        """
        if len(data) < self.PACKET_SIZE:
            return None

        magic = struct.unpack_from("<I", data, 0)[0]
        if magic != self.MMWAVE_MAGIC:
            return None

        heart_rate = struct.unpack_from("<f", data, 4)[0]
        breathing_rate = struct.unpack_from("<f", data, 8)[0]
        distance = struct.unpack_from("<f", data, 12)[0]
        target_count = data[16]
        presence = bool(data[17])

        return MmWaveVitals(
            heart_rate=heart_rate,
            breathing_rate=breathing_rate,
            distance=distance,
            target_count=target_count,
            presence=presence,
            timestamp=time.monotonic(),
        )

    def handle_packet(self, data: bytes) -> None:
        """Process an incoming mmWave UDP packet."""
        vitals = self.parse_packet(data)
        if vitals is None:
            return

        self._last_data = vitals
        self._last_receive_time = time.monotonic()
        self._packet_count += 1
        self._connected = True

    def get_fused_vitals(
        self,
        csi_hr: float | None = None,
        csi_br: float | None = None,
        mw_hr: float | None = None,
        mw_br: float | None = None,
    ) -> dict[str, float | None]:
        """Get Kalman-fused vital signs from mmWave + CSI.

        If mmWave is connected and mw_hr/mw_br are None, uses the latest
        mmWave data from the UDP stream. If mmWave is not connected,
        returns CSI-only values.

        Args:
            csi_hr: CSI-derived heart rate (BPM), or None.
            csi_br: CSI-derived breathing rate (BPM), or None.
            mw_hr: mmWave heart rate override (uses latest if None).
            mw_br: mmWave breathing rate override (uses latest if None).

        Returns:
            Dict with fused_hr, fused_br, source (modality used).
        """
        # Use latest mmWave data if not overridden
        if self.is_connected:
            if mw_hr is None:
                mw_hr = self._last_data.heart_rate if self._last_data.heart_rate > 0 else None
            if mw_br is None:
                mw_br = self._last_data.breathing_rate if self._last_data.breathing_rate > 0 else None

        # Validate ranges
        if mw_hr is not None and not (30.0 <= mw_hr <= 200.0):
            mw_hr = None
        if mw_br is not None and not (4.0 <= mw_br <= 40.0):
            mw_br = None
        if csi_hr is not None and not (30.0 <= csi_hr <= 200.0):
            csi_hr = None
        if csi_br is not None and not (4.0 <= csi_br <= 40.0):
            csi_br = None

        # Determine source modality
        if mw_hr is not None and csi_hr is not None:
            source = "mmwave+csi"
        elif mw_hr is not None:
            source = "mmwave_only"
        elif csi_hr is not None:
            source = "csi_only"
        else:
            source = "none"

        # Fuse via Kalman
        fused_hr = self._hr_kalman.fuse(mw_hr, csi_hr) if (mw_hr is not None or csi_hr is not None) else None
        fused_br = self._br_kalman.fuse(mw_br, csi_br) if (mw_br is not None or csi_br is not None) else None

        return {
            "fused_hr": round(fused_hr, 1) if fused_hr is not None else None,
            "fused_br": round(fused_br, 1) if fused_br is not None else None,
            "source": source,
            "mmwave_connected": self.is_connected,
            "mmwave_hr": round(mw_hr, 1) if mw_hr is not None else None,
            "mmwave_br": round(mw_br, 1) if mw_br is not None else None,
            "csi_hr": round(csi_hr, 1) if csi_hr is not None else None,
            "csi_br": round(csi_br, 1) if csi_br is not None else None,
        }

    def get_status(self) -> dict[str, Any]:
        """Get mmWave bridge status for API endpoint."""
        return {
            "enabled": True,
            "connected": self.is_connected,
            "udp_port": self.udp_port,
            "udp_host": self.udp_host,
            "packet_count": self._packet_count,
            "last_data": {
                "heart_rate": self._last_data.heart_rate,
                "breathing_rate": self._last_data.breathing_rate,
                "distance": self._last_data.distance,
                "target_count": self._last_data.target_count,
                "presence": self._last_data.presence,
            } if self._packet_count > 0 else None,
            "seconds_since_last": (
                round(time.monotonic() - self._last_receive_time, 1)
                if self._last_receive_time > 0 else None
            ),
        }

    async def start_listener(self, loop: asyncio.AbstractEventLoop) -> None:
        """Start async UDP listener for mmWave packets.

        This creates a datagram endpoint that receives packets from
        ESP32-C6 + MR60BHA2 and processes them.
        """
        self._running = True

        class MmWaveProtocol(asyncio.DatagramProtocol):
            def __init__(self, bridge: "MmWaveBridge"):
                self.bridge = bridge

            def datagram_received(self, data: bytes, addr) -> None:
                self.bridge.handle_packet(data)

        try:
            transport, _ = await loop.create_datagram_endpoint(
                lambda: MmWaveProtocol(self),
                local_addr=(self.udp_host, self.udp_port),
            )
            self._transport = transport
            print(f"[mmwave-bridge] Listening on UDP {self.udp_host}:{self.udp_port}")

            # Keep running until stopped
            while self._running:
                await asyncio.sleep(1.0)
        except OSError as e:
            print(f"[mmwave-bridge] Failed to bind UDP {self.udp_host}:{self.udp_port}: {e}")
        except asyncio.CancelledError:
            pass
        finally:
            if self._transport:
                self._transport.close()

    def stop(self) -> None:
        """Stop the mmWave bridge."""
        self._running = False
        if self._transport:
            self._transport.close()
            self._transport = None
        print("[mmwave-bridge] Stopped")
