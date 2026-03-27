/**
 * EnvironmentLayer — 3D 방 환경 컴포넌트
 *
 * environment.js (ruvnet-RuView) 로직을 React 19 + TypeScript 컴포넌트로 변환.
 * useThreeScene 훅의 scene을 props로 받아 방 환경 객체를 렌더링한다.
 *
 * 포함 요소:
 *  - 바닥(Phong), 그리드 라인, 반투명 벽 + 엣지 라인
 *  - TX/RX 마커 (콘 + PointLight + 스프라이트 레이블)
 *  - WiFi 신호경로 대시선
 *  - 감지존 링/필 + 레이블
 *  - 신뢰도 히트맵 (20×15 셀)
 *  - AP/RX 맥동 + 신호선 애니메이션 (onUpdate 콜백 등록)
 *
 * 씬 구성 순수 함수: environmentHelpers.ts
 */
import { useEffect, useRef } from 'react';
import * as THREE from 'three';
import {
  buildFloor, buildGrid, buildWalls,
  buildAPMarkers, buildSignalPaths,
  buildDetectionZones, buildConfidenceHeatmap,
} from './environmentHelpers';

// ---- 타입 정의 ----------------------------------------------------------------

export interface APConfig {
  id: string;
  pos: [number, number, number];
  type: 'transmitter' | 'receiver';
}

export interface ZoneConfig {
  id: string;
  center: [number, number, number];
  radius: number;
  color: number;
  label: string;
}

export interface ZoneOccupancy {
  [zoneId: string]: number;
}

/** confidenceMap: Float32Array(cols*rows) 또는 number[][] */
export type ConfidenceMap = Float32Array | number[][];

export interface EnvironmentLayerProps {
  scene: THREE.Scene;
  /** 업데이트 콜백 등록 함수 (useThreeScene의 onUpdate) */
  onUpdate: (cb: (delta: number, elapsed: number) => void) => () => void;
  zoneOccupancy?: ZoneOccupancy;
  confidenceMap?: ConfidenceMap;
  roomWidth?: number;
  roomDepth?: number;
  roomHeight?: number;
  accessPoints?: APConfig[];
  receivers?: APConfig[];
  zones?: ZoneConfig[];
}

// ---- 기본 상수 ----------------------------------------------------------------

const DEFAULT_ACCESS_POINTS: APConfig[] = [
  { id: 'TX1', pos: [-3.5, 2.5, -2.8], type: 'transmitter' },
  { id: 'TX2', pos: [0, 2.5, -2.8],    type: 'transmitter' },
  { id: 'TX3', pos: [3.5, 2.5, -2.8],  type: 'transmitter' },
];

const DEFAULT_RECEIVERS: APConfig[] = [
  { id: 'RX1', pos: [-3.5, 2.5, 2.8], type: 'receiver' },
  { id: 'RX2', pos: [0, 2.5, 2.8],    type: 'receiver' },
  { id: 'RX3', pos: [3.5, 2.5, 2.8],  type: 'receiver' },
];

const DEFAULT_ZONES: ZoneConfig[] = [
  { id: 'zone_1', center: [-2, 0, 0], radius: 2, color: 0x0066ff, label: 'Zone 1' },
  { id: 'zone_2', center: [0, 0, 0],  radius: 2, color: 0x00cc66, label: 'Zone 2' },
  { id: 'zone_3', center: [2, 0, 0],  radius: 2, color: 0xff6600, label: 'Zone 3' },
];

// ---- 히트맵 유틸 (정적) -------------------------------------------------------

/**
 * personPositions 기반 Gaussian 히트맵 생성 (데모용)
 */
export function generateDemoHeatmap(
  personPositions: Array<{ x: number; z: number; confidence?: number }>,
  cols: number,
  rows: number,
  roomWidth: number,
  roomDepth: number
): Float32Array {
  const map = new Float32Array(cols * rows);
  const cellW = roomWidth / cols;
  const cellD = roomDepth / rows;
  for (const pos of personPositions) {
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const cx = (c + 0.5) * cellW - roomWidth / 2;
        const cz = (r + 0.5) * cellD - roomDepth / 2;
        const dx = cx - (pos.x ?? 0);
        const dz = cz - (pos.z ?? 0);
        const dist = Math.sqrt(dx * dx + dz * dz);
        const conf = Math.exp(-dist * dist * 0.5) * (pos.confidence ?? 0.8);
        map[r * cols + c] = Math.max(map[r * cols + c], conf);
      }
    }
  }
  return map;
}

// ---- 컴포넌트 -----------------------------------------------------------------

/**
 * 씬에 방 환경 레이어를 추가하는 컴포넌트. DOM을 렌더링하지 않는다.
 */
export default function EnvironmentLayer({
  scene,
  onUpdate,
  zoneOccupancy,
  confidenceMap,
  roomWidth = 8,
  roomDepth = 6,
  roomHeight = 3,
  accessPoints = DEFAULT_ACCESS_POINTS,
  receivers = DEFAULT_RECEIVERS,
  zones = DEFAULT_ZONES,
}: EnvironmentLayerProps) {
  const groupRef = useRef<THREE.Group | null>(null);
  const zoneMatsRef = useRef<
    Map<string, { circleMat: THREE.MeshBasicMaterial; fillMat: THREE.MeshBasicMaterial }>
  >(new Map());
  const heatmapCellsRef = useRef<THREE.Mesh[][]>([]);
  const apMeshesRef = useRef<THREE.Mesh[]>([]);
  const rxMeshesRef = useRef<THREE.Mesh[]>([]);
  const signalLinesRef = useRef<THREE.Line[]>([]);

  // ── 씬 구성 (마운트 시 1회) ──────────────────────────────────────────────
  useEffect(() => {
    const group = new THREE.Group();
    group.name = 'environment';
    groupRef.current = group;

    buildFloor(group, roomWidth, roomDepth);
    buildGrid(group, roomWidth, roomDepth);
    buildWalls(group, roomWidth, roomDepth, roomHeight);
    buildAPMarkers(group, accessPoints, receivers, apMeshesRef.current, rxMeshesRef.current);
    buildSignalPaths(group, accessPoints, receivers, signalLinesRef.current);
    buildDetectionZones(group, zones, zoneMatsRef.current);
    buildConfidenceHeatmap(group, roomWidth, roomDepth, heatmapCellsRef.current);

    scene.add(group);

    return () => {
      group.traverse((child) => {
        const c = child as THREE.Mesh;
        if (c.geometry) c.geometry.dispose();
        if (c.material) {
          if (Array.isArray(c.material)) c.material.forEach((m) => m.dispose());
          else {
            const mat = c.material as THREE.Material & { map?: THREE.Texture };
            mat.map?.dispose();
            mat.dispose();
          }
        }
      });
      scene.remove(group);
      groupRef.current = null;
      zoneMatsRef.current.clear();
      heatmapCellsRef.current = [];
      apMeshesRef.current = [];
      rxMeshesRef.current = [];
      signalLinesRef.current = [];
    };
  }, [scene, roomWidth, roomDepth, roomHeight, accessPoints, receivers, zones]);

  // ── 존 점유 업데이트 ─────────────────────────────────────────────────────
  useEffect(() => {
    if (!zoneOccupancy) return;
    for (const [zoneId, mats] of zoneMatsRef.current.entries()) {
      const count = zoneOccupancy[zoneId] ?? 0;
      mats.circleMat.opacity = count > 0 ? 0.25 : 0.08;
      mats.fillMat.opacity = count > 0 ? 0.10 : 0.03;
    }
  }, [zoneOccupancy]);

  // ── 히트맵 업데이트 ─────────────────────────────────────────────────────
  useEffect(() => {
    if (!confidenceMap) return;
    const cells = heatmapCellsRef.current;
    const rows = cells.length;
    const cols = cells[0]?.length ?? 0;
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const idx = r * cols + c;
        const val = confidenceMap instanceof Float32Array
          ? (confidenceMap[idx] ?? 0)
          : (confidenceMap[r]?.[c] ?? 0);
        const cell = cells[r][c];
        const mat = cell.material as THREE.MeshBasicMaterial;
        if (val > 0.01) {
          mat.color.setHSL(0.6 - val * 0.6, 1.0, 0.3 + val * 0.3);
          mat.opacity = val * 0.3;
        } else {
          mat.opacity = 0;
        }
      }
    }
  }, [confidenceMap]);

  // ── 애니메이션 콜백 등록 ─────────────────────────────────────────────────
  useEffect(() => {
    const unregister = onUpdate((_delta, elapsed) => {
      for (const mesh of apMeshesRef.current) {
        const pulse = 0.9 + Math.sin(elapsed * 2) * 0.1;
        mesh.scale.setScalar(pulse);
        (mesh.material as THREE.MeshPhongMaterial).emissiveIntensity =
          0.3 + Math.sin(elapsed * 3) * 0.15;
      }
      for (const mesh of rxMeshesRef.current) {
        const pulse = 0.9 + Math.sin(elapsed * 2 + Math.PI) * 0.1;
        mesh.scale.setScalar(pulse);
        (mesh.material as THREE.MeshPhongMaterial).emissiveIntensity =
          0.3 + Math.sin(elapsed * 3 + Math.PI) * 0.15;
      }
      for (const line of signalLinesRef.current) {
        (line.material as THREE.LineDashedMaterial).opacity =
          0.08 + Math.sin(elapsed * 1.5) * 0.05;
      }
    });
    return unregister;
  }, [onUpdate]);

  return null;
}
