"""
Bridge Client — Outbound WebSocket tunnel to Cloudflare Worker.

Maintains a persistent connection from the office network to
the Cloudflare Durable Object broker, enabling external browser
access to real-time sensing data without inbound port forwarding.

Pattern from aimix: gateway/src/bridge-client.ts
"""
import asyncio
import json
import os
import time

import websockets

RECONNECT_BASE_S = 1.0
RECONNECT_MAX_S = 32.0


class BridgeClient:
    def __init__(self, url: str, session_id: str, token: str | None = None,
                 on_connected: "callable | None" = None):
        self.url = url
        self.session_id = session_id
        self.token = token
        self.on_connected = on_connected  # Called when bridge connects
        self._ws: websockets.WebSocketClientProtocol | None = None
        self._reconnect_delay = RECONNECT_BASE_S
        self._stopped = False
        self._connected = False
        self._message_count = 0

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def message_count(self) -> int:
        return self._message_count

    async def start(self):
        """Start the bridge connection loop (non-blocking)."""
        self._stopped = False
        asyncio.create_task(self._connection_loop())

    def stop(self):
        """Stop the bridge and close the connection."""
        self._stopped = True
        if self._ws:
            asyncio.create_task(self._ws.close())

    async def send(self, data: str):
        """Send data to the Cloudflare Worker (relayed to front clients)."""
        if self._ws and self._connected:
            try:
                await self._ws.send(data)
                self._message_count += 1
            except Exception:
                self._connected = False

    async def _connection_loop(self):
        """Maintain persistent connection with exponential backoff."""
        while not self._stopped:
            try:
                ws_url = f"{self.url}/api/agent/ws?session={self.session_id}"
                headers = {}
                if self.token:
                    headers["Authorization"] = f"Bearer {self.token}"

                print(f"[bridge] Connecting to {ws_url}...")
                async with websockets.connect(ws_url, additional_headers=headers) as ws:
                    self._ws = ws
                    self._connected = True
                    self._reconnect_delay = RECONNECT_BASE_S
                    print(f"[bridge] Connected to Cloudflare relay")

                    # Send initial state to front clients
                    if self.on_connected:
                        try:
                            init_data = await self.on_connected()
                            if init_data:
                                await ws.send(init_data)
                                print(f"[bridge] Sent init state to relay")
                        except Exception:
                            pass

                    async for message in ws:
                        # Front → Agent messages (commands from external browser)
                        # Currently we just log them; future: handle config changes
                        try:
                            msg = json.loads(message)
                            msg_type = msg.get("type", "unknown")
                            print(f"[bridge] Received from front: {msg_type}")
                        except json.JSONDecodeError:
                            pass

            except Exception as e:
                self._connected = False
                self._ws = None
                if not self._stopped:
                    print(f"[bridge] Disconnected: {e}. Reconnecting in {self._reconnect_delay:.0f}s...")
                    await asyncio.sleep(self._reconnect_delay)
                    self._reconnect_delay = min(
                        self._reconnect_delay * 2, RECONNECT_MAX_S
                    )
