# ADR-003: Camera + CSI Sensor Fusion

## Status
Accepted

## Date
2025-07-01

## Context
Camera-based pose estimation (YOLOv8-pose) provides accurate posture classification but
fails in darkness, occlusion, and raises privacy concerns. CSI-based motion detection
works through walls and in darkness but lacks fine-grained pose information. Neither
modality alone meets the reliability target of 95% fall detection accuracy.

## Decision
Implement weighted sensor fusion combining both modalities:

- **Camera branch:** YOLOv8-pose running on GPU server produces a posture vector
  (standing / sitting / lying / falling) with per-class confidence scores.
- **CSI branch:** Signal-adapter produces a motion descriptor (static / moving /
  sudden-drop) based on variance and derivative of filtered CSI amplitude.
- **Fusion weights:** Camera 80%, CSI 20% (default). Weights shift to CSI 100% when
  camera confidence drops below 0.3 (e.g., darkness, occlusion).
- **Agreement boost:** When both modalities agree on "fall", confidence is boosted to
  min(combined, 0.95). Disagreement triggers a 5-second observation window before alert.
- Fusion logic lives in `services/fall-detector/fusion.ts`.

## Consequences
- **Positive:** Combined accuracy reaches 0.95+ when both modalities agree, exceeding
  either modality alone (camera 0.88, CSI 0.72 in isolation).
- **Positive:** Graceful degradation -- system remains functional with only CSI in
  low-visibility conditions.
- **Negative:** Dual-modality increases system complexity and debugging difficulty.
- **Negative:** 5-second disagreement window adds latency to some edge-case alerts.
- **Trade-off:** Privacy concerns from camera are mitigated by on-premise processing
  with no cloud upload of video frames.
