# RuView Phase Workflow

> **목표**: ruvnet/RuView를 원본 베이스로, 요양원·건물관제 특화 WiFi-Sensing 플랫폼으로 커스터마이징
> **갱신**: 2026-03-27 (전수검증 완료) | 95+ commits | v0.1.0-alpha
> **원본 베이스**: `d:/home/ruvnet-RuView` (ruvnet/RuView.git)
> **배포**: https://ruview-monitor.pages.dev (Cloudflare Pages)

---

## 작업 분류 기호

| 기호 | 의미 |
|------|------|
| `[PORT]` | ruvnet/RuView에서 직접 이식 (JS→TSX 변환 포함) |
| `[ADAPT]` | ruvnet 로직 참조 후 우리 아키텍처(React/Zustand/FastAPI)에 맞게 변형 |
| `[CUSTOM]` | ruView 고유 신규 개발 (ruvnet에 없음) |
| `[DONE]` | 완료 |

---

## 전체 완성도 대시보드

| Phase | 영역 | 진행률 | 잔여 핵심 작업 |
|-------|------|--------|--------------|
| 0 기반정렬 | 안정화·검증 | 85% | 노드 위치 검증, 캘리브레이션 |
| 1 Observatory 이식 | 3D 관측소 완전 구현 | 55% | nebula, post-processing, mist 4개 모듈 |
| 2 UI 컴포넌트 이식 | ruvnet 15개 컴포넌트 React 변환 | 30% | PoseDetectionCanvas, dashboard-hud, signal-viz |
| 3 신호처리 알고리즘 | HW Normalizer, HRV, Gesture, DensePose | 65% | DTW Gesture, RF Tomography, DensePose 헤드 |
| 4 백엔드 서비스 | Pose/Stream/Sensing/Model/Training API | 20% | Pose API, Stream API, Sensing 패키지 전체 |
| 5 카메라/ML 고도화 | AETHER re-ID, 낙상 모델 | 70% | 데이터 150건 수집, AETHER |
| 6 Rust 포팅 | 4 crates 구현 | 10% | toolchain 설치, signal 구현 |
| 7 품질/배포 | QEMU, Witness, Blue-Green, Prometheus | 55% | Grafana 스택, QEMU chaos/mesh, README |
| 8 커스텀 기능 | 돌봄·건물관제 특화 | 0% | 알림 워크플로, 멀티층 뷰 |
| 9 펌웨어 고도화 | WASM, Swarm, OTA, Display | 0% | wasm_runtime, swarm_bridge, ota_update |
| 10 모바일·데스크톱 | React Native Expo, Tauri | 0% | 모바일 앱, 데스크톱 앱 |

---

## 전체 의존성 DAG

```
Phase 0 (기반정렬)
  ├─→ Phase 1 (Observatory 이식)
  │      └─→ Phase 2 (UI 컴포넌트 이식)
  │              └─→ Phase 5 (카메라/ML 고도화)
  ├─→ Phase 3 (신호처리 알고리즘)
  │      └─→ Phase 5
  ├─→ Phase 4 (백엔드 서비스)
  │      ├─→ Phase 6 (Rust 포팅)
  │      └─→ Phase 7 (품질/배포)
  ├─→ Phase 8 (커스텀: 0-6 인증 완료 후 병행)
  ├─→ Phase 9 (펌웨어 고도화: Phase 6 WASM 이후)
  └─→ Phase 10 (모바일·데스크톱: Phase 4+7 완료 후)
```

Phase 1·2·3·4는 병렬 진행 가능. Phase 5는 Phase 1+3 완료 후.

---

## Baseline — 완료된 기반 작업

> 기존 Phase 1-5에서 이미 완성된 항목. 이후 Phase에서 이 위에 빌드.

### 신호처리 기반 (Phase 1 완료)
- [x] [ADAPT] Butterworth + FFT + Zero-crossing 호흡/심박 추출
- [x] [ADAPT] Hampel 필터, CSI Ratio, Fresnel Zone (ruvnet wifi-densepose-signal 이식)
- [x] [ADAPT] STFT Spectrogram + doppler_velocity
- [x] [ADAPT] Welford Z-score 온라인 통계 (EMA decay 추가)
- [x] [CUSTOM] 다중인원 서브캐리어 클러스터링
- [x] [ADAPT] BVP (Body Velocity Profile)
- [x] [ADAPT] Top-K 서브캐리어 감도 선택
- [x] [CUSTOM] heart_rate uint32 파싱 수정 (1e-39 → 실 BPM) ← 2026-03-27

### 시각화 기반 (Phase 2 대부분 완료)
- [x] [CUSTOM] React 19 + TypeScript 8페이지 UI (Vite 6, TailwindCSS 3)
- [x] [CUSTOM] Zustand 5 스토어 (device, zone, event, signal, alert)
- [x] [CUSTOM] WebSocket exponential backoff 훅 (1s→32s, stale closure 방지)
- [x] [ADAPT] Observatory 4개 모듈 이식 (vitals-oracle, phase-constellation, presence-cartography, hud-controller)
- [x] [CUSTOM] 2D SVG 평면도 (4존, RSSI+BPM+HR 라벨, drag-drop)
- [x] [ADAPT] CSI 히트맵 30×40 Canvas texture (실IQ 데이터 연결)
- [x] [ADAPT] 도플러 스펙트럼 16바, 위상 플롯 30 subcarrier
- [x] [CUSTOM] KPI 카드 6개, SignalChart (Recharts 4라인)

### 낙상감지·카메라 기반 (Phase 3-5 대부분 완료)
- [x] [ADAPT] 낙상감지 ML 프레임워크 (SVM+RF+GBDT, 5-fold CV) — 데이터 수집 대기
- [x] [ADAPT] YOLOv8-pose 17keypoint + 자세 분류 4종
- [x] [CUSTOM] SimpleTracker IoU MOT + HSV 히스토그램 re-ID
- [x] [CUSTOM] 프라이버시 블러 (GaussianBlur), 다중 카메라 관리
- [x] [CUSTOM] 신뢰도 기반 모달리티 전환 3단계 (EMA α=0.1)
- [x] [ADAPT] mmWave 확장 프레임워크 (Kalman 80/20 fusion)
- [x] [CUSTOM] Kalman presenceCount 스무딩

### 인프라 기반 (Phase 7 부분 완료)
- [x] [CUSTOM] Docker Compose 4서비스 (signal-adapter, api-gateway, camera, web)
- [x] [CUSTOM] CI/CD GitHub Actions (lint+typecheck+build+pytest 134 tests+firmware)
- [x] [CUSTOM] Cloudflare Pages 배포 (ruview-monitor.pages.dev)
- [x] [CUSTOM] API 인증 Bearer token (6개 mutation 엔드포인트)
- [x] [CUSTOM] Prometheus /metrics 엔드포인트
- [x] [CUSTOM] ADR 5건 (CSI 신호처리, 멀티노드, 카메라 융합, CF 릴레이, 관측소)
- [x] [CUSTOM] ESP-IDF v5.5.3 업그레이드 + Octal PSRAM 설정

---

## Phase 0: 기반정렬

**목적**: 후속 Phase 진행을 위한 전제 조건 확보 및 현장 검증

| # | 분류 | 우선순위 | 작업 | 상태 |
|---|------|----------|------|------|
| 0-1 | CUSTOM | P1 | breathing_bpm 이상값 수정 (node-3: 36 BPM → 범위 클램프 12-30) | ⬜ |
| 0-2 | CUSTOM | P1 | confidence 하드코딩 8곳 제거 (SensingPage, PoseFusionPage, csi_processor.py) | ⬜ |
| 0-3 | CUSTOM | P1 | LiveDemoPage camera mock 제거 ('standing' 0.7 고정값) | ⬜ |
| 0-4 | CUSTOM | P2 | 노드 물리 위치 검증 (전원 뽑기 테스트) — **현장 작업** | ⬜ |
| 0-5 | CUSTOM | P2 | 빈방 캘리브레이션 (퇴근 후) — **현장 작업** | ⬜ |
| 0-6 | CUSTOM | P2 | demo 데이터 silent fallback → 사용자 가시 알림 | ⬜ |

---

## Phase 1: Observatory 완전 이식

**목적**: ruvnet observatory/js/ 14개 파일 중 미이식 9개 모듈을 우리 Observatory에 통합
**원본**: `d:/home/ruvnet-RuView/ui/observatory/js/`

### 1-A. 즉시 이식 가능 (Three.js 독립 모듈)

| # | ruvnet 파일 | 줄수 | 분류 | 우선순위 | 작업 |
|---|-------------|------|------|----------|------|
| 1-1 | figure-pool.js | 513 | PORT | P1 | 4인 와이어프레임 풀(재사용) → public/observatory/js/figure-pool.js |
| 1-2 | pose-system.js | 567 | PORT | P1 | 7가지 포즈 애니메이션(standing/walking/lying/sitting/fallen/exercising/gesturing) → pose-system.js |
| 1-3 | convergence-engine.js | 221 | ADAPT | P1 | 데이터 융합 로직 → Zustand signalStore에 통합 + convergence-engine.js |
| 1-4 | holographic-panel.js | 121 | PORT | P2 | 홀로그래픽 생체신호 표시 → holographic-panel.js |
| 1-5 | nebula-background.js | 115 | PORT | P2 | 별 필드 배경 → nebula-background.js |
| 1-6 | post-processing.js | 125 | PORT | P2 | EffectComposer 톤매핑/블룸 → post-processing.js |
| 1-7 | scenario-props.js | 739 | PORT | P2 | 방 소품(의자/매트/문/벽/화면/책상) → scenario-props.js |
| 1-8 | subcarrier-manifold.js | 163 | ADAPT | P2 | 서브캐리어 주파수 표시 → subcarrier-manifold.js + SignalChart 연동 |
| 1-9 | mist-effect (demo-data 내) | - | PORT | P3 | 입자 미스트 효과 → mist-effect.js |

> **구현 순서**: 1-1 + 1-2 (figure-pool ↔ pose-system 강결합, 단일 PR) → 1-3 → 나머지 병렬

### 1-B. main.js 업데이트

| # | 분류 | 우선순위 | 작업 |
|---|------|----------|------|
| 1-10 | ADAPT | P1 | main.js: 이식된 모듈 초기화 순서 통합, WebSocket 데이터→포즈 애니메이션 연동 |
| 1-11 | ADAPT | P2 | ObservatoryMini.tsx: iframe 브릿지 메시지 스키마 확장 (pose, scenario 이벤트 추가) |

---

## Phase 2: UI 컴포넌트 이식

**목적**: ruvnet/ui/components/ 12개 파일(합계 8,765줄)을 React 19 + TypeScript 컴포넌트로 변환
**원본**: `d:/home/ruvnet-RuView/ui/components/`

### 2-A. Three.js 공용 인프라 (선행 필요)

| # | ruvnet 파일 | 줄수 | 분류 | 우선순위 | 작업 |
|---|-------------|------|------|----------|------|
| 2-1 | scene.js | 196 | ADAPT | P1 | `useThreeScene` 공용 훅 추출 → hooks/useThreeScene.ts (Observatory + LiveDemo 공유) |
| 2-2 | environment.js | 476 | PORT | P1 | 3D 방 환경(바닥/그리드/벽/AP마커/신호경로/감지존) → components/observatory/EnvironmentLayer.tsx |
| 2-3 | body-model.js | 645 | PORT | P1 | DensePose 24부위 메시 + BodyModelManager 6인 → hooks/useBodyModel.ts |

### 2-B. 신호 시각화

| # | ruvnet 파일 | 줄수 | 분류 | 우선순위 | 작업 |
|---|-------------|------|------|----------|------|
| 2-4 | signal-viz.js | 467 | ADAPT | P1 | CSI 진폭 히트맵 30×40 + 위상 플롯 + 도플러 + 모션 에너지 → components/charts/SignalVizPanel.tsx |
| 2-5 | gaussian-splats.js | 412 | PORT | P2 | 커스텀 셰이더 신호장 렌더러 → components/observatory/GaussianSplatField.tsx (WebGL2 런타임 체크, Canvas 폴백) |

### 2-C. 탭/페이지 개편

| # | ruvnet 파일 | 줄수 | 분류 | 우선순위 | 작업 |
|---|-------------|------|------|----------|------|
| 2-6 | SensingTab.js | 337 | ADAPT | P1 | WiFi 센싱 3D 필드 + RSSI 스파크라인 + 신호특성 → SensingPage.tsx 개편 |
| 2-7 | DashboardTab.js | 436 | ADAPT | P1 | API 정보 + CPU/메모리/디스크 사용률 + 존 점유율 통계 → DashboardPage.tsx 확장 |
| 2-8 | HardwareTab.js | 173 | ADAPT | P1 | 안테나 배열 인터랙션 + CSI 진폭/위상 디스플레이 → HardwarePage.tsx 확장 |
| 2-9 | LiveDemoTab.js | 1885 | ADAPT | P2 | WebSocket 실시간 포즈 + 3D 신체모델 → LiveDemoPage.tsx 전면 개편 |
| 2-10 | ModelPanel.js | 230 | PORT | P2 | 모델 목록/로드/LoRA 프로필 → components/model/ModelPanel.tsx (SettingsPage 서브탭) |
| 2-11 | TrainingPanel.js | 419 | PORT | P2 | CSI 녹음/훈련상태/손실차트(PCK) → components/training/TrainingPanel.tsx |
| 2-12 | SettingsPanel.js + SettingsPanel | 971 | ADAPT | P2 | 전역 설정 패널 → SettingsPage.tsx 확장 |

### 2-D. 누락 컴포넌트 (전수검증 후 추가)

| # | ruvnet 파일 | 줄수 | 분류 | 우선순위 | 작업 |
|---|-------------|------|------|----------|------|
| 2-13 | PoseDetectionCanvas.js | 1552 | ADAPT | P1 | 실시간 스켈레톤 렌더링 + pose trail → PoseDetectionCanvas.tsx 전면 재구현 |
| 2-14 | dashboard-hud.js | 429 | PORT | P1 | HUD 오버레이 (FPS/연결/신뢰도/모드) → components/observatory/DashboardHUD.tsx |
| 2-15 | sensing.service.js | 375 | ADAPT | P1 | CSI 센싱 데이터 수집 + RSSI 실시간 푸시 → services/sensingService.ts |
| 2-16 | observatory.html | - | ADAPT | P1 | Observatory 독립 페이지 → /observatory 라우트 추가 |
| 2-17 | viz.html | - | ADAPT | P2 | 3D 시각화 독립 페이지 → /viz 라우트 추가 |

> **구현 순서**: 2-1(useThreeScene) → 2-2+2-3 병렬 → 2-4 → 나머지 병렬
> **주의**: BodyModelManager 클래스 → `useBodyModel(count: number)` 훅 패턴으로 분해

---

## Phase 3: 신호처리 알고리즘 이식

**목적**: ruvnet의 고급 DSP 알고리즘을 csi_processor.py에 추가
**원본**: `d:/home/ruvnet-RuView/rust-port/wifi-densepose-rs/crates/wifi-densepose-signal/`

| # | ruvnet 출처 | 분류 | 우선순위 | 작업 |
|---|-------------|------|----------|------|
| 3-1 | wifi-densepose-hardware | ADAPT | P1 | **Hardware Normalizer**: Catmull-Rom 보간 + cross-hardware 일반화 → `normalize_hardware()` in csi_processor.py |
| 3-2 | wifi-densepose-signal / vitals | ADAPT | P1 | **HRV 완전 구현**: SDNN/RMSSD/PNN50 → `_compute_hrv()` 완성 (현재 프레임워크만) |
| 3-3 | 현장 작업 | CUSTOM | P1 | **낙상 데이터 수집 150건+** (50+ 낙상, 100+ 정상) → fall_detector.py 모델 훈련 — **현장 필수** |
| 3-4 | wifi-densepose-signal | PORT | P2 | **RF Tomography** (ISTA solver): MIMO 공간 재구성 → `rf_tomography.py` 신규 모듈 |
| 3-5 | wifi-densepose-signal | ADAPT | P2 | **Intention Detection**: 200-500ms 선행신호 감지 → event_engine.py에 통합 |
| 3-6 | ruvnet gesture.rs 참조 | PORT | P2 | **DTW Gesture Recognition**: 제스처 분류 → `gesture_classifier.py` 신규 모듈 |
| 3-7 | v1/src/models/densepose_head.py | ADAPT | P2 | **DensePose 헤드 신경망**: PyTorch 24부위 분할+UV 회귀 → `models/densepose_head.py` |
| 3-8 | v1/src/models/modality_translation.py | ADAPT | P2 | **Modality Translation**: CSI → 시각 특성 공간 변환 신경망 → `models/modality_translation.py` |
| 3-9 | v1/src/sensing/classifier.py | ADAPT | P1 | **PresenceClassifier**: RSSI 기반 ABSENT/PRESENT_STILL/ACTIVE 분류 → `sensing/classifier.py` |
| 3-10 | v1/src/sensing/feature_extractor.py | ADAPT | P1 | **RssiFeatureExtractor**: CUSUM 변화점 감지 + 호흡/운동 대역 검출 → `sensing/feature_extractor.py` |
| 3-11 | v1/src/sensing/rssi_collector.py | ADAPT | P1 | **RssiCollector**: WiFi RSSI 시계열 수집 + 윈도우 관리 → `sensing/rssi_collector.py` |

---

## Phase 4: 백엔드 서비스 완성

**목적**: ruvnet의 서비스 레이어를 api-gateway / signal-adapter에 이식
**원본**: `d:/home/ruvnet-RuView/ui/services/`, `d:/home/ruvnet-RuView/v1/src/services/`

| # | ruvnet 출처 | 분류 | 우선순위 | 작업 |
|---|-------------|------|----------|------|
| 4-1 | health.service.js / health_check.py | ADAPT | P1 | **HealthCheckService 완전 구현**: 컴포넌트 주기적 체크 + 상태 히스토리 → `apps/api-gateway/app/routes/health.py` 확장 |
| 4-2 | stream.service.js | ADAPT | P1 | **StreamService 완전 구현**: 스트리밍 로직 → `ws_manager.py` 보완 + 스트림 버퍼링 |
| 4-3 | model.service.js + v1/src/api/routers/pose.py | ADAPT | P2 | **Model 관리 API**: GET/POST /api/v1/models (로드/언로드/LoRA) → `apps/api-gateway/app/routes/models.py` |
| 4-4 | training.service.js + TrainingPanel | ADAPT | P2 | **Training API**: /api/v1/train/start-stop, /api/v1/recording/start-stop → `apps/api-gateway/app/routes/training.py` |
| 4-5 | data-processor.js | ADAPT | P2 | **데이터 전처리 파이프라인**: 서버사이드 정규화 → `signal-adapter/main.py` 통합 |
| 4-6 | orchestrator.py 참조 | CUSTOM | P2 | **OrchestratorService**: 서비스 라이프사이클 관리 → `services/orchestrator.py` (start_all.sh 대체) |
| 4-7 | v1/src/api/routers/pose.py | ADAPT | P1 | **Pose API 완성**: POST /analyze, /historical, GET /zone-occupancy/{id}, /zones-summary, /activities, /calibrate, /stats → `routes/pose.py` |
| 4-8 | v1/src/api/routers/stream.py | ADAPT | P1 | **Stream API 완성**: WS /api/v1/stream/pose, GET /stream/status, fps 제어 → `routes/stream.py` |
| 4-9 | v1/src/api/routers/health.py | ADAPT | P1 | **Ready 엔드포인트**: GET /ready (readiness probe) → `routes/health.py` 확장 |
| 4-10 | v1/src/database/ | ADAPT | P2 | **Database ORM + Migrations**: SQLAlchemy Device/Event/CSI 모델 + Alembic → `apps/api-gateway/database/` |
| 4-11 | v1/src/tasks/ | ADAPT | P3 | **Background Tasks**: backup.py / cleanup.py / monitoring.py → `apps/api-gateway/tasks/` |

---

## Phase 5: 카메라/ML 고도화

**목적**: AETHER re-ID 고도화, 낙상 모델 실용화, 포즈 시각화 완성
**원본**: `d:/home/ruvnet-RuView/rust-port/wifi-densepose-rs/crates/wifi-densepose-nn/`

| # | ruvnet 출처 | 분류 | 우선순위 | 작업 |
|---|-------------|------|----------|------|
| 5-1 | Phase 3-3 결과물 | CUSTOM | P1 | **앙상블 모델 훈련**: 데이터 150건 수집 완료 후 SVM+RF+GBDT 재훈련 및 배포 |
| 5-2 | wifi-densepose-nn (AETHER) | ADAPT | P2 | **AETHER Contrastive Embedding**: HSV histogram → 딥러닝 re-ID → `detector.py _compute_appearance()` 교체 |
| 5-3 | PoseDetectionCanvas.js (1552줄) | ADAPT | P2 | **PoseDetectionCanvas 완전 이식**: 실시간 포즈 스켈레톤 렌더러 → `PoseDetectionCanvas.tsx` 전면 개편 |
| 5-4 | 현장 작업 | CUSTOM | P2 | **모달리티 자동 전환 튜닝**: EMA 임계값 실환경 조정 (어둠/밝음/부재 시나리오별) |
| 5-5 | mmwave_fusion_bridge.py | ADAPT | P3 | **mmWave Kalman 80/20 융합 실환경 검증** |

---

## Phase 6: Rust 포팅

**목적**: ruvnet 18개 crate → ruView 4개 crate 핵심 기능 구현
**원본**: `d:/home/ruvnet-RuView/rust-port/wifi-densepose-rs/crates/`

### ruvnet 18 crates → ruView 4 crates 매핑

| ruView crate | ruvnet 대응 crate | 분류 |
|--------------|------------------|------|
| ruview-core | wifi-densepose-core + wifi-densepose-hardware | ADAPT |
| ruview-signal | wifi-densepose-signal + wifi-densepose-vitals | ADAPT |
| ruview-server | wifi-densepose-api + wifi-densepose-sensing-server | ADAPT |
| ruview-wasm | wifi-densepose-wasm + wifi-densepose-wasm-edge | ADAPT |

### 작업 목록

| # | 분류 | 우선순위 | 작업 |
|---|------|----------|------|
| 6-1 | CUSTOM | P1 | **rustup toolchain 설치** + wasm-pack + 기존 23 tests 빌드 검증 |
| 6-2 | ADAPT | P2 | **ruview-signal**: Butterworth/FFT/Hampel/Fresnel/BVP Rust 구현 — ruvnet wifi-densepose-signal 참조 |
| 6-3 | ADAPT | P2 | **ruview-core**: Hardware Normalizer + 다중인원 클러스터링 — ruvnet wifi-densepose-hardware 참조 |
| 6-4 | ADAPT | P3 | **ruview-server**: Axum HTTP/WS 서버로 signal-adapter 대체 (810x 성능 목표) |
| 6-5 | ADAPT | P3 | **ruview-wasm**: 브라우저 내 CSI 전처리 — ruvnet wifi-densepose-wasm-edge 참조 |
| 6-6 | CUSTOM | P3 | **1,000+ 테스트** (현재 23개) |

> **의존성**: 6-1이 모든 후속 작업의 전제. 6-4는 Phase 4 백엔드 API 설계 확정 후 진행.

---

## Phase 7: 품질/배포 고도화

**목적**: ruvnet의 운영 인프라를 우리 환경에 이식
**원본**: `d:/home/ruvnet-RuView/scripts/`, `d:/home/ruvnet-RuView/docs/`

| # | ruvnet 출처 | 분류 | 우선순위 | 작업 |
|---|-------------|------|----------|------|
| 7-1 | - | CUSTOM | P1 | **README.md 작성** (프로젝트 개요, 설치, 빠른 시작) |
| 7-2 | - | CUSTOM | P1 | **단위 테스트 추가**: signal-adapter + api-gateway 각 80% 커버리지 목표 |
| 7-3 | infra/blue-green 참조 | CUSTOM | P2 | **Blue-Green 무중단 배포** → `infra/blue-green/` |
| 7-4 | qemu-esp32s3-test.sh 등 | ADAPT | P3 | **QEMU 펌웨어 테스트** 9층 프레임워크 이식 → `firmware/tests/` |
| 7-5 | qemu-chaos-test.sh, qemu-mesh-test.sh | ADAPT | P3 | **QEMU 고급 테스트**: chaos 주입 + 다중노드 메시 + 스냅샷 회귀 → `firmware/tests/advanced/` |
| 7-6 | generate-witness-bundle.sh + WITNESS-LOG-028.md | ADAPT | P3 | **Witness Verification** SHA-256 증명 시스템 → `infra/witness/` |
| 7-7 | swarm_health.py | ADAPT | P3 | **Swarm Health 오라클**: 다중 노드 건강 모니터링 → `monitoring/` |
| 7-8 | monitoring/prometheus-config.yml + grafana-dashboard.json | ADAPT | P2 | **Prometheus + Grafana 스택**: 수집 설정 + 대시보드 + 알림 규칙 → `infra/monitoring/` |
| 7-9 | docker/Dockerfile.rust | ADAPT | P3 | **Rust 빌드 컨테이너**: Docker Compose에 rust-builder 서비스 추가 |

---

## Phase 8: ruView 커스텀 기능 (도메인 특화)

**목적**: ruvnet 원본에 없는 요양원·건물관제 특화 기능 개발. 100% CUSTOM.
**배경**: docs/STRATEGY_2026.md — 돌봄→건물관제→소방/스마트시티 3단계 전략

| # | 분류 | 우선순위 | 작업 |
|---|------|----------|------|
| 8-1 | CUSTOM | P1 | **낙상 자동 호출 워크플로우**: 낙상 감지 → 담당자 호출 (Webhook + 모바일 푸시) |
| 8-2 | CUSTOM | P1 | **멀티 층 건물 뷰**: 호실 배치 + 층별 존 집계 + 층 전환 네비게이션 |
| 8-3 | CUSTOM | P2 | **야간 모니터링 모드**: 야간 색상 테마 전환 + 알림 임계값 시간대 조정 |
| 8-4 | CUSTOM | P2 | **입주자 프로필 관리**: 이름/방번호/기저질환 → re-ID 연동 (AETHER Phase 5-2 이후) |
| 8-5 | CUSTOM | P2 | **일간·주간 바이탈 요약 리포트** PDF 생성 (호흡/심박 트렌드, 이상 이벤트) |
| 8-6 | CUSTOM | P2 | **Supabase 완전 연동**: 이벤트 이력 + 알림 기록 장기 저장 + RLS 정책 |
| 8-7 | CUSTOM | P3 | **모바일 반응형 UI** (관리자 스마트폰 접근) |

> **의존성**: 8-1은 Phase 0-6(API 인증) 필수. 8-4는 Phase 5-2(AETHER) 이후 권장.

---

## Phase 9: 펌웨어 고도화

**목적**: ruvnet firmware/esp32-csi-node/의 고급 기능 이식
**원본**: `d:/home/ruvnet-RuView/firmware/esp32-csi-node/main/`

| # | ruvnet 파일 | 분류 | 우선순위 | 작업 |
|---|-------------|------|----------|------|
| 9-1 | wasm_runtime.c/h | PORT | P1 | **WASM3 온-디바이스 인터프리터**: ESP32에서 WASM 알고리즘 실행 (ADR-040) → `vendor/.../main/wasm_runtime.c/h` |
| 9-2 | ota_update.c/h | PORT | P2 | **HTTP OTA 무선 업데이트**: 포트 8032, 파티션 안전 업데이트 → `vendor/.../main/ota_update.c/h` |
| 9-3 | wasm_upload.c/h | PORT | P2 | **WASM 모듈 동적 업로드**: HTTP 엔드포인트로 런타임 알고리즘 교체 → `vendor/.../main/wasm_upload.c/h` |
| 9-4 | swarm_bridge.c/h | PORT | P2 | **Swarm 코디네이터**: 멀티노드 Cognitum Seed 클러스터 (ADR-066) → `vendor/.../main/swarm_bridge.c/h` |
| 9-5 | power_mgmt.c/h | PORT | P3 | **전력 관리**: Sleep/Wake 시간대별 스케줄 → `vendor/.../main/power_mgmt.c/h` |
| 9-6 | display_task.c/h + display_ui.c/h | PORT | P3 | **LVGL 온보드 디스플레이**: ST7789/AMOLED 상태 표시 + CSI 히트맵 (ADR-045) → `vendor/.../main/display_*.c/h` |
| 9-7 | rvf_parser.c/h | PORT | P3 | **RVF 바이너리 파서**: RuVector Format 파싱 (ADR-002) → `vendor/.../main/rvf_parser.c/h` |

> **의존성**: Phase 6 Rust WASM(6-5) 완료 후 9-1 진행. 9-2(OTA)는 펌웨어 안정화(Phase 0) 이후.

---

## Phase 10: 모바일·데스크톱

**목적**: ruvnet의 크로스플랫폼 클라이언트를 ruView에 이식
**원본**: `d:/home/ruvnet-RuView/ui/mobile/`, `d:/home/ruvnet-RuView/rust-port/.../wifi-densepose-desktop/`

| # | ruvnet 출처 | 분류 | 우선순위 | 작업 |
|---|-------------|------|----------|------|
| 10-1 | ui/mobile/ (React Native Expo) | ADAPT | P2 | **모바일 앱**: 화면/훅/네비게이션 → `apps/mobile/` (요양원 관리자용) |
| 10-2 | ui/mobile/src/assets/webview/ | PORT | P2 | **모바일 웹뷰**: Gaussian Splats + Observatory 임베드 → 모바일 앱 내 3D 뷰 |
| 10-3 | wifi-densepose-desktop (Tauri v2) | ADAPT | P3 | **Tauri 데스크톱 앱**: 로컬 관제 센터용 네이티브 앱 → `apps/desktop/` (ADR-054) |

> **의존성**: Phase 4 API 완성 후 모바일 앱 개발 가능. Phase 6 Rust 이후 데스크톱 앱 가능.

---

## 다음 즉시 실행 가능 작업

> (2026-03-27 기준) Phase 0 잔여 → Phase 4-7,8 Pose/Stream API → Phase 2-13,14 누락 컴포넌트

| 순서 | 작업 | Phase | 예상 |
|------|------|-------|------|
| 1 | Pose API 완성 (analyze/zone-occupancy/calibrate) | 4-7 | 반나절 |
| 2 | Stream API (WS /stream/pose) | 4-8 | 반나절 |
| 3 | PoseDetectionCanvas.tsx 전면 재구현 | 2-13 | 하루 |
| 4 | dashboard-hud.js → DashboardHUD.tsx 이식 | 2-14 | 2시간 |
| 5 | Sensing 패키지 (classifier + feature_extractor) | 3-9, 3-10 | 하루 |
| 6 | nebula-background + post-processing 이식 | 1-5, 1-6 | 2시간 |

---

## ruvnet/RuView 참조 파일 색인

| 분류 | ruvnet 파일 | 대응 Phase |
|------|-------------|-----------|
| Observatory | `ui/observatory/js/figure-pool.js` | Phase 1-1 |
| Observatory | `ui/observatory/js/pose-system.js` | Phase 1-2 |
| Observatory | `ui/observatory/js/convergence-engine.js` | Phase 1-3 |
| Observatory | `ui/observatory/js/holographic-panel.js` | Phase 1-4 |
| Observatory | `ui/observatory/js/nebula-background.js` | Phase 1-5 |
| Observatory | `ui/observatory/js/post-processing.js` | Phase 1-6 |
| Observatory | `ui/observatory/js/scenario-props.js` | Phase 1-7 |
| Observatory | `ui/observatory/js/subcarrier-manifold.js` | Phase 1-8 |
| 3D 컴포넌트 | `ui/components/scene.js` | Phase 2-1 |
| 3D 컴포넌트 | `ui/components/environment.js` | Phase 2-2 |
| 3D 컴포넌트 | `ui/components/body-model.js` | Phase 2-3 |
| 신호처리 | `ui/components/signal-viz.js` | Phase 2-4 |
| 3D 렌더링 | `ui/components/gaussian-splats.js` | Phase 2-5 |
| UI 탭 | `ui/components/SensingTab.js` | Phase 2-6 |
| UI 탭 | `ui/components/DashboardTab.js` | Phase 2-7 |
| UI 탭 | `ui/components/HardwareTab.js` | Phase 2-8 |
| UI 탭 | `ui/components/LiveDemoTab.js` | Phase 2-9 |
| UI 컴포넌트 | `ui/components/PoseDetectionCanvas.js` | Phase 2-13 |
| UI 컴포넌트 | `ui/components/dashboard-hud.js` | Phase 2-14 |
| UI 서비스 | `ui/services/sensing.service.js` | Phase 2-15 |
| UI 페이지 | `ui/observatory.html` | Phase 2-16 |
| UI 페이지 | `ui/viz.html` | Phase 2-17 |
| Sensing 패키지 | `v1/src/sensing/classifier.py` | Phase 3-9 |
| Sensing 패키지 | `v1/src/sensing/feature_extractor.py` | Phase 3-10 |
| Sensing 패키지 | `v1/src/sensing/rssi_collector.py` | Phase 3-11 |
| ML 모델 | `v1/src/models/densepose_head.py` | Phase 3-7 |
| ML 모델 | `v1/src/models/modality_translation.py` | Phase 3-8 |
| API | `v1/src/api/routers/pose.py` | Phase 4-7 |
| API | `v1/src/api/routers/stream.py` | Phase 4-8 |
| Database | `v1/src/database/` | Phase 4-10 |
| 모니터링 | `monitoring/prometheus-config.yml` | Phase 7-8 |
| 모니터링 | `monitoring/grafana-dashboard.json` | Phase 7-8 |
| QEMU | `scripts/qemu-chaos-test.sh` | Phase 7-5 |
| QEMU | `scripts/qemu-mesh-test.sh` | Phase 7-5 |
| 펌웨어 | `firmware/.../wasm_runtime.c/h` | Phase 9-1 |
| 펌웨어 | `firmware/.../ota_update.c/h` | Phase 9-2 |
| 펌웨어 | `firmware/.../swarm_bridge.c/h` | Phase 9-4 |
| 모바일 | `ui/mobile/` (React Native) | Phase 10-1 |
| 데스크톱 | `rust-port/.../wifi-densepose-desktop/` | Phase 10-3 |
| UI 패널 | `ui/components/ModelPanel.js` | Phase 2-10 |
| UI 패널 | `ui/components/TrainingPanel.js` | Phase 2-11 |
| UI 패널 | `ui/components/SettingsPanel.js` | Phase 2-12 |
| DSP 알고리즘 | `rust-port/.../wifi-densepose-hardware/` | Phase 3-1 |
| DSP 알고리즘 | `rust-port/.../wifi-densepose-signal/` | Phase 3-2, 3-4~3-6 |
| 카메라 ML | `rust-port/.../wifi-densepose-nn/` (AETHER) | Phase 5-2 |
| 서비스 | `ui/services/health.service.js` | Phase 4-1 |
| 서비스 | `ui/services/stream.service.js` | Phase 4-2 |
| 서비스 | `ui/services/model.service.js` | Phase 4-3 |
| 서비스 | `ui/services/training.service.js` | Phase 4-4 |
| 서비스 | `ui/services/data-processor.js` | Phase 4-5 |
| Rust crates | `rust-port/wifi-densepose-rs/crates/` | Phase 6 |
| QEMU 테스트 | `scripts/qemu-esp32s3-test.sh` | Phase 7-4 |
| Witness | `scripts/generate-witness-bundle.sh` | Phase 7-5 |
| ADR | `docs/adr/` (ADR-001~066) | Phase 전반 참조 |

---

## 코드 검토 이력

| 날짜 | P1 | P2 | P3 | 문서 |
|------|-----|-----|-----|------|
| 2026-03-23 | 9/9 수정 | 19건 (10 수정) | 20건 | CODE_REVIEW_2026-03-23.md |
| 2026-03-27 | heart_rate uint32 파싱 수정 | breathing_bpm 이상값 잔여 | confidence 하드코딩 8곳 잔여 | — |
