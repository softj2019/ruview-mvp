"""
Unit tests for bridge_client.py

Covers:
- BridgeClient initial state
- send() when disconnected (no-op, no crash)
- send() when connected (increments message_count)
- stop() sets _stopped flag and closes websocket
- _connection_loop: successful connect, on_connected callback, message handling
- _connection_loop: reconnect backoff on failure
"""
import asyncio
import json
import sys
import os

import pytest


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bridge_client import BridgeClient, RECONNECT_BASE_S, RECONNECT_MAX_S

LOOP_TEST_TIMEOUT = 3.0  # seconds — guard against hung event loops


# ---------------------------------------------------------------------------
# Helpers / Fakes
# ---------------------------------------------------------------------------

class _FakeWS:
    """Minimal fake WebSocket protocol."""

    def __init__(self, messages=None):
        self.sent: list[str] = []
        self._messages = messages or []
        self._closed = False

    async def send(self, data: str):
        self.sent.append(data)

    async def close(self):
        self._closed = True

    def __aiter__(self):
        return self._iter_messages()

    async def _iter_messages(self):
        for msg in self._messages:
            yield msg


# ---------------------------------------------------------------------------
# Initial state
# ---------------------------------------------------------------------------

def test_initial_state():
    client = BridgeClient(url="ws://relay.example.com", session_id="sess-1")
    assert client.is_connected is False
    assert client.message_count == 0
    assert client._stopped is False


# ---------------------------------------------------------------------------
# send() — disconnected (no-op)
# ---------------------------------------------------------------------------

async def test_send_when_disconnected_no_crash():
    client = BridgeClient(url="ws://relay.example.com", session_id="sess-1")
    # Should not raise even though _ws is None
    await client.send(json.dumps({"type": "test"}))
    assert client.message_count == 0


# ---------------------------------------------------------------------------
# send() — connected
# ---------------------------------------------------------------------------

async def test_send_when_connected_increments_count():
    client = BridgeClient(url="ws://relay.example.com", session_id="sess-1")
    fake_ws = _FakeWS()
    client._ws = fake_ws
    client._connected = True

    await client.send('{"type":"heartbeat"}')
    await client.send('{"type":"data"}')

    assert client.message_count == 2
    assert len(fake_ws.sent) == 2


async def test_send_clears_connected_on_ws_error():
    """send() catches exceptions from the websocket and marks disconnected."""

    class _ErrorWS(_FakeWS):
        async def send(self, data: str):
            raise OSError("broken pipe")

    client = BridgeClient(url="ws://relay.example.com", session_id="sess-1")
    client._ws = _ErrorWS()
    client._connected = True

    await client.send("data")

    assert client._connected is False
    assert client.message_count == 0


# ---------------------------------------------------------------------------
# stop()
# ---------------------------------------------------------------------------

async def test_stop_sets_flag():
    client = BridgeClient(url="ws://relay.example.com", session_id="sess-1")
    client.stop()
    assert client._stopped is True


async def test_stop_closes_websocket():
    client = BridgeClient(url="ws://relay.example.com", session_id="sess-1")
    fake_ws = _FakeWS()
    client._ws = fake_ws
    client._connected = True

    client.stop()
    # The close task needs to run
    await asyncio.sleep(0)

    assert client._stopped is True
    assert fake_ws._closed is True


# ---------------------------------------------------------------------------
# _connection_loop helpers
# ---------------------------------------------------------------------------

def _make_stop_after_connect(client, connected_event: asyncio.Event, ws_obj=None):
    """Returns a fake websockets.connect CM that fires connected_event then stops client."""

    class _FakeConnect:
        def __init__(self, url, additional_headers=None):
            pass

        async def __aenter__(self):
            ws = ws_obj if ws_obj is not None else _FakeWS()
            connected_event.set()
            client._stopped = True  # stop after first connect
            return ws

        async def __aexit__(self, *args):
            pass

    return lambda url, additional_headers=None: _FakeConnect(url)


async def _run_loop_until_event(client, event: asyncio.Event, timeout=LOOP_TEST_TIMEOUT):
    """Run _connection_loop until event is set (or timeout)."""
    task = asyncio.create_task(client._connection_loop())
    try:
        await asyncio.wait_for(event.wait(), timeout=timeout)
    finally:
        client._stopped = True
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


# ---------------------------------------------------------------------------
# _connection_loop — successful connect
# ---------------------------------------------------------------------------

async def test_connection_loop_connected_state(monkeypatch):
    """_connected=True and backoff reset when connection succeeds."""
    import bridge_client as bc

    connected_event = asyncio.Event()
    client = BridgeClient(url="ws://relay.example.com", session_id="sess-1")
    monkeypatch.setattr(bc.websockets, "connect", _make_stop_after_connect(client, connected_event))

    await _run_loop_until_event(client, connected_event)

    assert connected_event.is_set()
    assert client._reconnect_delay == RECONNECT_BASE_S


# ---------------------------------------------------------------------------
# _connection_loop — on_connected callback
# ---------------------------------------------------------------------------

async def test_connection_loop_on_connected_callback(monkeypatch):
    """on_connected is called and its return value is sent to the relay."""
    import bridge_client as bc

    sent_init: list[str] = []
    connected_event = asyncio.Event()

    class _TrackWS(_FakeWS):
        async def send(self, data: str):
            sent_init.append(data)
            await super().send(data)

    async def on_connected():
        return json.dumps({"type": "init", "state": "ready"})

    client = BridgeClient(url="ws://relay.example.com", session_id="sess-1", on_connected=on_connected)
    monkeypatch.setattr(
        bc.websockets, "connect",
        _make_stop_after_connect(client, connected_event, ws_obj=_TrackWS()),
    )

    await _run_loop_until_event(client, connected_event)

    assert len(sent_init) >= 1
    parsed = json.loads(sent_init[0])
    assert parsed["type"] == "init"


# ---------------------------------------------------------------------------
# _connection_loop — incoming message handling
# ---------------------------------------------------------------------------

async def test_connection_loop_handles_incoming_messages(monkeypatch, capsys):
    """Messages from front-end clients are logged without crashing."""
    import bridge_client as bc

    messages = [
        json.dumps({"type": "config_update", "value": 42}),
        "not-valid-json",
    ]
    connected_event = asyncio.Event()
    client = BridgeClient(url="ws://relay.example.com", session_id="sess-1")
    monkeypatch.setattr(
        bc.websockets, "connect",
        _make_stop_after_connect(client, connected_event, ws_obj=_FakeWS(messages=messages)),
    )

    await _run_loop_until_event(client, connected_event)

    captured = capsys.readouterr()
    assert "config_update" in captured.out


# ---------------------------------------------------------------------------
# _connection_loop — backoff on failure
# ---------------------------------------------------------------------------

async def test_connection_loop_backoff_on_failure(monkeypatch):
    """asyncio.sleep is called with a delay after a failed connection attempt."""
    import bridge_client as bc

    sleep_calls: list[float] = []
    sleep_called = asyncio.Event()

    async def _fake_sleep(delay):
        sleep_calls.append(delay)
        sleep_called.set()
        client._stopped = True  # stop after first backoff

    monkeypatch.setattr(bc.asyncio, "sleep", _fake_sleep)
    monkeypatch.setattr(bc.websockets, "connect", None)  # raises TypeError on call

    client = BridgeClient(url="ws://relay.example.com", session_id="sess-1")

    await _run_loop_until_event(client, sleep_called)

    assert len(sleep_calls) >= 1
    assert sleep_calls[0] == RECONNECT_BASE_S


# ---------------------------------------------------------------------------
# Constants sanity check
# ---------------------------------------------------------------------------

def test_reconnect_constants():
    assert RECONNECT_BASE_S == 1.0
    assert RECONNECT_MAX_S == 32.0
    assert RECONNECT_MAX_S > RECONNECT_BASE_S
