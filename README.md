# RuView — WiFi CSI 비접촉 재실 감지 + 생체신호 모니터링

## Overview

WiFi CSI (Channel State Information) sensing system for non-contact presence detection and vital sign monitoring. 6 ESP32-S3 nodes transmit CSI data via UDP to a Python backend, which fuses it with YOLOv8-pose camera detections for accurate occupancy counting and 3D visualization.

## Features

- **CSI Processing**: Subcarrier amplitude/phase extraction, Welford z-score presence detection, multi-person separation via clustering
- **Vital Signs**: Breathing rate (8-25 BPM) and heart rate (50-100 BPM) extraction from CSI phase variation
- **Camera Fusion**: YOLOv8-pose person detection + CSI pose classification with weighted confidence fusion
- **Kalman-smoothed Presence**: 1D Kalman filter for stable presenceCount estimation
- **3D Visualization**: Three.js real-time floor plan with device positions, zone overlays, heatmaps
- **Multi-zone**: 4-room layout with per-zone presence counts, auto device-zone assignment
- **Event Engine**: Fall detection, anomaly alerts, severity-based event broadcasting
- **Cloud Relay**: Cloudflare Workers bridge for external dashboard access
- **Empty-room Calibration**: One-click baseline capture, Welford tracker reset
- **Learning Reports**: Hourly auto-generated calibration & presence summaries

## Architecture

```
ESP32-S3 x6 ──UDP──▶ signal-adapter (FastAPI :5280)
                          │
    camera-service ──POST─┤  ◀── YOLOv8-pose
                          │
                     ┌────┴────┐
                     │ CSI Proc│  Welford / Kalman / EventEngine
                     └────┬────┘
                          │
              ┌───────────┼───────────┐
              ▼           ▼           ▼
         WebSocket    Supabase    Bridge→CF Workers
              │                       │
         Dashboard               Cloud Dashboard
       localhost:5280      ruview-monitor.pages.dev
```

## Quick Start

```bash
bash start_all.sh
```

- **Dashboard**: http://localhost:5280
- **Cloud**: https://ruview-monitor.pages.dev
- **Health**: `GET http://localhost:5280/health`

## Node Layout

```
┌─────────────┬─────────────┬─────────────┬─────────────┐
│  Room 1001  │  Room 1002  │  Room 1003  │  Room 1004  │
│             │             │             │             │
│ [N2]        │             │    [N5]     │       [N3]  │
│  A2         │             │     F2      │        H1   │
│             │             │             │             │
│             │             │             │    [N4]     │
│             │             │             │     G4      │
│             │             │             │             │
│ [N1]        │    [N6]     │             │             │
│  A5         │     D5      │             │             │
└─────────────┴─────────────┴─────────────┴─────────────┘
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Firmware | ESP-IDF C, WiFi CSI API |
| Backend | Python 3.11, FastAPI, NumPy, Pydantic |
| Frontend | React 18, Three.js (R3F), Recharts, TailwindCSS |
| AI/ML | YOLOv8-pose (camera), CSI subcarrier clustering |
| Cloud | Cloudflare Workers + Pages, Supabase (PostgreSQL) |
| Infra | Docker Compose, pnpm workspaces, Turborepo |

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Service health check |
| GET | `/api/devices` | List all ESP32 nodes |
| PUT | `/api/devices/{id}/position` | Update node position (drag-drop) |
| GET | `/api/zones` | List zones with presence counts |
| PUT | `/api/zones/presence` | Manual presence override |
| DELETE | `/api/zones/presence` | Clear manual override |
| POST | `/api/camera/detections` | Camera detection ingestion |
| POST | `/api/calibration/empty-room` | Empty-room baseline capture |
| GET | `/api/learning-report` | Current learning report |
| POST | `/api/csi/ingest` | Direct CSI data ingestion |
| WS | `/ws/events` | Real-time event stream |

## Phase Workflow

See [docs/PHASE_WORKFLOW.md](docs/PHASE_WORKFLOW.md) for the full development phase plan.

## License

MIT
