/**
 * useThreeScene — Three.js 씬 초기화 공용 훅
 *
 * scene.js (ruvnet-RuView) 로직을 React 19 + TypeScript 패턴으로 변환.
 * 카메라, 렌더러, OrbitControls, 조명, 리사이즈를 한 번에 처리한다.
 */
import { useRef, useEffect, useCallback } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

export interface ThreeSceneResult {
  sceneRef: React.RefObject<THREE.Scene | null>;
  cameraRef: React.RefObject<THREE.PerspectiveCamera | null>;
  rendererRef: React.RefObject<THREE.WebGLRenderer | null>;
  controlsRef: React.RefObject<OrbitControls | null>;
  clockRef: React.RefObject<THREE.Clock | null>;
  mountRef: React.RefObject<HTMLDivElement | null>;
  /** 업데이트 콜백 등록. 반환값을 호출하면 등록 해제. */
  onUpdate: (cb: (delta: number, elapsed: number) => void) => () => void;
  /** 카메라를 기본 위치로 리셋 */
  resetCamera: () => void;
  /** 리소스 정리 (useEffect cleanup에서 자동 호출됨) */
  cleanup: () => void;
}

/**
 * Three.js 씬 전체를 초기화하고 AnimationLoop를 돌리는 훅.
 *
 * @example
 * ```tsx
 * function MyScene() {
 *   const { mountRef } = useThreeScene();
 *   return <div ref={mountRef} style={{ width: '100%', height: '400px' }} />;
 * }
 * ```
 */
export function useThreeScene(): ThreeSceneResult {
  const mountRef = useRef<HTMLDivElement | null>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);
  const clockRef = useRef<THREE.Clock | null>(null);
  const animationIdRef = useRef<number | null>(null);
  const updateCallbacksRef = useRef<Array<(delta: number, elapsed: number) => void>>([]);
  const resizeObserverRef = useRef<ResizeObserver | null>(null);
  const isRunningRef = useRef(false);

  // 콜백 등록 (useCallback으로 안정적 참조 유지)
  const onUpdate = useCallback(
    (cb: (delta: number, elapsed: number) => void) => {
      updateCallbacksRef.current.push(cb);
      return () => {
        const idx = updateCallbacksRef.current.indexOf(cb);
        if (idx !== -1) updateCallbacksRef.current.splice(idx, 1);
      };
    },
    []
  );

  const resetCamera = useCallback(() => {
    if (!cameraRef.current || !controlsRef.current) return;
    cameraRef.current.position.set(8, 7, 10);
    controlsRef.current.target.set(0, 1.2, 0);
    controlsRef.current.update();
  }, []);

  // 리사이즈 처리
  const onResize = useCallback(() => {
    const container = mountRef.current;
    if (!container || !cameraRef.current || !rendererRef.current) return;
    const w = container.clientWidth;
    const h = container.clientHeight;
    if (w === 0 || h === 0) return;
    cameraRef.current.aspect = w / h;
    cameraRef.current.updateProjectionMatrix();
    rendererRef.current.setSize(w, h);
  }, []);

  // 조명 설정
  const setupLights = useCallback((scene: THREE.Scene) => {
    // Ambient — 청색 기술 분위기
    const ambient = new THREE.AmbientLight(0x223355, 0.4);
    scene.add(ambient);

    // Hemisphere — sky/ground 그라디언트
    const hemi = new THREE.HemisphereLight(0x4488cc, 0x112233, 0.5);
    hemi.position.set(0, 20, 0);
    scene.add(hemi);

    // Key light — 우상단 따뜻한 디렉셔널
    const keyLight = new THREE.DirectionalLight(0xffeedd, 0.8);
    keyLight.position.set(5, 10, 5);
    keyLight.castShadow = true;
    keyLight.shadow.mapSize.width = 1024;
    keyLight.shadow.mapSize.height = 1024;
    keyLight.shadow.camera.near = 0.5;
    keyLight.shadow.camera.far = 30;
    keyLight.shadow.camera.left = -10;
    keyLight.shadow.camera.right = 10;
    keyLight.shadow.camera.top = 10;
    keyLight.shadow.camera.bottom = -10;
    scene.add(keyLight);

    // Fill light — 좌측 차가운 보조광
    const fillLight = new THREE.DirectionalLight(0x88aaff, 0.3);
    fillLight.position.set(-5, 6, -3);
    scene.add(fillLight);

    // Uplight — 바닥에서 올라오는 포인트 글로우
    const uplight = new THREE.PointLight(0x0066ff, 0.4, 8);
    uplight.position.set(0, 0.1, 0);
    scene.add(uplight);
  }, []);

  // 애니메이션 루프
  const animate = useCallback(() => {
    if (!isRunningRef.current) return;
    animationIdRef.current = requestAnimationFrame(animate);

    const clock = clockRef.current;
    const renderer = rendererRef.current;
    const scene = sceneRef.current;
    const camera = cameraRef.current;
    const controls = controlsRef.current;
    if (!clock || !renderer || !scene || !camera || !controls) return;

    const delta = clock.getDelta();
    const elapsed = clock.getElapsedTime();

    for (const cb of updateCallbacksRef.current) {
      cb(delta, elapsed);
    }

    controls.update();
    renderer.render(scene, camera);
  }, []);

  const cleanup = useCallback(() => {
    isRunningRef.current = false;

    if (animationIdRef.current !== null) {
      cancelAnimationFrame(animationIdRef.current);
      animationIdRef.current = null;
    }

    resizeObserverRef.current?.disconnect();

    controlsRef.current?.dispose();

    if (rendererRef.current) {
      const domEl = rendererRef.current.domElement;
      if (domEl.parentNode) domEl.parentNode.removeChild(domEl);
      rendererRef.current.dispose();
    }

    updateCallbacksRef.current = [];
    sceneRef.current = null;
    cameraRef.current = null;
    rendererRef.current = null;
    controlsRef.current = null;
    clockRef.current = null;
  }, []);

  useEffect(() => {
    const container = mountRef.current;
    if (!container) return;

    const w = container.clientWidth || 960;
    const h = container.clientHeight || 640;

    // Scene
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0a0a1a);
    scene.fog = new THREE.FogExp2(0x0a0a1a, 0.008);
    sceneRef.current = scene;

    // Camera — 3/4 앵글로 방 전체 보기
    const camera = new THREE.PerspectiveCamera(55, w / h, 0.1, 500);
    camera.position.set(8, 7, 10);
    camera.lookAt(0, 1.5, 0);
    cameraRef.current = camera;

    // Renderer
    const renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: false,
      powerPreference: 'high-performance',
    });
    renderer.setSize(w, h);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.0;
    container.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    // OrbitControls
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.minDistance = 3;
    controls.maxDistance = 30;
    controls.maxPolarAngle = Math.PI * 0.85;
    controls.target.set(0, 1.2, 0);
    controls.update();
    controlsRef.current = controls;

    // 조명
    setupLights(scene);

    // Clock
    const clock = new THREE.Clock();
    clockRef.current = clock;

    // ResizeObserver
    const ro = new ResizeObserver(onResize);
    ro.observe(container);
    resizeObserverRef.current = ro;
    window.addEventListener('resize', onResize);

    // 애니메이션 시작
    isRunningRef.current = true;
    clock.start();
    animate();

    return () => {
      window.removeEventListener('resize', onResize);
      cleanup();
    };
  }, [animate, cleanup, onResize, setupLights]);

  return {
    sceneRef,
    cameraRef,
    rendererRef,
    controlsRef,
    clockRef,
    mountRef,
    onUpdate,
    resetCamera,
    cleanup,
  };
}
