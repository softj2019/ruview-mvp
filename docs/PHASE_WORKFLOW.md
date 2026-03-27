# RuView Phase Workflow

> **목표**: ruvnet/RuView를 원본 베이스로, 요양원·건물관제 특화 WiFi-Sensing 플랫폼으로 커스터마이징
> **갱신**: 2026-03-27 | 95+ commits | v0.1.0-alpha
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
| 1 Observatory 이식 | 3D 관측소 완전 구현 | 40% | figure-pool, pose-system 등 9개 모듈 |
| 2 UI 컴포넌트 이식 | ruvnet 12개 컴포넌트 React 변환 | 30% | body-model, env, gaussian-splats |
| 3 신호처리 알고리즘 | HW Normalizer, HRV, Gesture | 55% | Hardware Normalizer, HRV 완성, Gesture |
| 4 백엔드 서비스 | Model/Training/Orchestrator API | 30% | model.py, training.py, health 확장 |
| 5 카메라/ML 고도화 | AETHER re-ID, 낙상 모델 | 70% | 데이터 150건 수집, AETHER |
| 6 Rust 포팅 | 4 crates 구현 | 10% | toolchain 설치, signal 구현 |
| 7 품질/배포 | QEMU, Witness, Blue-Green | 60% | QEMU, Witness, README |
| 8 커스텀 기능 | 돌봄·건물관제 특화 | 0% | 알림 워크플로, 멀티층 뷰 |

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
  └─→ Phase 8 (커스텀: Phase 0-6 인증 완료 후 병행 가능)
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
| 7-5 | generate-witness-bundle.sh + WITNESS-LOG-028.md | ADAPT | P3 | **Witness Verification** SHA-256 증명 시스템 → `infra/witness/` |
| 7-6 | swarm_health.py | ADAPT | P3 | **Swarm Health 오라클**: 다중 노드 건강 모니터링 → `monitoring/` |

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

## 다음 즉시 실행 가능 작업

> Phase 0 버그 수정 → Phase 1-A figure-pool + pose-system 병렬 이식

| 순서 | 작업 | Phase | 예상 |
|------|------|-------|------|
| 1 | breathing_bpm 범위 클램프 수정 | 0-1 | 30분 |
| 2 | confidence 하드코딩 8곳 제거 | 0-2 | 1시간 |
| 3 | figure-pool.js + pose-system.js 이식 | 1-1, 1-2 | 반나절 |
| 4 | useThreeScene 공용 훅 추출 | 2-1 | 2시간 |
| 5 | Hardware Normalizer 구현 | 3-1 | 반나절 |

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
