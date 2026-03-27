/**
 * singleBodyModel — 단일 인물 3D 인체 모델 클래스
 *
 * DensePose 24부위 + COCO 17-keypoint 포맷을 Three.js 메시로 표현한다.
 * BodyModel.tsx에서 import하여 사용한다.
 */
import * as THREE from 'three';
import type { Keypoint, BodyPartConfidences } from './BodyModel';

// ---- 골격 연결 페어 -----------------------------------------------------------

export const BONE_CONNECTIONS: [string, string][] = [
  ['pelvis', 'spine'], ['spine', 'chest'], ['chest', 'neck'], ['neck', 'head'],
  ['chest', 'left_shoulder'], ['left_shoulder', 'left_elbow'], ['left_elbow', 'left_wrist'],
  ['chest', 'right_shoulder'], ['right_shoulder', 'right_elbow'], ['right_elbow', 'right_wrist'],
  ['pelvis', 'left_hip'], ['left_hip', 'left_knee'], ['left_knee', 'left_ankle'],
  ['pelvis', 'right_hip'], ['right_hip', 'right_knee'], ['right_knee', 'right_ankle'],
];

// ---- T-pose 기본 조인트 -------------------------------------------------------

export type JointPositions = Record<string, { x: number; y: number; z: number }>;

export function defaultJointPositions(): JointPositions {
  return {
    head:           { x: 0,     y: 1.70, z: 0 },
    neck:           { x: 0,     y: 1.55, z: 0 },
    chest:          { x: 0,     y: 1.35, z: 0 },
    spine:          { x: 0,     y: 1.10, z: 0 },
    pelvis:         { x: 0,     y: 0.90, z: 0 },
    left_shoulder:  { x: -0.22, y: 1.48, z: 0 },
    right_shoulder: { x:  0.22, y: 1.48, z: 0 },
    left_elbow:     { x: -0.45, y: 1.20, z: 0 },
    right_elbow:    { x:  0.45, y: 1.20, z: 0 },
    left_wrist:     { x: -0.55, y: 0.95, z: 0 },
    right_wrist:    { x:  0.55, y: 0.95, z: 0 },
    left_hip:       { x: -0.12, y: 0.88, z: 0 },
    right_hip:      { x:  0.12, y: 0.88, z: 0 },
    left_knee:      { x: -0.13, y: 0.50, z: 0 },
    right_knee:     { x:  0.13, y: 0.50, z: 0 },
    left_ankle:     { x: -0.13, y: 0.08, z: 0 },
    right_ankle:    { x:  0.13, y: 0.08, z: 0 },
  };
}

// ---- LimbDef -----------------------------------------------------------------

interface LimbDef { name: string; from: string; to: string; radius: number; }

const LIMB_DEFS: LimbDef[] = [
  { name: 'torso_upper',     from: 'chest',          to: 'neck',           radius: 0.060 },
  { name: 'torso_lower',     from: 'spine',          to: 'chest',          radius: 0.070 },
  { name: 'hip_section',     from: 'pelvis',         to: 'spine',          radius: 0.065 },
  { name: 'left_upper_arm',  from: 'left_shoulder',  to: 'left_elbow',     radius: 0.030 },
  { name: 'right_upper_arm', from: 'right_shoulder', to: 'right_elbow',    radius: 0.030 },
  { name: 'left_forearm',    from: 'left_elbow',     to: 'left_wrist',     radius: 0.025 },
  { name: 'right_forearm',   from: 'right_elbow',    to: 'right_wrist',    radius: 0.025 },
  { name: 'left_thigh',      from: 'left_hip',       to: 'left_knee',      radius: 0.040 },
  { name: 'right_thigh',     from: 'right_hip',      to: 'right_knee',     radius: 0.040 },
  { name: 'left_shin',       from: 'left_knee',      to: 'left_ankle',     radius: 0.030 },
  { name: 'right_shin',      from: 'right_knee',     to: 'right_ankle',    radius: 0.030 },
  { name: 'left_clavicle',   from: 'chest',          to: 'left_shoulder',  radius: 0.025 },
  { name: 'right_clavicle',  from: 'chest',          to: 'right_shoulder', radius: 0.025 },
  { name: 'left_pelvis',     from: 'pelvis',         to: 'left_hip',       radius: 0.030 },
  { name: 'right_pelvis',    from: 'pelvis',         to: 'right_hip',      radius: 0.030 },
  { name: 'neck_head',       from: 'neck',           to: 'head',           radius: 0.025 },
];

// ---- PartGlow ----------------------------------------------------------------

interface PartRegion {
  pos: [number, number, number];
  scale: [number, number, number];
  parts: number[];
}

const PART_REGIONS: Record<string, PartRegion> = {
  torso:           { pos: [0,     1.20, 0    ], scale: [0.20, 0.30, 0.10], parts: [1, 2] },
  left_upper_arm:  { pos: [-0.35, 1.35, 0    ], scale: [0.06, 0.15, 0.06], parts: [15, 17] },
  right_upper_arm: { pos: [0.35,  1.35, 0    ], scale: [0.06, 0.15, 0.06], parts: [16, 18] },
  left_lower_arm:  { pos: [-0.50, 1.08, 0    ], scale: [0.05, 0.13, 0.05], parts: [19, 21] },
  right_lower_arm: { pos: [0.50,  1.08, 0    ], scale: [0.05, 0.13, 0.05], parts: [20, 22] },
  left_hand:       { pos: [-0.55, 0.95, 0    ], scale: [0.04, 0.04, 0.03], parts: [4] },
  right_hand:      { pos: [0.55,  0.95, 0    ], scale: [0.04, 0.04, 0.03], parts: [3] },
  left_upper_leg:  { pos: [-0.13, 0.70, 0    ], scale: [0.07, 0.18, 0.07], parts: [8, 10] },
  right_upper_leg: { pos: [0.13,  0.70, 0    ], scale: [0.07, 0.18, 0.07], parts: [7, 9] },
  left_lower_leg:  { pos: [-0.13, 0.30, 0    ], scale: [0.05, 0.18, 0.05], parts: [12, 14] },
  right_lower_leg: { pos: [0.13,  0.30, 0    ], scale: [0.05, 0.18, 0.05], parts: [11, 13] },
  left_foot:       { pos: [-0.13, 0.05, 0.03 ], scale: [0.04, 0.03, 0.06], parts: [5] },
  right_foot:      { pos: [0.13,  0.05, 0.03 ], scale: [0.04, 0.03, 0.06], parts: [6] },
  head:            { pos: [0,     1.72, 0    ], scale: [0.09, 0.10, 0.09], parts: [23, 24] },
};

// ---- 클래스 ------------------------------------------------------------------

interface LimbRef { mesh: THREE.Mesh; from: string; to: string; }

export class SingleBodyModel {
  readonly group: THREE.Group;
  confidence = 0;
  isVisible = false;

  private joints: Record<string, THREE.Mesh> = {};
  private limbs: Record<string, LimbRef> = {};
  private boneLine!: THREE.LineSegments;
  private partMeshes: Record<number, THREE.Mesh> = {};
  private currentPositions: JointPositions;
  private targetPositions: JointPositions;
  private materials: {
    joint: THREE.MeshPhongMaterial;
    limb: THREE.MeshPhongMaterial;
    head: THREE.MeshPhongMaterial;
    bone: THREE.LineBasicMaterial;
  };

  constructor() {
    this.group = new THREE.Group();
    this.group.name = 'body-model';
    this.currentPositions = defaultJointPositions();
    this.targetPositions = defaultJointPositions();
    this.materials = this._createMaterials();
    this._buildBody();
    this.group.visible = false;
  }

  private _createMaterials() {
    return {
      joint: new THREE.MeshPhongMaterial({
        color: 0x00aaff, emissive: new THREE.Color(0x003366),
        emissiveIntensity: 0.3, shininess: 60, transparent: true, opacity: 0.9,
      }),
      limb: new THREE.MeshPhongMaterial({
        color: 0x0088dd, emissive: new THREE.Color(0x002244),
        emissiveIntensity: 0.2, shininess: 40, transparent: true, opacity: 0.85,
      }),
      head: new THREE.MeshPhongMaterial({
        color: 0x00ccff, emissive: new THREE.Color(0x004466),
        emissiveIntensity: 0.4, shininess: 80, transparent: true, opacity: 0.9,
      }),
      bone: new THREE.LineBasicMaterial({
        color: 0x00ffcc, transparent: true, opacity: 0.6, linewidth: 2,
      }),
    };
  }

  private _buildBody() {
    const jointGeom = new THREE.SphereGeometry(0.035, 12, 12);
    const headGeom  = new THREE.SphereGeometry(0.10,  16, 16);

    for (const [name, pos] of Object.entries(this.currentPositions)) {
      const isHead = name === 'head';
      const mesh = new THREE.Mesh(
        isHead ? headGeom : jointGeom,
        isHead ? this.materials.head.clone() : this.materials.joint.clone()
      );
      mesh.position.set(pos.x, pos.y, pos.z);
      mesh.castShadow = true;
      mesh.name = `joint-${name}`;
      this.group.add(mesh);
      this.joints[name] = mesh;
    }

    for (const def of LIMB_DEFS) {
      const mesh = this._createLimbMesh(def.from, def.to, def.radius);
      mesh.name = `limb-${def.name}`;
      this.group.add(mesh);
      this.limbs[def.name] = { mesh, from: def.from, to: def.to };
    }

    this._createBoneLines();
    this._createPartGlows();
  }

  private _createLimbMesh(fromName: string, toName: string, radius: number): THREE.Mesh {
    const from = this.currentPositions[fromName];
    const to   = this.currentPositions[toName];
    const dir  = new THREE.Vector3(to.x - from.x, to.y - from.y, to.z - from.z);
    const length = dir.length();
    const geom = new THREE.CylinderGeometry(radius, radius, length, 8, 1);
    const mesh = new THREE.Mesh(geom, this.materials.limb.clone());
    mesh.castShadow = true;
    this._positionLimb(mesh, from, to, length);
    return mesh;
  }

  private _positionLimb(
    mesh: THREE.Mesh,
    from: { x: number; y: number; z: number },
    to:   { x: number; y: number; z: number },
    length: number
  ) {
    mesh.position.set((from.x + to.x) / 2, (from.y + to.y) / 2, (from.z + to.z) / 2);
    const dir = new THREE.Vector3(to.x - from.x, to.y - from.y, to.z - from.z).normalize();
    const up  = new THREE.Vector3(0, 1, 0);
    if (Math.abs(dir.dot(up)) < 0.999) {
      const quat = new THREE.Quaternion();
      quat.setFromUnitVectors(up, dir);
      mesh.quaternion.copy(quat);
    }
    const params = (mesh.geometry as THREE.CylinderGeometry).parameters;
    mesh.scale.y = length / params.height;
  }

  private _createBoneLines() {
    const positions = new Float32Array(BONE_CONNECTIONS.length * 6);
    const geom = new THREE.BufferGeometry();
    geom.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    this.boneLine = new THREE.LineSegments(geom, this.materials.bone);
    this.boneLine.name = 'skeleton-bones';
    this.group.add(this.boneLine);
  }

  private _createPartGlows() {
    const glowGeom = new THREE.SphereGeometry(1, 8, 8);
    for (const [, region] of Object.entries(PART_REGIONS)) {
      const mat = new THREE.MeshBasicMaterial({
        color: 0x00ffcc, transparent: true, opacity: 0, depthWrite: false,
      });
      const mesh = new THREE.Mesh(glowGeom, mat);
      mesh.position.set(...region.pos);
      mesh.scale.set(...region.scale);
      this.group.add(mesh);
      for (const partId of region.parts) {
        this.partMeshes[partId] = mesh;
      }
    }
  }

  updateFromKeypoints(keypoints: Keypoint[], personConfidence: number) {
    this.confidence = personConfidence;
    this.isVisible  = this.confidence > 0.15;
    this.group.visible = this.isVisible;
    if (!this.isVisible || keypoints.length < 17) return;

    const kp = keypoints;
    const mapX = (v: number) => (v - 0.5) * 4;

    const lShoulder = kp[5];
    const lAnkle    = kp[15];
    let scale = 1.0;
    if (lShoulder && lAnkle && lShoulder.confidence > 0.2 && lAnkle.confidence > 0.2) {
      const pixelH = Math.abs(lAnkle.y - lShoulder.y);
      if (pixelH > 0.05) scale = 0.85 / pixelH;
    }

    const groundRef = Math.max(
      kp[15] && kp[15].confidence > 0.2 ? kp[15].y : 0.95,
      kp[16] && kp[16].confidence > 0.2 ? kp[16].y : 0.95
    );
    const mapY = (v: number) => (groundRef - v) * scale * 1.75;

    const avgCoord = (indices: number[], coord: 'x' | 'y'): number | null => {
      let sum = 0, count = 0;
      for (const idx of indices) {
        const k = kp[idx];
        if (k && k.confidence > 0.1) { sum += k[coord]; count++; }
      }
      return count > 0 ? sum / count : null;
    };

    const midHipX      = avgCoord([11, 12], 'x');
    const midHipY      = avgCoord([11, 12], 'y');
    const midShoulderX = avgCoord([5, 6],   'x');
    const midShoulderY = avgCoord([5, 6],   'y');
    const centerX      = midHipX !== null ? mapX(midHipX) : 0;

    const setTarget = (name: string, idx: number) => {
      const k = kp[idx];
      if (k && k.confidence > 0.1) {
        this.targetPositions[name] = { x: mapX(k.x) - centerX, y: mapY(k.y), z: 0 };
      }
    };

    const headX = avgCoord([0, 1, 2, 3, 4], 'x');
    const headY = avgCoord([0, 1, 2, 3, 4], 'y');
    if (headX !== null && headY !== null) {
      this.targetPositions.head = { x: mapX(headX) - centerX, y: mapY(headY) + 0.08, z: 0 };
    }

    const noseK = kp[0];
    if (midShoulderX !== null && noseK && noseK.confidence > 0.1) {
      this.targetPositions.neck = {
        x: mapX((midShoulderX + noseK.x) / 2) - centerX,
        y: mapY((midShoulderY! + noseK.y) / 2),
        z: 0,
      };
    }
    if (midShoulderX !== null && midShoulderY !== null) {
      this.targetPositions.chest = { x: mapX(midShoulderX) - centerX, y: mapY(midShoulderY), z: 0 };
    }
    if (midShoulderX !== null && midHipX !== null) {
      this.targetPositions.spine = {
        x: mapX((midShoulderX + midHipX) / 2) - centerX,
        y: mapY((midShoulderY! + midHipY!) / 2),
        z: 0,
      };
    }
    if (midHipX !== null && midHipY !== null) {
      this.targetPositions.pelvis = { x: mapX(midHipX) - centerX, y: mapY(midHipY), z: 0 };
    }

    setTarget('left_shoulder', 5);  setTarget('right_shoulder', 6);
    setTarget('left_elbow', 7);     setTarget('right_elbow', 8);
    setTarget('left_wrist', 9);     setTarget('right_wrist', 10);
    setTarget('left_hip', 11);      setTarget('right_hip', 12);
    setTarget('left_knee', 13);     setTarget('right_knee', 14);
    setTarget('left_ankle', 15);    setTarget('right_ankle', 16);

    this.group.position.x = centerX;
  }

  activateParts(partConfidences: BodyPartConfidences) {
    for (const [partIdStr, mesh] of Object.entries(this.partMeshes)) {
      const conf = partConfidences[Number(partIdStr)] ?? 0;
      const mat = mesh.material as THREE.MeshBasicMaterial;
      mat.opacity = conf * 0.4;
      mat.color.setHSL((1 - conf) * 0.55, 1.0, 0.5 + conf * 0.2);
    }
  }

  update(delta: number) {
    if (!this.isVisible) return;
    const lerpFactor = 1 - Math.pow(0.001, delta);

    for (const [name, joint] of Object.entries(this.joints)) {
      const target  = this.targetPositions[name];
      const current = this.currentPositions[name];
      if (!target) continue;
      current.x += (target.x - current.x) * lerpFactor;
      current.y += (target.y - current.y) * lerpFactor;
      current.z += (target.z - current.z) * lerpFactor;
      joint.position.set(current.x, current.y, current.z);
    }

    for (const limb of Object.values(this.limbs)) {
      const from = this.currentPositions[limb.from];
      const to   = this.currentPositions[limb.to];
      if (!from || !to) continue;
      const length = new THREE.Vector3(to.x - from.x, to.y - from.y, to.z - from.z).length();
      if (length < 0.001) continue;
      this._positionLimb(limb.mesh, from, to, length);
    }

    this._updateBoneLines();
    this._updateMaterialColors();
  }

  private _updateBoneLines() {
    const posAttr = this.boneLine.geometry.getAttribute('position') as THREE.BufferAttribute;
    const arr = posAttr.array as Float32Array;
    let i = 0;
    for (const [fromName, toName] of BONE_CONNECTIONS) {
      const from = this.currentPositions[fromName];
      const to   = this.currentPositions[toName];
      if (from && to) {
        arr[i] = from.x; arr[i+1] = from.y; arr[i+2] = from.z;
        arr[i+3] = to.x; arr[i+4] = to.y;   arr[i+5] = to.z;
      }
      i += 6;
    }
    posAttr.needsUpdate = true;
  }

  private _updateMaterialColors() {
    const conf  = this.confidence;
    const hue   = 0.55 - conf * 0.25;
    const sat   = 0.8;
    const light = 0.35 + conf * 0.2;

    for (const [name, joint] of Object.entries(this.joints)) {
      if (name !== 'head') {
        const mat = joint.material as THREE.MeshPhongMaterial;
        mat.color.setHSL(hue, sat, light);
        mat.emissive.setHSL(hue, sat, light * 0.3);
        mat.opacity = 0.5 + conf * 0.5;
      }
    }
    for (const limb of Object.values(this.limbs)) {
      const mat = limb.mesh.material as THREE.MeshPhongMaterial;
      mat.color.setHSL(hue, sat * 0.9, light * 0.9);
      mat.emissive.setHSL(hue, sat * 0.9, light * 0.2);
      mat.opacity = 0.4 + conf * 0.5;
    }
    const headJoint = this.joints.head;
    if (headJoint) {
      const mat = headJoint.material as THREE.MeshPhongMaterial;
      mat.color.setHSL(hue - 0.05, sat, light + 0.1);
      mat.emissive.setHSL(hue - 0.05, sat, light * 0.4);
      mat.opacity = 0.6 + conf * 0.4;
    }
    this.materials.bone.color.setHSL(hue + 0.1, 1.0, 0.5 + conf * 0.2);
    this.materials.bone.opacity = 0.3 + conf * 0.4;
  }

  setWorldPosition(x: number, y: number, z: number) {
    this.group.position.set(x, y, z);
  }

  dispose() {
    this.group.traverse((child) => {
      const c = child as THREE.Mesh;
      if (c.geometry) c.geometry.dispose();
      if (c.material) {
        if (Array.isArray(c.material)) c.material.forEach((m) => m.dispose());
        else (c.material as THREE.Material).dispose();
      }
    });
  }
}
