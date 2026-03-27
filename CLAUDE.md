# ruView — Claude Code 팀 구성

## 프로젝트 개요
- WiFi CSI 기반 비접촉 재실감지/낙상감지 서비스 MVP — 모노레포(pnpm workspace)
- ESP32-S3 6대 → Python 신호처리 → React 대시보드 + Three.js 3D 관측소
- 배포: https://ruview-monitor.pages.dev (Cloudflare Pages)
- 버전: 0.1.0-alpha | 95+ commits | 33 기능 완료

## 기술 스택
| 계층 | 기술 | 비고 |
|------|------|------|
| 펌웨어 | ESP-IDF C | WiFi CSI, 채널 호핑 |
| 백엔드 | Python 3.11, FastAPI | NumPy, SciPy, scikit-learn |
| 프론트엔드 | React 19 + TypeScript | Vite 6, TailwindCSS 3, Zustand 5 |
| 3D 시각화 | Three.js | Observatory, R3F |
| AI/ML | YOLOv8-pose | 자세 분류, 스켈레톤 |
| DB | Supabase (PostgreSQL) | RLS, Realtime |
| 클라우드 | Cloudflare | Workers (relay), Pages (CDN) |
| Rust 포팅 | Axum, Tokio, wasm-bindgen | Phase 6 대상 |

---

## 팀 포지셔닝

### 🏛 Architect (Opus) — 설계/계획/검토/검수
트리거: 계획, 설계, 분석, 검토, 검수, 체크리스트, 이슈, 재구성

**담당 영역:**
- 전체 시스템 아키텍처 의사결정 (ADR 작성/검토)
- CSI 신호 처리 파이프라인 설계 (ESP32 → signal-adapter → api-gateway → web-monitor)
- Phase 워크플로 관리 및 다음 단계 계획
- 코드 리뷰 (P1/P2 이슈 식별 및 수정 방향)
- Rust 포팅 아키텍처 (ruview-core/signal/server/wasm 구조)
- 마이크로서비스 간 통신 프로토콜 및 WebSocket 메시지 스키마
- 보안/인증 설계 (API key, CORS)

### 🔨 Builder (Sonnet) — 빌드/코딩/인프라
트리거: 만들어, 구현, 수정, 빌드, 배포, 코드, 고쳐

**담당 영역:**
- web-monitor: React 페이지/컴포넌트 구현 (8개 라우트)
- signal-adapter: CSI 처리 파이프라인 구현 (main.py, csi_processor.py)
- api-gateway: REST + WebSocket 프록시 엔드포인트
- camera-service: YOLOv8-pose 감지 + 트래킹
- observatory: Three.js 3D 시각화 (main.js)
- rust-port: 4개 crate 구현 (core/signal/server/wasm)
- Docker Compose, CI/CD, 배포 스크립트

### 🔍 Scout (Haiku) — 탐색/진단/확인
트리거: 확인, 찾아, 검색, 현황, 왜, 상태, 에러

**담당 영역:**
- 서비스 상태 확인 (api-gateway:8000, signal-adapter:8001, web:5280)
- CSI 신호 수신/처리 로그 분석
- WebSocket 연결 진단 (reconnection, backoff)
- 빌드 에러 / TypeScript 타입 에러 탐색
- pnpm workspace 의존성 충돌 확인
- ESP32 노드 온라인/오프라인 현황

---

## 프로젝트 구조
```
ruView/
├── apps/
│   ├── api-gateway/          # Python FastAPI (port 8000) — REST+WS 프록시
│   │   └── app/routers/      # devices, zones, events 엔드포인트
│   └── web-monitor/          # React 19 + Vite 6 (port 5280)
│       ├── src/
│       │   ├── pages/        # 8개 라우트 (Dashboard, Sensing, LiveDemo...)
│       │   ├── components/   # floor/, camera/, charts/, alerts/, observatory/
│       │   ├── stores/       # Zustand (device, signal, zone, event, alert)
│       │   └── hooks/        # useWebSocket (exponential backoff)
│       └── public/observatory/  # Three.js 3D 관측소
├── services/
│   ├── signal-adapter/       # Python FastAPI (port 8001) — CSI 핵심 처리
│   │   ├── main.py           # UDP 수신, WS 브로드캐스트, 이벤트 엔진
│   │   ├── csi_processor.py  # Hampel, Welford, FFT, BVP, STFT 알고리즘
│   │   ├── event_engine.py   # 이벤트 감지 로직
│   │   ├── fall_detector.py  # ML 앙상블 (SVM+RF+GBDT)
│   │   └── notifier.py       # 알림 (토스트, 웹훅, rate limiting)
│   ├── camera-service/       # YOLOv8-pose + 트래킹 + 프라이버시 블러
│   ├── demo-recorder/        # 데모 녹화
│   └── supabase-sync/        # Supabase 데이터 동기화
├── rust-port/                # Phase 6 Rust 포팅
│   ├── ruview-core/          # 핵심 타입, CsiFrame 파싱, WelfordStats
│   ├── ruview-signal/        # DSP 알고리즘 (Hampel, CSI Ratio, BPM...)
│   ├── ruview-server/        # Axum HTTP/WS 서버 (스캐폴드)
│   └── ruview-wasm/          # WASM 바인딩 (스캐폴드)
├── esp32/                    # ESP32 펌웨어 드라이버
├── infra/                    # Docker, Cloudflare, Supabase 설정
├── docs/
│   ├── PHASE_WORKFLOW.md     # Phase 0-7 진행 상태 (마스터 문서)
│   ├── CODE_REVIEW_2026-03-23.md
│   ├── adr/                  # 아키텍처 결정 기록 5건
│   └── architecture/         # 시스템 아키텍처 다이어그램
└── docker/                   # Docker Compose 설정
```

## 포트 정책
D:\home\port-registry.json 참고. port-guard 감시 중.
- web-monitor: 5280
- api-gateway: 8000 (내부)
- signal-adapter: 8001 (내부)

## Key Commands
- `pnpm dev:web` — 웹 모니터 개발서버 (:5280)
- `pnpm dev:api` — API 게이트웨이 (uvicorn :8000)
- `pnpm dev:adapter` — 신호 어댑터 (uvicorn :8001)
- `pnpm build:web` — 웹 모니터 프로덕션 빌드
- `pnpm lint` / `pnpm typecheck` — 전체 린트/타입체크

## 사용자 패턴
- 묻지 말고 진행, 완료 후 결과만 보고
- 한글 커밋 (기능:, 수정:, 개선:)
- 다크모드 100% 사용 (Tailwind dark: 클래스)

## 현재 Phase 진행 상태
> 상세: docs/PHASE_WORKFLOW.md 참조

| Phase | 내용 | 진행률 | 잔여 |
|-------|------|--------|------|
| 0 기반 안정화 | ESP32 프로비저닝, 서비스 자동화 | 85% | 노드 물리검증, 빈방 캘리브레이션 |
| 1 CSI 신호처리 | Butterworth/FFT/Hampel/Welford/BVP | **100%** | - |
| 2 시각화 | 4존 평면도, 3D 관측소, KPI, 8페이지 | **95%** | - |
| 3 낙상 감지 | ML 앙상블, 알림, 교차검증 | 80% | 현장 데이터 수집 (150건+) |
| 4 카메라 CV | YOLOv8, 트래킹, re-ID, 블러 | **100%** | - |
| 5 센서 융합 | Kalman, mmWave, 자세 융합 | 85% | 모달리티 자동 전환 |
| 6 Rust 포팅 | 4 crate 스캐폴드, 23 테스트 | 20% | Axum 서버, WASM, 1000+ 테스트 |
| 7 배포/운영 | ADR, Prometheus, Docker(스캐폴드) | 40% | CI/CD, README, Blue-Green |
