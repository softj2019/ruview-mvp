//! ruview-wasm — WebAssembly bindings for the RuView WiFi-CSI system.
//!
//! Exposes key signal-processing and classification functions to JavaScript
//! via `wasm-bindgen`.

use wasm_bindgen::prelude::*;

use ruview_core::CsiFrame;
use ruview_signal::{classify_pose as do_classify_pose, hampel_filter as do_hampel_filter};

// ---------------------------------------------------------------------------
// Serializable result for process_csi
// ---------------------------------------------------------------------------

#[derive(serde::Serialize)]
struct ProcessedCsiJs {
    node_id: u8,
    n_subcarriers: u16,
    frequency_mhz: u32,
    sequence: u32,
    rssi: i8,
    noise_floor: i8,
    amplitudes: Vec<f32>,
    phases: Vec<f32>,
}

// ---------------------------------------------------------------------------
// Exported functions
// ---------------------------------------------------------------------------

/// Parse a raw CSI binary frame and return a JSON object with the parsed
/// header fields, amplitudes, and phases.
///
/// Returns a `JsValue` containing the serialized `ProcessedCsiJs`.
/// On parse failure, returns a JS error string.
#[wasm_bindgen]
pub fn process_csi(data: &[u8]) -> JsValue {
    match CsiFrame::parse(data) {
        Ok(frame) => {
            let result = ProcessedCsiJs {
                node_id: frame.node_id,
                n_subcarriers: frame.n_subcarriers,
                frequency_mhz: frame.frequency_mhz,
                sequence: frame.sequence,
                rssi: frame.rssi,
                noise_floor: frame.noise_floor,
                amplitudes: frame.amplitudes(),
                phases: frame.phases(),
            };
            serde_wasm_bindgen::to_value(&result).unwrap_or(JsValue::NULL)
        }
        Err(e) => {
            // Return the error as a JS string so the caller can handle it.
            JsValue::from_str(&format!("{}", e))
        }
    }
}

/// Apply Hampel filter to the input data, replacing outliers with the local
/// median.  Uses a half-window of 3 and threshold of 3.0 (standard defaults).
///
/// Returns the filtered data as a new `Vec<f32>`.
#[wasm_bindgen]
pub fn hampel_filter(data: Vec<f32>) -> Vec<f32> {
    let mut filtered = data;
    do_hampel_filter(&mut filtered, 3, 3.0);
    filtered
}

/// Classify the current pose/activity from a motion index value.
///
/// Returns a string label: "empty", "stationary", "sitting", "walking",
/// or "running".
#[wasm_bindgen]
pub fn classify_pose(motion: f32) -> String {
    let (label, _confidence) = do_classify_pose(motion, None);
    label.into()
}
