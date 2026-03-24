# ADR-005: Three.js 3D Observatory

## Status
Accepted

## Date
2025-07-20

## Context
The ruView dashboard needs to display real-time spatial data (CSI heatmaps, presence
zones, vitals, alerts) in an intuitive format. Traditional 2D dashboards cannot
effectively convey spatial relationships between rooms, sensor nodes, and detected
persons. We need a 3D visualization that runs at 60fps in the browser.

## Decision
Build a Three.js-based "Observatory" view with modular visualization layers:

1. **Floor plan mesh:** Room geometry loaded from `/apps/ruview-dashboard/assets/floorplan.glb`.
2. **CSI Heatmap:** `CanvasTexture` rendered from a 64x64 grid of CSI power values,
   projected onto the floor plane. Updated at 10fps via WebSocket.
3. **Signal floor:** `InstancedMesh` with ~500 bar instances representing per-subcarrier
   amplitude. Provides a "signal forest" view of raw CSI activity.
4. **Presence markers:** Animated spheres at estimated person positions, color-coded
   by activity state (green=active, yellow=sedentary, red=alert).
5. **Vitals Oracle:** Floating HUD panels attached to presence markers showing real-time
   breathing rate, heart rate, and confidence scores.
6. **Fall alert overlay:** Full-screen red pulse animation triggered on fall detection.

Additional modules: Zone boundaries, node positions, Fresnel ellipses, signal paths,
historical replay timeline, camera feed PiP.

Rendering budget: All modules combined must maintain 60fps on mid-range hardware
(GTX 1060 / M1 MacBook Air). `InstancedMesh` and texture atlasing keep draw calls <50.

## Consequences
- **Positive:** 60fps achieved with 10+ simultaneous visualization modules.
- **Positive:** Spatial context makes it intuitive for non-technical caregivers.
- **Positive:** Modular layer system allows toggling individual visualizations.
- **Negative:** Three.js bundle adds ~600KB (gzipped) to the dashboard.
- **Negative:** WebGL not supported on some older mobile browsers; 2D fallback needed.
- **Trade-off:** Canvas-based heatmap limits resolution to 64x64 but keeps GPU load low.
