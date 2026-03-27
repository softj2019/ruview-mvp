"""Swarm Health Oracle — monitors multiple ESP32 CSI nodes.

Polls the signal-adapter /health/nodes endpoint at a configurable interval
and tracks per-node health metrics. Nodes are classified as:
  - online:   CSI frames arriving at expected rate, RSSI acceptable
  - degraded: frames arriving but rate low or packet loss high
  - offline:  no frames received within the timeout window

Usage:
    python monitoring/swarm_health.py
    python monitoring/swarm_health.py --url http://localhost:8001 --interval 5
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

import httpx

logger = logging.getLogger("swarm_health")

# ── Thresholds ──────────────────────────────────────────────────────────────────

OFFLINE_TIMEOUT_S = 10.0    # seconds since last frame before node is offline
DEGRADED_RATE_HZ = 50.0     # CSI rate below this → degraded (nominal ~100 Hz)
DEGRADED_LOSS_PCT = 0.20    # packet loss above 20% → degraded
DEGRADED_RSSI_DBM = -80.0   # RSSI below this → degraded


# ── Data model ─────────────────────────────────────────────────────────────────

@dataclass
class NodeHealth:
    node_id: str
    last_seen: float = 0.0          # unix timestamp
    csi_rate_hz: float = 0.0        # frames per second
    packet_loss: float = 0.0        # 0.0 – 1.0
    rssi_avg: float = 0.0           # dBm
    status: str = "unknown"         # online | offline | degraded | unknown
    consecutive_failures: int = 0   # poll cycles with no data
    mac_addr: str = ""
    zone_id: Optional[str] = None


# ── Oracle ─────────────────────────────────────────────────────────────────────

class SwarmHealthOracle:
    """Continuously polls signal-adapter and tracks ESP32 node health."""

    def __init__(
        self,
        signal_adapter_url: str = "http://localhost:8001",
        http_timeout: float = 5.0,
    ) -> None:
        self.signal_adapter_url = signal_adapter_url.rstrip("/")
        self.http_timeout = http_timeout
        self.nodes: dict[str, NodeHealth] = {}
        self._client: Optional[httpx.AsyncClient] = None

    # ── HTTP client lifecycle ──────────────────────────────────────────────────

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.http_timeout)
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ── Status determination ───────────────────────────────────────────────────

    def _determine_status(self, node: NodeHealth) -> str:
        """Classify a node based on its latest metrics."""
        now = time.time()

        if node.last_seen == 0.0:
            return "unknown"

        if (now - node.last_seen) > OFFLINE_TIMEOUT_S:
            return "offline"

        degraded_reasons = []
        if node.csi_rate_hz < DEGRADED_RATE_HZ:
            degraded_reasons.append(f"rate={node.csi_rate_hz:.1f}Hz")
        if node.packet_loss > DEGRADED_LOSS_PCT:
            degraded_reasons.append(f"loss={node.packet_loss*100:.0f}%")
        if node.rssi_avg < DEGRADED_RSSI_DBM:
            degraded_reasons.append(f"rssi={node.rssi_avg:.0f}dBm")

        if degraded_reasons:
            logger.debug("Node %s degraded: %s", node.node_id, ", ".join(degraded_reasons))
            return "degraded"

        return "online"

    # ── Poll ──────────────────────────────────────────────────────────────────

    async def poll(self) -> dict[str, NodeHealth]:
        """Poll signal-adapter /health/nodes endpoint and update node states."""
        url = f"{self.signal_adapter_url}/health/nodes"
        client = await self._get_client()

        try:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
        except httpx.ConnectError:
            logger.warning("Cannot reach signal-adapter at %s", url)
            # Mark all previously known nodes as offline
            for node in self.nodes.values():
                node.consecutive_failures += 1
                if node.consecutive_failures >= 3:
                    node.status = "offline"
            return self.nodes
        except httpx.HTTPStatusError as exc:
            logger.warning("HTTP %s from %s", exc.response.status_code, url)
            return self.nodes
        except Exception as exc:
            logger.error("Unexpected error polling %s: %s", url, exc)
            return self.nodes

        # Parse response — expected format:
        # {
        #   "nodes": [
        #     {
        #       "node_id": "esp32_01",
        #       "mac": "AA:BB:CC:DD:EE:01",
        #       "last_frame_ts": 1711539200.123,
        #       "csi_rate_hz": 98.4,
        #       "packet_loss": 0.02,
        #       "rssi_avg": -55.0,
        #       "zone_id": "1001"
        #     },
        #     ...
        #   ]
        # }
        node_list = data.get("nodes", [])
        seen_ids: set[str] = set()

        for raw in node_list:
            nid = str(raw.get("node_id", ""))
            if not nid:
                continue
            seen_ids.add(nid)

            node = self.nodes.setdefault(nid, NodeHealth(node_id=nid))
            node.last_seen = float(raw.get("last_frame_ts", time.time()))
            node.csi_rate_hz = float(raw.get("csi_rate_hz", 0.0))
            node.packet_loss = float(raw.get("packet_loss", 0.0))
            node.rssi_avg = float(raw.get("rssi_avg", 0.0))
            node.mac_addr = str(raw.get("mac", ""))
            node.zone_id = raw.get("zone_id")
            node.consecutive_failures = 0
            node.status = self._determine_status(node)

        # Nodes not in the latest response — increment failure counter
        for nid, node in self.nodes.items():
            if nid not in seen_ids:
                node.consecutive_failures += 1
                if node.consecutive_failures >= 3:
                    node.status = "offline"

        return self.nodes

    # ── Continuous monitoring loop ────────────────────────────────────────────

    async def run(self, interval: float = 5.0) -> None:
        """Poll indefinitely and log status changes."""
        logger.info(
            "SwarmHealthOracle started — polling %s every %.1fs",
            self.signal_adapter_url,
            interval,
        )
        prev_statuses: dict[str, str] = {}

        try:
            while True:
                await self.poll()
                self._log_summary(prev_statuses)
                prev_statuses = {nid: n.status for nid, n in self.nodes.items()}
                await asyncio.sleep(interval)
        finally:
            await self.close()

    def _log_summary(self, prev: dict[str, str]) -> None:
        """Log a one-liner summary and emit warnings on status transitions."""
        now_str = time.strftime("%H:%M:%S")
        online = [n for n in self.nodes.values() if n.status == "online"]
        degraded = self.get_degraded()
        offline = [n for n in self.nodes.values() if n.status == "offline"]

        logger.info(
            "[%s] Nodes: %d online, %d degraded, %d offline",
            now_str,
            len(online),
            len(degraded),
            len(offline),
        )

        for nid, node in self.nodes.items():
            prev_status = prev.get(nid, "unknown")
            if node.status != prev_status:
                if node.status in ("offline", "degraded"):
                    logger.warning(
                        "Node %s transitioned %s → %s "
                        "(rate=%.1fHz, loss=%.0f%%, rssi=%.0fdBm)",
                        nid,
                        prev_status,
                        node.status,
                        node.csi_rate_hz,
                        node.packet_loss * 100,
                        node.rssi_avg,
                    )
                else:
                    logger.info("Node %s recovered: %s → %s", nid, prev_status, node.status)

    # ── Query helpers ─────────────────────────────────────────────────────────

    def get_degraded(self) -> list[str]:
        """Return node_ids with degraded or offline status."""
        return [
            nid
            for nid, node in self.nodes.items()
            if node.status in ("degraded", "offline")
        ]

    def get_summary(self) -> dict:
        """Return a serialisable summary dict."""
        return {
            "total": len(self.nodes),
            "online": sum(1 for n in self.nodes.values() if n.status == "online"),
            "degraded": sum(1 for n in self.nodes.values() if n.status == "degraded"),
            "offline": sum(1 for n in self.nodes.values() if n.status == "offline"),
            "unknown": sum(1 for n in self.nodes.values() if n.status == "unknown"),
            "nodes": {
                nid: {
                    "status": n.status,
                    "csi_rate_hz": n.csi_rate_hz,
                    "packet_loss": n.packet_loss,
                    "rssi_avg": n.rssi_avg,
                    "last_seen": n.last_seen,
                    "zone_id": n.zone_id,
                }
                for nid, n in self.nodes.items()
            },
        }


# ── CLI entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ruView Swarm Health Oracle")
    parser.add_argument(
        "--url",
        default="http://localhost:8001",
        help="signal-adapter base URL (default: http://localhost:8001)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=5.0,
        help="Poll interval in seconds (default: 5.0)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    oracle = SwarmHealthOracle(signal_adapter_url=args.url)
    asyncio.run(oracle.run(interval=args.interval))
