//! ruview-server — HTTP + WebSocket server for the RuView WiFi-CSI system.
//!
//! Rust equivalent of the Python signal-adapter `main.py`.
//! Provides REST endpoints for device/zone state, a learning report,
//! Prometheus metrics, and a WebSocket endpoint for real-time events.

use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Arc;
use std::time::Instant;

use axum::extract::ws::{Message, WebSocket, WebSocketUpgrade};
use axum::extract::State;
use axum::response::IntoResponse;
use axum::routing::get;
use axum::{Json, Router};
use dashmap::DashMap;
use serde::Serialize;

// ---------------------------------------------------------------------------
// Application state
// ---------------------------------------------------------------------------

/// Shared application state, wrapped in `Arc` and passed to all handlers.
pub struct AppState {
    pub devices: DashMap<String, DeviceState>,
    pub zones: Vec<ZoneState>,
    pub csi_frames_total: AtomicU64,
}

impl AppState {
    /// Create a new `AppState` with sensible defaults and demo data.
    pub fn new() -> Self {
        Self {
            devices: DashMap::new(),
            zones: vec![
                ZoneState {
                    id: "zone-1".into(),
                    name: "Living Room".into(),
                    presence_count: 0,
                },
                ZoneState {
                    id: "zone-2".into(),
                    name: "Bedroom".into(),
                    presence_count: 0,
                },
                ZoneState {
                    id: "zone-3".into(),
                    name: "Kitchen".into(),
                    presence_count: 0,
                },
            ],
            csi_frames_total: AtomicU64::new(0),
        }
    }
}

impl Default for AppState {
    fn default() -> Self {
        Self::new()
    }
}

// ---------------------------------------------------------------------------
// Domain types
// ---------------------------------------------------------------------------

/// Per-device state tracked by the server.
pub struct DeviceState {
    pub id: String,
    pub status: String,
    pub x: i32,
    pub y: i32,
    pub rssi: i8,
    pub breathing_bpm: Option<f32>,
    pub heart_rate: Option<f32>,
    pub csi_pose: Option<String>,
    pub last_seen: Instant,
}

/// Zone presence state.
pub struct ZoneState {
    pub id: String,
    pub name: String,
    pub presence_count: u32,
}

// ---------------------------------------------------------------------------
// Serializable response types
// ---------------------------------------------------------------------------

#[derive(Serialize)]
struct HealthResponse {
    status: &'static str,
    version: &'static str,
    csi_frames_total: u64,
}

#[derive(Serialize)]
struct DeviceResponse {
    id: String,
    status: String,
    x: i32,
    y: i32,
    rssi: i8,
    breathing_bpm: Option<f32>,
    heart_rate: Option<f32>,
    csi_pose: Option<String>,
    last_seen_ms_ago: u128,
}

#[derive(Serialize)]
struct ZoneResponse {
    id: String,
    name: String,
    presence_count: u32,
}

#[derive(Serialize)]
struct LearningReportResponse {
    total_frames: u64,
    active_devices: usize,
    zones: Vec<ZoneResponse>,
    model_status: &'static str,
}

// ---------------------------------------------------------------------------
// Router
// ---------------------------------------------------------------------------

/// Build the Axum router with all RuView endpoints.
pub fn create_router(state: Arc<AppState>) -> Router {
    Router::new()
        .route("/health", get(health))
        .route("/api/devices", get(list_devices))
        .route("/api/zones", get(list_zones))
        .route("/api/learning-report", get(learning_report))
        .route("/metrics", get(prometheus_metrics))
        .route("/ws/events", get(ws_handler))
        .with_state(state)
}

// ---------------------------------------------------------------------------
// Handlers
// ---------------------------------------------------------------------------

/// GET /health — liveness / readiness probe.
async fn health(State(state): State<Arc<AppState>>) -> Json<HealthResponse> {
    Json(HealthResponse {
        status: "ok",
        version: env!("CARGO_PKG_VERSION"),
        csi_frames_total: state.csi_frames_total.load(Ordering::Relaxed),
    })
}

/// GET /api/devices — list all known devices and their latest state.
async fn list_devices(State(state): State<Arc<AppState>>) -> Json<Vec<DeviceResponse>> {
    let now = Instant::now();
    let devices: Vec<DeviceResponse> = state
        .devices
        .iter()
        .map(|entry| {
            let d = entry.value();
            DeviceResponse {
                id: d.id.clone(),
                status: d.status.clone(),
                x: d.x,
                y: d.y,
                rssi: d.rssi,
                breathing_bpm: d.breathing_bpm,
                heart_rate: d.heart_rate,
                csi_pose: d.csi_pose.clone(),
                last_seen_ms_ago: now.duration_since(d.last_seen).as_millis(),
            }
        })
        .collect();
    Json(devices)
}

/// GET /api/zones — list all zones with current presence counts.
async fn list_zones(State(state): State<Arc<AppState>>) -> Json<Vec<ZoneResponse>> {
    let zones: Vec<ZoneResponse> = state
        .zones
        .iter()
        .map(|z| ZoneResponse {
            id: z.id.clone(),
            name: z.name.clone(),
            presence_count: z.presence_count,
        })
        .collect();
    Json(zones)
}

/// GET /api/learning-report — summary of the system's learning state.
async fn learning_report(State(state): State<Arc<AppState>>) -> Json<LearningReportResponse> {
    let zones: Vec<ZoneResponse> = state
        .zones
        .iter()
        .map(|z| ZoneResponse {
            id: z.id.clone(),
            name: z.name.clone(),
            presence_count: z.presence_count,
        })
        .collect();

    Json(LearningReportResponse {
        total_frames: state.csi_frames_total.load(Ordering::Relaxed),
        active_devices: state.devices.len(),
        zones,
        model_status: "idle",
    })
}

/// GET /metrics — Prometheus-compatible text metrics.
async fn prometheus_metrics(State(state): State<Arc<AppState>>) -> impl IntoResponse {
    let frames = state.csi_frames_total.load(Ordering::Relaxed);
    let devices = state.devices.len();

    let body = format!(
        "# HELP ruview_csi_frames_total Total CSI frames received.\n\
         # TYPE ruview_csi_frames_total counter\n\
         ruview_csi_frames_total {frames}\n\
         # HELP ruview_active_devices Number of active devices.\n\
         # TYPE ruview_active_devices gauge\n\
         ruview_active_devices {devices}\n"
    );

    (
        [(
            axum::http::header::CONTENT_TYPE,
            "text/plain; version=0.0.4; charset=utf-8",
        )],
        body,
    )
}

/// GET /ws/events — WebSocket upgrade for real-time event streaming.
async fn ws_handler(
    ws: WebSocketUpgrade,
    State(_state): State<Arc<AppState>>,
) -> impl IntoResponse {
    ws.on_upgrade(handle_ws)
}

/// Handle an individual WebSocket connection.
///
/// Sends a welcome message and then echoes back any text frames received.
/// The connection stays alive until the client disconnects.
async fn handle_ws(mut socket: WebSocket) {
    // Send a welcome message so the client knows the connection is live.
    let welcome = serde_json::json!({
        "type": "connected",
        "message": "RuView event stream",
    });
    if socket
        .send(Message::Text(welcome.to_string().into()))
        .await
        .is_err()
    {
        return;
    }

    // Keep the connection alive: read frames and echo them back.
    while let Some(Ok(msg)) = socket.recv().await {
        match msg {
            Message::Text(text) => {
                let ack = serde_json::json!({
                    "type": "ack",
                    "echo": text.to_string(),
                });
                if socket
                    .send(Message::Text(ack.to_string().into()))
                    .await
                    .is_err()
                {
                    break;
                }
            }
            Message::Ping(data) => {
                if socket.send(Message::Pong(data)).await.is_err() {
                    break;
                }
            }
            Message::Close(_) => break,
            _ => {}
        }
    }
}
