# ADR-002: 6-Node ESP32 Architecture

## Status
Accepted

## Date
2025-06-20

## Context
The monitored facility has 4 rooms (living room, bedroom, kitchen, bathroom). A single
WiFi CSI link cannot reliably cover all rooms due to wall attenuation and dead zones.
We need full spatial coverage with per-zone presence detection.

## Decision
Deploy 6 ESP32-S3 nodes in a multi-link mesh:

| Node | Location       | Role        | Pair        |
|------|---------------|-------------|-------------|
| N1   | Living room A | Tx + Rx     | N2          |
| N2   | Living room B | Tx + Rx     | N1          |
| N3   | Bedroom       | Tx + Rx     | N4          |
| N4   | Kitchen       | Tx + Rx     | N3          |
| N5   | Bathroom      | Tx          | N6          |
| N6   | Hallway       | Rx          | N5          |

- Each node runs custom firmware (`/esp32/csi_node/`) and transmits raw CSI packets
  via UDP unicast to the central `signal-adapter` service on port 5500.
- Packet format: 8-byte header (node_id, seq, timestamp) + 128 subcarrier I/Q pairs.
- Nodes are powered via USB-C with UPS backup; OTA firmware updates via `/firmware-cache`.

## Consequences
- **Positive:** Full coverage across all 4 rooms with overlapping Fresnel zones.
- **Positive:** Per-zone presence and room-level localization (zone accuracy ~95%).
- **Positive:** UDP keeps latency under 5ms from capture to server ingestion.
- **Negative:** 6 nodes increase hardware cost and maintenance surface.
- **Negative:** UDP has no delivery guarantee; packet loss >5% degrades signal quality.
- **Mitigation:** Watchdog (`watchdog.sh`) monitors node heartbeats and triggers alerts
  if a node goes silent for >10 seconds.
