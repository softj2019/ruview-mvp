/**
 * GaussianSplatField — Phase 2-5
 * Three.js Points + 커스텀 ShaderMaterial로 WiFi 신호장 렌더링
 * 참조: ruvnet-RuView/ui/components/gaussian-splats.js
 */
import { useRef, useEffect } from 'react';
import * as THREE from 'three';

// ---- 셰이더 소스 -------------------------------------------------------

const SPLAT_VERTEX = /* glsl */ `
  attribute float splatSize;
  attribute vec3  splatColor;
  attribute float splatOpacity;

  varying vec3  vColor;
  varying float vOpacity;

  void main() {
    vColor   = splatColor;
    vOpacity = splatOpacity;

    vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
    gl_PointSize = splatSize * (300.0 / -mvPosition.z);
    gl_Position  = projectionMatrix * mvPosition;
  }
`;

const SPLAT_FRAGMENT = /* glsl */ `
  varying vec3  vColor;
  varying float vOpacity;

  void main() {
    float dist = length(gl_PointCoord - vec2(0.5));
    if (dist > 0.5) discard;
    float alpha = smoothstep(0.5, 0.2, dist) * vOpacity;
    gl_FragColor = vec4(vColor, alpha);
  }
`;

// ---- 타입 / Props -------------------------------------------------------

export interface GaussianSplatFieldProps {
  amplitudes: number[];        // 길이 가변 (gridSize² 또는 30 서브캐리어)
  scene: THREE.Scene;
}

// ---- 헬퍼 ---------------------------------------------------------------

/** 0–1 스칼라 → 파란→녹색→빨간 RGB */
function valueToColor(v: number): [number, number, number] {
  const c = Math.max(0, Math.min(1, v));
  if (c < 0.5) {
    const t = c * 2;
    return [0, t, 1 - t];
  } else {
    const t = (c - 0.5) * 2;
    return [t, 1 - t, 0];
  }
}

/** WebGL2 지원 여부 확인 */
function supportsWebGL2(): boolean {
  try {
    const canvas = document.createElement('canvas');
    return !!canvas.getContext('webgl2');
  } catch {
    return false;
  }
}

// ---- Canvas 2D 폴백 렌더러 ----------------------------------------------

function renderFallback(
  canvas: HTMLCanvasElement,
  amplitudes: number[],
  animRef: React.MutableRefObject<number>,
) {
  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  const W = canvas.width;
  const H = canvas.height;
  const cols = Math.ceil(Math.sqrt(amplitudes.length));
  const rows = Math.ceil(amplitudes.length / cols);
  const cellW = W / cols;
  const cellH = H / rows;

  const draw = () => {
    animRef.current = requestAnimationFrame(draw);
    ctx.fillStyle = '#0a0a12';
    ctx.fillRect(0, 0, W, H);

    for (let i = 0; i < amplitudes.length; i++) {
      const v = amplitudes[i] ?? 0;
      const [r, g, b] = valueToColor(v);
      const col = i % cols;
      const row = Math.floor(i / cols);
      const cx = col * cellW + cellW / 2;
      const cy = row * cellH + cellH / 2;
      const radius = Math.max(2, (cellW / 2) * (0.3 + v * 0.7));

      const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, radius);
      grad.addColorStop(0, `rgba(${Math.round(r * 255)},${Math.round(g * 255)},${Math.round(b * 255)},${0.1 + v * 0.6})`);
      grad.addColorStop(1, 'rgba(0,0,0,0)');
      ctx.beginPath();
      ctx.arc(cx, cy, radius, 0, Math.PI * 2);
      ctx.fillStyle = grad;
      ctx.fill();
    }

    // 라벨
    ctx.fillStyle = '#4a7a99';
    ctx.font = '10px monospace';
    ctx.fillText('WebGL2 미지원 — Canvas 2D 폴백', 8, 16);
  };

  draw();
}

// ---- 메인 컴포넌트 -------------------------------------------------------

export default function GaussianSplatField({ amplitudes, scene }: GaussianSplatFieldProps) {
  const mountRef = useRef<HTMLDivElement>(null);
  const animRef = useRef<number>(0);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const pointsRef = useRef<THREE.Points | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const fallbackRef = useRef<HTMLCanvasElement | null>(null);
  const gl2Supported = useRef<boolean>(false);

  // 초기화 (씬 객체가 외부에서 전달되므로, 렌더러+카메라만 내부 생성)
  useEffect(() => {
    const container = mountRef.current;
    if (!container) return;

    gl2Supported.current = supportsWebGL2();

    // ── WebGL2 미지원 → Canvas 2D 폴백 ──────────────────────────────────
    if (!gl2Supported.current) {
      const canvas = document.createElement('canvas');
      canvas.width = container.clientWidth || 400;
      canvas.height = 300;
      canvas.style.width = '100%';
      canvas.style.height = '100%';
      canvas.style.display = 'block';
      container.appendChild(canvas);
      fallbackRef.current = canvas;
      renderFallback(canvas, amplitudes, animRef);
      return () => {
        cancelAnimationFrame(animRef.current);
        canvas.remove();
      };
    }

    // ── WebGL2 경로 ──────────────────────────────────────────────────────
    const W = container.clientWidth || 400;
    const H = 300;

    const camera = new THREE.PerspectiveCamera(55, W / H, 0.1, 200);
    camera.position.set(0, 14, 14);
    camera.lookAt(0, 0, 0);
    cameraRef.current = camera;

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(W, H);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    // 그리드 (씬에 추가)
    const grid = new THREE.GridHelper(20, 20, 0x1a3a4a, 0x0d1f28);
    scene.add(grid);

    // 룸 와이어프레임
    const boxEdges = new THREE.EdgesGeometry(new THREE.BoxGeometry(20, 6, 20));
    const boxLine = new THREE.LineSegments(
      boxEdges,
      new THREE.LineBasicMaterial({ color: 0x1a4a5a, opacity: 0.3, transparent: true }),
    );
    boxLine.position.y = 3;
    scene.add(boxLine);

    // ── 신호장 스플랫 생성 ───────────────────────────────────────────────
    const gridSize = 20;
    const count = gridSize * gridSize;

    const positions = new Float32Array(count * 3);
    const sizes     = new Float32Array(count);
    const colors    = new Float32Array(count * 3);
    const opacities = new Float32Array(count);

    for (let iz = 0; iz < gridSize; iz++) {
      for (let ix = 0; ix < gridSize; ix++) {
        const idx = iz * gridSize + ix;
        positions[idx * 3]     = (ix - gridSize / 2) + 0.5;
        positions[idx * 3 + 1] = 0.05;
        positions[idx * 3 + 2] = (iz - gridSize / 2) + 0.5;
        sizes[idx]         = 1.5;
        colors[idx * 3]    = 0.1;
        colors[idx * 3 + 1] = 0.2;
        colors[idx * 3 + 2] = 0.6;
        opacities[idx]     = 0.15;
      }
    }

    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position',     new THREE.BufferAttribute(positions, 3));
    geo.setAttribute('splatSize',    new THREE.BufferAttribute(sizes, 1));
    geo.setAttribute('splatColor',   new THREE.BufferAttribute(colors, 3));
    geo.setAttribute('splatOpacity', new THREE.BufferAttribute(opacities, 1));

    const mat = new THREE.ShaderMaterial({
      vertexShader: SPLAT_VERTEX,
      fragmentShader: SPLAT_FRAGMENT,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });

    const fieldPoints = new THREE.Points(geo, mat);
    scene.add(fieldPoints);
    pointsRef.current = fieldPoints;

    // 라우터 마커 (중앙 녹색 구)
    const routerMarker = new THREE.Mesh(
      new THREE.SphereGeometry(0.3, 16, 16),
      new THREE.MeshBasicMaterial({ color: 0x00ff88, transparent: true, opacity: 0.8 }),
    );
    routerMarker.position.set(0, 0.5, 0);
    scene.add(routerMarker);

    // 렌더 루프
    const animate = () => {
      animRef.current = requestAnimationFrame(animate);
      // 라우터 글로우 펄스
      const pulseMat = routerMarker.material as THREE.MeshBasicMaterial;
      pulseMat.opacity = 0.6 + 0.3 * Math.sin(Date.now() * 0.003);
      renderer.render(scene, camera);
    };
    animate();

    // 리사이즈 핸들러
    const handleResize = () => {
      if (!container || !camera || !renderer) return;
      const nW = container.clientWidth;
      camera.aspect = nW / H;
      camera.updateProjectionMatrix();
      renderer.setSize(nW, H);
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      cancelAnimationFrame(animRef.current);

      // 씬에서 추가한 객체 제거
      scene.remove(grid, boxLine, fieldPoints, routerMarker);
      geo.dispose();
      mat.dispose();
      boxEdges.dispose();

      renderer.dispose();
      renderer.domElement.remove();
      rendererRef.current = null;
      pointsRef.current = null;
      cameraRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scene]);

  // amplitudes 변경 시 스플랫 속성 업데이트
  useEffect(() => {
    if (!gl2Supported.current) {
      // 폴백: 캔버스 재드로우 (다음 animFrame에서 자동으로 최신 amplitudes 사용)
      return;
    }

    const points = pointsRef.current;
    if (!points || !amplitudes.length) return;

    const geo = points.geometry;
    const clr    = geo.attributes.splatColor.array as Float32Array;
    const sizes  = geo.attributes.splatSize.array as Float32Array;
    const opac   = geo.attributes.splatOpacity.array as Float32Array;
    const count  = Math.min(amplitudes.length, clr.length / 3);

    for (let i = 0; i < count; i++) {
      const v = Math.max(0, Math.min(1, amplitudes[i] ?? 0));
      const [r, g, b] = valueToColor(v);
      clr[i * 3]     = r;
      clr[i * 3 + 1] = g;
      clr[i * 3 + 2] = b;
      sizes[i] = 1.0 + v * 4.0;
      opac[i]  = 0.1 + v * 0.6;
    }

    (geo.attributes.splatColor as THREE.BufferAttribute).needsUpdate   = true;
    (geo.attributes.splatSize  as THREE.BufferAttribute).needsUpdate   = true;
    (geo.attributes.splatOpacity as THREE.BufferAttribute).needsUpdate = true;
  }, [amplitudes]);

  // 폴백 캔버스에 최신 amplitudes 전달 (animRef 루프가 이미 돌고 있으므로 별도 처리 없음)
  useEffect(() => {
    if (!gl2Supported.current && fallbackRef.current) {
      // 새 amplitudes로 재시작
      cancelAnimationFrame(animRef.current);
      renderFallback(fallbackRef.current, amplitudes, animRef);
    }
  }, [amplitudes]);

  return (
    <div
      ref={mountRef}
      className="w-full overflow-hidden rounded-lg border border-gray-800 bg-[#0a0a12]"
      style={{ height: 300 }}
    />
  );
}
