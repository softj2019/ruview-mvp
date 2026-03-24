# Example Scripts

Standalone helper scripts for interacting with the ruView system.

## Scripts

| Script | Description |
|--------|-------------|
| [basic_monitor.py](basic_monitor.py) | Connect to signal-adapter WebSocket and display real-time presence, per-zone status, and vitals in the terminal. |
| [fall_recorder.py](fall_recorder.py) | Interactive tool for labelling fall / non-fall events and recording them via the `/api/fall/record` endpoint for ML training. |

## Prerequisites

```bash
pip install websockets requests
```

## Usage

```bash
# Real-time monitor
python examples/basic_monitor.py

# Fall event recorder (interactive)
python examples/fall_recorder.py
```
