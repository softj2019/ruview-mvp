/**
 * environmentHelpers — EnvironmentLayer 씬 구성 순수 함수 모음
 *
 * Three.js 오브젝트 생성 로직만 담당하며 React 의존성이 없다.
 */
import * as THREE from 'three';
import type { APConfig, ZoneConfig } from './EnvironmentLayer';

// ---- 레이블 스프라이트 ---------------------------------------------------------

export function createLabel(text: string, color: number): THREE.Sprite {
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d')!;
  canvas.width = 128;
  canvas.height = 32;
  ctx.font = 'bold 14px monospace';
  ctx.fillStyle = '#' + new THREE.Color(color).getHexString();
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(text, canvas.width / 2, canvas.height / 2);
  const texture = new THREE.CanvasTexture(canvas);
  const mat = new THREE.SpriteMaterial({ map: texture, transparent: true, depthWrite: false });
  return new THREE.Sprite(mat);
}

// ---- 바닥 ---------------------------------------------------------------------

export function buildFloor(group: THREE.Group, w: number, d: number) {
  const geom = new THREE.PlaneGeometry(w, d);
  const mat = new THREE.MeshPhongMaterial({
    color: 0x0a0a15,
    emissive: 0x050510,
    shininess: 60,
    specular: new THREE.Color(0x111122),
    transparent: true,
    opacity: 0.95,
    side: THREE.DoubleSide,
  });
  const floor = new THREE.Mesh(geom, mat);
  floor.rotation.x = -Math.PI / 2;
  floor.receiveShadow = true;
  group.add(floor);
}

// ---- 그리드 -------------------------------------------------------------------

export function buildGrid(group: THREE.Group, w: number, d: number) {
  const gridGroup = new THREE.Group();
  const gridMat = new THREE.LineBasicMaterial({ color: 0x1a1a3a, transparent: true, opacity: 0.4 });
  const halfW = w / 2;
  const halfD = d / 2;
  const step = 0.5;

  for (let z = -halfD; z <= halfD; z += step) {
    const geom = new THREE.BufferGeometry();
    geom.setAttribute('position',
      new THREE.BufferAttribute(new Float32Array([-halfW, 0.005, z, halfW, 0.005, z]), 3));
    gridGroup.add(new THREE.Line(geom, gridMat));
  }
  for (let x = -halfW; x <= halfW; x += step) {
    const geom = new THREE.BufferGeometry();
    geom.setAttribute('position',
      new THREE.BufferAttribute(new Float32Array([x, 0.005, -halfD, x, 0.005, halfD]), 3));
    gridGroup.add(new THREE.Line(geom, gridMat));
  }

  const centerMat = new THREE.LineBasicMaterial({ color: 0x2233aa, transparent: true, opacity: 0.25 });
  const cxGeom = new THREE.BufferGeometry();
  cxGeom.setAttribute('position',
    new THREE.BufferAttribute(new Float32Array([-halfW, 0.006, 0, halfW, 0.006, 0]), 3));
  gridGroup.add(new THREE.Line(cxGeom, centerMat));

  const czGeom = new THREE.BufferGeometry();
  czGeom.setAttribute('position',
    new THREE.BufferAttribute(new Float32Array([0, 0.006, -halfD, 0, 0.006, halfD]), 3));
  gridGroup.add(new THREE.Line(czGeom, centerMat));

  group.add(gridGroup);
}

// ---- 벽 -----------------------------------------------------------------------

export function buildWalls(group: THREE.Group, w: number, d: number, h: number) {
  const wallMat = new THREE.MeshBasicMaterial({
    color: 0x112244, transparent: true, opacity: 0.06,
    side: THREE.DoubleSide, depthWrite: false,
  });
  const halfW = w / 2;
  const halfD = d / 2;

  const backWall = new THREE.Mesh(new THREE.PlaneGeometry(w, h), wallMat);
  backWall.position.set(0, h / 2, -halfD);
  group.add(backWall);

  const frontMat = wallMat.clone();
  frontMat.opacity = 0.03;
  const frontWall = new THREE.Mesh(new THREE.PlaneGeometry(w, h), frontMat);
  frontWall.position.set(0, h / 2, halfD);
  group.add(frontWall);

  const leftWall = new THREE.Mesh(new THREE.PlaneGeometry(d, h), wallMat);
  leftWall.rotation.y = Math.PI / 2;
  leftWall.position.set(-halfW, h / 2, 0);
  group.add(leftWall);

  const rightWall = new THREE.Mesh(new THREE.PlaneGeometry(d, h), wallMat);
  rightWall.rotation.y = -Math.PI / 2;
  rightWall.position.set(halfW, h / 2, 0);
  group.add(rightWall);

  const edgeMat = new THREE.LineBasicMaterial({ color: 0x334466, transparent: true, opacity: 0.3 });
  const edges: number[][] = [
    [-halfW, 0, -halfD, halfW, 0, -halfD], [halfW, 0, -halfD, halfW, 0, halfD],
    [halfW, 0, halfD, -halfW, 0, halfD],   [-halfW, 0, halfD, -halfW, 0, -halfD],
    [-halfW, h, -halfD, halfW, h, -halfD], [halfW, h, -halfD, halfW, h, halfD],
    [-halfW, h, halfD, -halfW, h, -halfD],
    [-halfW, 0, -halfD, -halfW, h, -halfD], [halfW, 0, -halfD, halfW, h, -halfD],
    [-halfW, 0, halfD, -halfW, h, halfD],  [halfW, 0, halfD, halfW, h, halfD],
  ];
  for (const e of edges) {
    const geom = new THREE.BufferGeometry();
    geom.setAttribute('position', new THREE.BufferAttribute(new Float32Array(e), 3));
    group.add(new THREE.Line(geom, edgeMat));
  }
}

// ---- AP/RX 마커 ---------------------------------------------------------------

export function buildAPMarkers(
  group: THREE.Group,
  accessPoints: APConfig[],
  receivers: APConfig[],
  apMeshesOut: THREE.Mesh[],
  rxMeshesOut: THREE.Mesh[]
) {
  const txGeom = new THREE.ConeGeometry(0.12, 0.25, 4);
  const txMat = new THREE.MeshPhongMaterial({
    color: 0x0088ff, emissive: new THREE.Color(0x003366),
    emissiveIntensity: 0.5, transparent: true, opacity: 0.9,
  });
  for (const ap of accessPoints) {
    const mesh = new THREE.Mesh(txGeom, txMat.clone());
    mesh.position.set(...ap.pos);
    mesh.rotation.z = Math.PI;
    mesh.castShadow = true;
    mesh.name = `ap-${ap.id}`;
    group.add(mesh);
    apMeshesOut.push(mesh);
    const light = new THREE.PointLight(0x0066ff, 0.3, 4);
    light.position.set(...ap.pos);
    group.add(light);
    const label = createLabel(ap.id, 0x0088ff);
    label.position.set(ap.pos[0], ap.pos[1] + 0.3, ap.pos[2]);
    group.add(label);
  }

  const rxGeom = new THREE.ConeGeometry(0.12, 0.25, 4);
  const rxMat = new THREE.MeshPhongMaterial({
    color: 0x00cc44, emissive: new THREE.Color(0x004422),
    emissiveIntensity: 0.5, transparent: true, opacity: 0.9,
  });
  for (const rx of receivers) {
    const mesh = new THREE.Mesh(rxGeom, rxMat.clone());
    mesh.position.set(...rx.pos);
    mesh.castShadow = true;
    mesh.name = `rx-${rx.id}`;
    group.add(mesh);
    rxMeshesOut.push(mesh);
    const light = new THREE.PointLight(0x00cc44, 0.2, 3);
    light.position.set(...rx.pos);
    group.add(light);
    const label = createLabel(rx.id, 0x00cc44);
    label.position.set(rx.pos[0], rx.pos[1] + 0.3, rx.pos[2]);
    group.add(label);
  }
}

// ---- 신호 경로 ----------------------------------------------------------------

export function buildSignalPaths(
  group: THREE.Group,
  accessPoints: APConfig[],
  receivers: APConfig[],
  signalLinesOut: THREE.Line[]
) {
  const lineMat = new THREE.LineDashedMaterial({
    color: 0x1133aa, transparent: true, opacity: 0.15,
    dashSize: 0.15, gapSize: 0.1, linewidth: 1,
  });
  for (const tx of accessPoints) {
    for (const rx of receivers) {
      const geom = new THREE.BufferGeometry();
      geom.setAttribute('position',
        new THREE.BufferAttribute(new Float32Array([...tx.pos, ...rx.pos]), 3));
      const line = new THREE.Line(geom, lineMat.clone());
      line.computeLineDistances();
      group.add(line);
      signalLinesOut.push(line);
    }
  }
}

// ---- 감지 존 -----------------------------------------------------------------

export function buildDetectionZones(
  group: THREE.Group,
  zones: ZoneConfig[],
  zoneMatsOut: Map<string, { circleMat: THREE.MeshBasicMaterial; fillMat: THREE.MeshBasicMaterial }>
) {
  for (const zone of zones) {
    const zoneGroup = new THREE.Group();
    zoneGroup.name = `zone-${zone.id}`;

    const circleMat = new THREE.MeshBasicMaterial({
      color: zone.color, transparent: true, opacity: 0.12,
      side: THREE.DoubleSide, depthWrite: false,
    });
    const circle = new THREE.Mesh(new THREE.RingGeometry(zone.radius * 0.95, zone.radius, 48), circleMat);
    circle.rotation.x = -Math.PI / 2;
    circle.position.set(zone.center[0], 0.01, zone.center[2]);
    zoneGroup.add(circle);

    const fillMat = new THREE.MeshBasicMaterial({
      color: zone.color, transparent: true, opacity: 0.04,
      side: THREE.DoubleSide, depthWrite: false,
    });
    const fill = new THREE.Mesh(new THREE.CircleGeometry(zone.radius * 0.95, 48), fillMat);
    fill.rotation.x = -Math.PI / 2;
    fill.position.set(zone.center[0], 0.008, zone.center[2]);
    zoneGroup.add(fill);

    const label = createLabel(zone.label, zone.color);
    label.position.set(zone.center[0], 0.15, zone.center[2] + zone.radius + 0.2);
    label.scale.set(1.0, 0.25, 1);
    zoneGroup.add(label);

    group.add(zoneGroup);
    zoneMatsOut.set(zone.id, { circleMat, fillMat });
  }
}

// ---- 히트맵 ------------------------------------------------------------------

export function buildConfidenceHeatmap(
  group: THREE.Group,
  roomWidth: number,
  roomDepth: number,
  heatmapCellsOut: THREE.Mesh[][]
) {
  const cols = 20;
  const rows = 15;
  const cellW = roomWidth / cols;
  const cellD = roomDepth / rows;
  const cellGeom = new THREE.PlaneGeometry(cellW * 0.95, cellD * 0.95);
  const heatmapGroup = new THREE.Group();
  heatmapGroup.position.y = 0.003;

  for (let r = 0; r < rows; r++) {
    const rowCells: THREE.Mesh[] = [];
    for (let c = 0; c < cols; c++) {
      const mat = new THREE.MeshBasicMaterial({
        color: 0x000000, transparent: true, opacity: 0,
        side: THREE.DoubleSide, depthWrite: false,
      });
      const cell = new THREE.Mesh(cellGeom, mat);
      cell.rotation.x = -Math.PI / 2;
      cell.position.set(
        (c + 0.5) * cellW - roomWidth / 2,
        0,
        (r + 0.5) * cellD - roomDepth / 2
      );
      heatmapGroup.add(cell);
      rowCells.push(cell);
    }
    heatmapCellsOut.push(rowCells);
  }
  group.add(heatmapGroup);
}
