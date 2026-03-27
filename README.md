# ruView — WiFi CSI 재실·낙상 감지 시스템

> ESP32-S3 × Python × React — 비접촉 스마트 모니터링

[![CI](https://github.com/ruview/ruview/actions/workflows/ci.yml/badge.svg)](https://github.com/ruview/ruview/actions)
[![Deploy](https://img.shields.io/badge/deploy-Cloudflare%20Pages-orange)](https://ruview-monitor.pages.dev)
[![Version](https://img.shields.io/badge/version-0.1.0--alpha-blue)](package.json)

## 특징

- **WiFi CSI 비접촉 감지**: 6개 ESP32-S3 노드가 채널 상태 정보(CSI)를 실시간 수집, 사람 감지·낙상 감지·바이탈 사인(호흡/심박) 측정
- **ML 앙상블 낙상 감지**: SVM + Random Forest + GBDT 앙상블 (95%+ 정확도 목표), 교차검증 포함
- **센서 융합**: YOLOv8-pose 카메라 + CSI + mmWave 레이더 Kalman 필터 융합
- **Three.js 3D 관측소**: 가우시안 스플랫, 실시간 WebSocket 업데이트, Observatory HUD
- **4존 평면도**: 실시간 재실자 수·RSSI·BPM·HR 라벨, 드래그-드롭 노드 배치
- **클라우드 릴레이**: Cloudflare Workers 브릿지 → Pages CDN 배포

## 빠른 시작

### 사전 요구사항

- Node.js 20+, pnpm 9+
- Python 3.12+
- Docker / Docker Compose (선택)

### 설치 및 실행

```bash
# 저장소 클론
git clone https://github.com/ruview/ruview.git
cd ruview

# 의존성 설치
pnpm install

# 개발 서버 시작 (각 터미널에서 실행)
pnpm dev:web      # 웹 모니터  → http://localhost:5280
pnpm dev:api      # API 게이트웨이 → http://localhost:8000
pnpm dev:adapter  # 신호 어댑터  → http://localhost:8001

# Python 서비스 의존성
cd services/signal-adapter
pip install -r requirements.txt

# 전체 스택 일괄 시작 (편의 스크립트)
bash start_all.sh
```

### Docker Compose로 실행

```bash
docker compose -f docker/docker-compose.yml up -d
```

### 빌드

```bash
pnpm build:web    # 웹 모니터 프로덕션 빌드
pnpm lint         # 전체 린트
pnpm typecheck    # TypeScript 타입 검사
```

## 아키텍처

4계층 파이프라인으로 구성됩니다.

```
┌─────────────────────────────────────────────────────────┐
│  Layer 1 — 펌웨어 (ESP32-S3 × 6)                        │
│  ESP-IDF C · WiFi CSI API · 채널 호핑                    │
│  UDP → 192.168.x.x:5500                                  │
└───────────────────┬─────────────────────────────────────┘
                    │ UDP multicast (CSI frames 100Hz)
┌───────────────────▼─────────────────────────────────────┐
│  Layer 2 — 신호 처리 (signal-adapter :8001)              │
│  Python 3.12 · FastAPI · NumPy · SciPy · scikit-learn    │
│  · Butterworth / FFT / Hampel 필터                       │
│  · Welford Z-score 온라인 통계                           │
│  · STFT Spectrogram / BVP / Fresnel Zone                 │
│  · ML 앙상블 낙상 감지 (SVM+RF+GBDT)                    │
│  · Kalman 스무딩 재실 카운트                              │
│  ↕ WebSocket broadcast                                   │
└───────────────────┬─────────────────────────────────────┘
                    │ REST + WebSocket
┌───────────────────▼─────────────────────────────────────┐
│  Layer 3 — API 게이트웨이 (api-gateway :8000)            │
│  Python · FastAPI · 프록시 라우터                        │
│  /devices · /zones · /events · /ws/events                │
│  ↕ camera-service (YOLOv8-pose, :8002)                   │
└───────────────────┬─────────────────────────────────────┘
                    │ WebSocket / REST
┌───────────────────▼─────────────────────────────────────┐
│  Layer 4 — 웹 모니터 (web-monitor :5280)                 │
│  React 19 · TypeScript · Vite 6 · TailwindCSS 3          │
│  Zustand 5 스토어 · Three.js 3D 관측소                   │
│  8개 라우트: Dashboard / Sensing / LiveDemo / ...        │
│                                                          │
│  [클라우드] Cloudflare Workers 릴레이                    │
│  → https://ruview-monitor.pages.dev                      │
└─────────────────────────────────────────────────────────┘
```

### 서비스 포트

| 서비스 | 포트 | 설명 |
|--------|------|------|
| web-monitor | 5280 | React 대시보드 |
| api-gateway | 8000 | REST + WS 프록시 |
| signal-adapter | 8001 | CSI 핵심 처리 |
| camera-service | 8002 | YOLOv8-pose |

## Phase 진행 상황

| Phase | 내용 | 진행률 | 비고 |
|-------|------|--------|------|
| 0 | 기반 안정화 (ESP32 프로비저닝, 서비스 자동화) | 85% | 노드 물리검증 잔여 |
| 1 | Observatory 이식 (3D 관측소 완전 구현) | 55% | nebula/post-processing 잔여 |
| 2 | UI 컴포넌트 이식 (ruvnet 15개 컴포넌트) | 30% | PoseDetectionCanvas 잔여 |
| 3 | 신호처리 알고리즘 (HW Normalizer, HRV, Gesture) | 65% | DTW Gesture 잔여 |
| 4 | 백엔드 서비스 (Pose/Stream/Sensing API) | 20% | Pose API 전체 잔여 |
| 5 | 카메라/ML 고도화 (AETHER re-ID, 낙상 모델) | 70% | 현장 데이터 150건 수집 중 |
| 6 | Rust 포팅 (4 crates: core/signal/server/wasm) | 10% | toolchain 설치, signal 구현 |
| 7 | 품질/배포 (QEMU, Witness, Blue-Green, Prometheus) | 55% | Grafana 스택 잔여 |
| 8 | 커스텀 기능 (돌봄·건물관제 특화) | 0% | 알림 워크플로, 멀티층 뷰 |
| 9 | 펌웨어 고도화 (WASM, Swarm, OTA) | 0% | wasm_runtime, swarm_bridge |
| 10 | 모바일·데스크톱 (React Native Expo, Tauri) | 0% | 모바일 앱, 데스크톱 앱 |

## 프로젝트 구조

```
ruView/
├── apps/
│   ├── api-gateway/          # Python FastAPI REST+WS 프록시 (:8000)
│   └── web-monitor/          # React 19 + Vite 6 대시보드 (:5280)
├── services/
│   ├── signal-adapter/       # CSI 핵심 처리 파이프라인 (:8001)
│   ├── camera-service/       # YOLOv8-pose + 트래킹 + 프라이버시 블러
│   └── supabase-sync/        # Supabase 데이터 동기화
├── rust-port/                # Phase 6 Rust 포팅 (4 crates)
├── esp32/                    # ESP32 펌웨어 드라이버
├── infra/                    # Docker, Cloudflare, Blue-Green 배포
├── monitoring/               # Prometheus + Grafana + Swarm Health
├── firmware/tests/           # QEMU 펌웨어 스모크 테스트
└── docs/                     # ADR, Phase 워크플로, 아키텍처 다이어그램
```

## API 레퍼런스

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/health` | 서비스 헬스 체크 |
| GET | `/api/devices` | ESP32 노드 목록 |
| PUT | `/api/devices/{id}/position` | 노드 위치 업데이트 |
| GET | `/api/zones` | 존별 재실자 수 |
| POST | `/api/calibration/empty-room` | 빈방 기준선 캡처 |
| POST | `/api/csi/ingest` | CSI 데이터 직접 수집 |
| WS | `/ws/events` | 실시간 이벤트 스트림 |

## 관련 문서

- [Phase 워크플로](docs/PHASE_WORKFLOW.md) — Phase 0-10 상세 진행 계획
- [2026 전략](docs/STRATEGY_2026.md) — 돌봄→건물관제→소방/스마트시티 진입 전략
- [ADR](docs/adr/) — 아키텍처 결정 기록 5건
- [Blue-Green 배포](infra/blue-green/README.md) — 무중단 배포 가이드

## 라이선스

MIT
