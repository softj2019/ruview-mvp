"""
Real-time streaming service for RuView Signal Adapter.
Adapted from vendor/ruview-temp/v1/src/services/stream_service.py
"""

import logging
import asyncio
import json
from typing import Dict, List, Optional, Any, Set
from datetime import datetime
from collections import deque

import numpy as np
from fastapi import WebSocket

logger = logging.getLogger(__name__)

# Default buffer and heartbeat configuration
_DEFAULT_BUFFER_SIZE = 200
_DEFAULT_PING_INTERVAL = 30  # seconds


class StreamService:
    """Service for real-time data streaming with buffer management and client tracking."""

    def __init__(
        self,
        buffer_size: int = _DEFAULT_BUFFER_SIZE,
        ping_interval: float = _DEFAULT_PING_INTERVAL,
    ):
        """Initialize stream service.

        Args:
            buffer_size: Maximum number of entries retained in each deque buffer.
            ping_interval: Seconds between heartbeat broadcasts.
        """
        self.buffer_size = buffer_size
        self.ping_interval = ping_interval
        self.logger = logging.getLogger(__name__)

        # WebSocket connections
        self.connections: Set[WebSocket] = set()
        self.connection_metadata: Dict[WebSocket, Dict[str, Any]] = {}

        # Stream buffers
        self.csi_buffer: deque = deque(maxlen=self.buffer_size)
        self.signal_buffer: deque = deque(maxlen=self.buffer_size)
        self.event_buffer: deque = deque(maxlen=self.buffer_size)

        # Service state
        self.is_running = False
        self.last_error: Optional[str] = None

        # Streaming statistics
        self.stats: Dict[str, Any] = {
            "active_connections": 0,
            "total_connections": 0,
            "messages_sent": 0,
            "messages_failed": 0,
            "data_points_streamed": 0,
            "average_latency_ms": 0.0,
        }

        # Background task handle
        self._streaming_task: Optional[asyncio.Task] = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def initialize(self):
        """Initialize the stream service."""
        self.logger.info("StreamService initialized (buffer_size=%d)", self.buffer_size)

    async def start(self):
        """Start the stream service and heartbeat loop."""
        if self.is_running:
            return
        self.is_running = True
        self._streaming_task = asyncio.create_task(self._streaming_loop())
        self.logger.info("StreamService started")

    async def stop(self):
        """Stop the stream service and close all connections."""
        self.is_running = False
        if self._streaming_task:
            self._streaming_task.cancel()
            try:
                await self._streaming_task
            except asyncio.CancelledError:
                pass
        await self._close_all_connections()
        self.logger.info("StreamService stopped")

    # ── Connection management ─────────────────────────────────────────────────

    async def add_connection(self, websocket: WebSocket,
                             metadata: Optional[Dict[str, Any]] = None):
        """Register a new WebSocket connection and send buffered initial data."""
        try:
            await websocket.accept()
            self.connections.add(websocket)
            self.connection_metadata[websocket] = metadata or {}
            self.stats["active_connections"] = len(self.connections)
            self.stats["total_connections"] += 1
            self.logger.info(
                "New WebSocket connection. Total: %d", len(self.connections)
            )
            await self._send_initial_data(websocket)
        except Exception as e:
            self.logger.error("Error adding WebSocket connection: %s", e)
            raise

    async def remove_connection(self, websocket: WebSocket):
        """Remove a WebSocket connection from tracking."""
        try:
            self.connections.discard(websocket)
            self.connection_metadata.pop(websocket, None)
            self.stats["active_connections"] = len(self.connections)
            self.logger.info(
                "WebSocket connection removed. Total: %d", len(self.connections)
            )
        except Exception as e:
            self.logger.error("Error removing WebSocket connection: %s", e)

    # ── Broadcast helpers ─────────────────────────────────────────────────────

    async def broadcast_csi_data(self, csi_data: Any, metadata: Dict[str, Any]):
        """Buffer and broadcast a CSI data frame."""
        if not self.is_running:
            return
        csi_list = csi_data.tolist() if isinstance(csi_data, np.ndarray) else csi_data
        entry = {
            "type": "csi_data",
            "timestamp": datetime.now().isoformat(),
            "data": csi_list,
            "metadata": metadata,
        }
        self.csi_buffer.append(entry)
        await self._broadcast_message({
            "type": "csi_update",
            "timestamp": entry["timestamp"],
            "data": csi_list,
            "metadata": metadata,
        })

    async def broadcast_signal(self, signal_payload: Dict[str, Any]):
        """Buffer and broadcast a processed signal payload."""
        if not self.is_running:
            return
        entry = {
            "type": "signal",
            "timestamp": datetime.now().isoformat(),
            "data": signal_payload,
        }
        self.signal_buffer.append(entry)
        await self._broadcast_message({
            "type": "signal",
            "timestamp": entry["timestamp"],
            "data": signal_payload,
        })

    async def broadcast_event(self, event_payload: Dict[str, Any]):
        """Buffer and broadcast an event payload."""
        if not self.is_running:
            return
        entry = {
            "type": "event",
            "timestamp": datetime.now().isoformat(),
            "data": event_payload,
        }
        self.event_buffer.append(entry)
        await self._broadcast_message({
            "type": "event",
            "timestamp": entry["timestamp"],
            "data": event_payload,
        })

    async def broadcast_system_status(self, status_data: Dict[str, Any]):
        """Broadcast a system status message to all connected clients."""
        if not self.is_running:
            return
        await self._broadcast_message({
            "type": "system_status",
            "timestamp": datetime.now().isoformat(),
            "data": status_data,
        })

    async def send_to_connection(self, websocket: WebSocket, message: Dict[str, Any]):
        """Send a message to a specific connection."""
        try:
            if websocket in self.connections:
                await websocket.send_text(json.dumps(message))
                self.stats["messages_sent"] += 1
        except Exception as e:
            self.logger.error("Error sending message to connection: %s", e)
            self.stats["messages_failed"] += 1
            await self.remove_connection(websocket)

    async def _broadcast_message(self, message: Dict[str, Any]):
        """Send a message to all connected clients; prune disconnected ones."""
        if not self.connections:
            return
        payload = json.dumps(message)
        disconnected: Set[WebSocket] = set()
        for ws in self.connections.copy():
            try:
                await ws.send_text(payload)
                self.stats["messages_sent"] += 1
            except Exception as e:
                self.logger.warning("Failed to send to connection: %s", e)
                self.stats["messages_failed"] += 1
                disconnected.add(ws)
        for ws in disconnected:
            await self.remove_connection(ws)
        if message.get("type") in ("csi_update", "signal", "event"):
            self.stats["data_points_streamed"] += 1

    async def _send_initial_data(self, websocket: WebSocket):
        """Send recent buffered data to a newly connected client."""
        try:
            if self.csi_buffer:
                await self.send_to_connection(websocket, {
                    "type": "initial_csi",
                    "timestamp": datetime.now().isoformat(),
                    "data": list(self.csi_buffer)[-5:],
                })
            if self.signal_buffer:
                await self.send_to_connection(websocket, {
                    "type": "initial_signals",
                    "timestamp": datetime.now().isoformat(),
                    "data": list(self.signal_buffer)[-10:],
                })
            status = await self.get_status()
            await self.send_to_connection(websocket, {
                "type": "service_status",
                "timestamp": datetime.now().isoformat(),
                "data": status,
            })
        except Exception as e:
            self.logger.error("Error sending initial data: %s", e)

    # ── Background loop ───────────────────────────────────────────────────────

    async def _streaming_loop(self):
        """Periodic heartbeat loop."""
        try:
            while self.is_running:
                if self.connections:
                    await self._broadcast_message({
                        "type": "heartbeat",
                        "timestamp": datetime.now().isoformat(),
                        "active_connections": len(self.connections),
                    })
                await asyncio.sleep(self.ping_interval)
        except asyncio.CancelledError:
            self.logger.info("Streaming loop cancelled")
        except Exception as e:
            self.logger.error("Error in streaming loop: %s", e)
            self.last_error = str(e)

    async def _close_all_connections(self):
        """Close all WebSocket connections gracefully."""
        to_close = list(self.connections)
        for ws in to_close:
            try:
                await ws.close()
            except Exception as e:
                self.logger.warning("Error closing connection: %s", e)
        for ws in to_close:
            await self.remove_connection(ws)

    # ── Buffer access ─────────────────────────────────────────────────────────

    def get_buffer_data(self, buffer_type: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Return recent entries from a named buffer.

        Args:
            buffer_type: One of "csi", "signal", "event".
            limit: Maximum number of entries to return (most recent).
        """
        if buffer_type == "csi":
            return list(self.csi_buffer)[-limit:]
        elif buffer_type == "signal":
            return list(self.signal_buffer)[-limit:]
        elif buffer_type == "event":
            return list(self.event_buffer)[-limit:]
        return []

    # ── Status / metrics ──────────────────────────────────────────────────────

    async def get_status(self) -> Dict[str, Any]:
        """Get service status."""
        return {
            "status": "healthy" if self.is_running and not self.last_error else "unhealthy",
            "running": self.is_running,
            "last_error": self.last_error,
            "connections": {
                "active": len(self.connections),
                "total": self.stats["total_connections"],
            },
            "buffers": {
                "csi_buffer_size": len(self.csi_buffer),
                "signal_buffer_size": len(self.signal_buffer),
                "event_buffer_size": len(self.event_buffer),
                "max_buffer_size": self.buffer_size,
            },
            "statistics": self.stats.copy(),
            "configuration": {
                "buffer_size": self.buffer_size,
                "ping_interval": self.ping_interval,
            },
        }

    async def get_metrics(self) -> Dict[str, Any]:
        """Get stream service metrics."""
        total = self.stats["messages_sent"] + self.stats["messages_failed"]
        success_rate = self.stats["messages_sent"] / max(1, total)
        return {
            "stream_service": {
                "active_connections": self.stats["active_connections"],
                "total_connections": self.stats["total_connections"],
                "messages_sent": self.stats["messages_sent"],
                "messages_failed": self.stats["messages_failed"],
                "message_success_rate": success_rate,
                "data_points_streamed": self.stats["data_points_streamed"],
                "average_latency_ms": self.stats["average_latency_ms"],
            }
        }

    async def get_connection_info(self) -> List[Dict[str, Any]]:
        """Get information about active connections."""
        result = []
        for ws in self.connections:
            meta = self.connection_metadata.get(ws, {})
            result.append({
                "id": id(ws),
                "connected_at": meta.get("connected_at", "unknown"),
                "user_agent": meta.get("user_agent", "unknown"),
                "ip_address": meta.get("ip_address", "unknown"),
                "subscription_types": meta.get("subscription_types", []),
            })
        return result

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check."""
        try:
            status = "healthy" if self.is_running and not self.last_error else "unhealthy"
            return {
                "status": status,
                "message": self.last_error or "Stream service is running normally",
                "active_connections": len(self.connections),
                "metrics": {
                    "messages_sent": self.stats["messages_sent"],
                    "messages_failed": self.stats["messages_failed"],
                    "data_points_streamed": self.stats["data_points_streamed"],
                },
            }
        except Exception as e:
            return {"status": "unhealthy", "message": f"Health check failed: {e}"}

    async def reset(self):
        """Reset buffers and statistics (connections are preserved)."""
        self.csi_buffer.clear()
        self.signal_buffer.clear()
        self.event_buffer.clear()
        self.stats = {
            "active_connections": len(self.connections),
            "total_connections": 0,
            "messages_sent": 0,
            "messages_failed": 0,
            "data_points_streamed": 0,
            "average_latency_ms": 0.0,
        }
        self.last_error = None
        self.logger.info("StreamService reset")

    @property
    def is_active(self) -> bool:
        """Check if stream service is active."""
        return self.is_running

    async def is_ready(self) -> bool:
        """Check if service is ready to accept connections."""
        return self.is_running
