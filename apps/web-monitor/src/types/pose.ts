/**
 * COCO-17 keypoint 기반 포즈 감지 타입 정의 — Phase 5-3
 */

/** 단일 COCO keypoint */
export interface Keypoint17 {
  x: number;      // 정규화 좌표 [0,1] 또는 픽셀 좌표
  y: number;
  score: number;  // 신뢰도 [0,1]
  name: string;   // e.g. 'nose', 'left_eye', ...
}

/** 한 사람의 포즈 데이터 */
export interface PoseData {
  personId: string;
  keypoints: Keypoint17[];          // 길이 17 (COCO-17 순서)
  confidence: number;               // 전체 포즈 신뢰도
  bbox?: [number, number, number, number]; // [x, y, w, h] 정규화
}
