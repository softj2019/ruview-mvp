/**
 * BodyModel — DensePose 24부위 3D 인체 메시 컴포넌트
 *
 * body-model.js (ruvnet-RuView) 로직을 React 19 + TypeScript 컴포넌트로 변환.
 * 단일 인물 클래스 로직: singleBodyModel.ts
 * 최대 maxModels(기본 6)인 멀티 트래킹을 지원한다.
 *
 * Props:
 *   persons  — 감지된 인물 목록 (COCO 17-keypoint 포맷)
 *   scene    — useThreeScene 의 sceneRef.current
 *   onUpdate — useThreeScene 의 onUpdate (프레임 애니메이션용)
 */
import { useEffect, useRef } from 'react';
import type * as THREE from 'three';
import { SingleBodyModel } from './singleBodyModel';

// ---- 타입 정의 ----------------------------------------------------------------

/** COCO 17-keypoint 형식의 개별 키포인트 */
export interface Keypoint {
  x: number;           // 정규화 [0,1]
  y: number;           // 정규화 [0,1] (0=상단)
  confidence: number;
}

/** DensePose 파트 신뢰도 맵  { partId: confidence } */
export type BodyPartConfidences = Record<number, number>;

export interface PersonData {
  id?: string;
  keypoints?: Keypoint[];
  confidence?: number;
  body_parts?: BodyPartConfidences;
}

export interface BodyModelProps {
  persons: PersonData[];
  scene: THREE.Scene;
  onUpdate: (cb: (delta: number, elapsed: number) => void) => () => void;
  /** 비활성 인물 제거 대기 시간 (ms). 기본 3000 */
  inactiveTimeout?: number;
  /** 최대 동시 모델 수. 기본 6 */
  maxModels?: number;
}

// ---- DensePose 파트 ID (외부 참조용) -----------------------------------------

export const DENSEPOSE_PARTS = {
  TORSO_BACK: 1, TORSO_FRONT: 2,
  RIGHT_HAND: 3, LEFT_HAND: 4,
  LEFT_FOOT: 5,  RIGHT_FOOT: 6,
  RIGHT_UPPER_LEG_BACK: 7,  LEFT_UPPER_LEG_BACK: 8,
  RIGHT_UPPER_LEG_FRONT: 9, LEFT_UPPER_LEG_FRONT: 10,
  RIGHT_LOWER_LEG_BACK: 11, LEFT_LOWER_LEG_BACK: 12,
  RIGHT_LOWER_LEG_FRONT: 13,LEFT_LOWER_LEG_FRONT: 14,
  LEFT_UPPER_ARM_FRONT: 15,  RIGHT_UPPER_ARM_FRONT: 16,
  LEFT_UPPER_ARM_BACK: 17,   RIGHT_UPPER_ARM_BACK: 18,
  LEFT_LOWER_ARM_FRONT: 19,  RIGHT_LOWER_ARM_FRONT: 20,
  LEFT_LOWER_ARM_BACK: 21,   RIGHT_LOWER_ARM_BACK: 22,
  HEAD_RIGHT: 23, HEAD_LEFT: 24,
} as const;

// ---- 컴포넌트 -----------------------------------------------------------------

/**
 * 씬에 최대 6인의 3D 인체 모델을 렌더링하는 컴포넌트. DOM을 렌더링하지 않는다.
 *
 * @example
 * ```tsx
 * const { sceneRef, onUpdate } = useThreeScene();
 * if (sceneRef.current) {
 *   return <BodyModel persons={persons} scene={sceneRef.current} onUpdate={onUpdate} />;
 * }
 * ```
 */
export default function BodyModel({
  persons,
  scene,
  onUpdate,
  inactiveTimeout = 3000,
  maxModels = 6,
}: BodyModelProps) {
  const modelsRef  = useRef<Map<string, SingleBodyModel>>(new Map());
  const lastSeenRef = useRef<Map<string, number>>(new Map());

  // ── 프레임 애니메이션 (update + 비활성 정리) ────────────────────────────
  useEffect(() => {
    const unregister = onUpdate((delta) => {
      const now    = Date.now();
      const models = modelsRef.current;
      const seen   = lastSeenRef.current;

      // 비활성 모델 제거
      for (const [id, lastTime] of seen.entries()) {
        if (now - lastTime > inactiveTimeout) {
          const model = models.get(id);
          if (model) {
            scene.remove(model.group);
            model.dispose();
            models.delete(id);
          }
          seen.delete(id);
        }
      }

      // 프레임 애니메이션
      for (const model of models.values()) {
        model.update(delta);
      }
    });
    return unregister;
  }, [onUpdate, scene, inactiveTimeout]);

  // ── persons 변경 시 모델 생성/업데이트 ──────────────────────────────────
  useEffect(() => {
    const now    = Date.now();
    const models = modelsRef.current;
    const seen   = lastSeenRef.current;

    for (let i = 0; i < Math.min(persons.length, maxModels); i++) {
      const person   = persons[i];
      const personId = person.id ?? `person_${i}`;

      let model = models.get(personId);
      if (!model) {
        model = new SingleBodyModel();
        models.set(personId, model);
        scene.add(model.group);
      }

      if (person.keypoints) {
        model.updateFromKeypoints(person.keypoints, person.confidence ?? 0);
      }
      if (person.body_parts) {
        model.activateParts(person.body_parts);
      }

      seen.set(personId, now);
    }
  }, [persons, scene, maxModels]);

  // ── 언마운트 정리 ────────────────────────────────────────────────────────
  useEffect(() => {
    return () => {
      for (const model of modelsRef.current.values()) {
        scene.remove(model.group);
        model.dispose();
      }
      modelsRef.current.clear();
      lastSeenRef.current.clear();
    };
  }, [scene]);

  return null;
}

// ---- 편의 훅 (activeCount, avgConfidence 조회) --------------------------------

export function useBodyModelStats(
  modelsRef: React.RefObject<Map<string, SingleBodyModel> | null>
): { activeCount: number; avgConfidence: number } {
  const models = modelsRef.current;
  if (!models || models.size === 0) return { activeCount: 0, avgConfidence: 0 };
  let sum = 0;
  for (const m of models.values()) sum += m.confidence;
  return { activeCount: models.size, avgConfidence: sum / models.size };
}
