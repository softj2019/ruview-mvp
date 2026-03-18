# RuView MVP 진행 체크리스트

> 최종 업데이트: 2026-03-18

## Phase 0: 설계 고정 및 저장소 생성 ✅

- [x] 모노레포 생성 (ruview-mvp)
- [x] 디렉토리 구조 생성
- [x] package.json / pnpm workspace
- [x] .gitignore / .editorconfig / .prettierrc
- [x] GitHub 원격 저장소 생성
- [x] main + develop 브랜치
- [x] 브랜치 보호 규칙
- [x] 라벨 21개 생성
- [x] 마일스톤 M0~M5 생성
- [x] PR/Issue 템플릿
- [x] CODEOWNERS
- [x] CI/CD GitHub Actions
- [x] 에이전트 문서 6개

## Phase 1: 로컬 장비 연동 ✅

- [x] ESP32 COM3 연결 확인 (CP2102 드라이버)
- [x] 칩 타입 확인 (ESP32-D0WDQ6 → S3 필요)
- [x] RuView 업스트림 클론
- [x] ESP32-S3 호환성 분석
- [x] Mock CSI 생성기 (5 시나리오)
- [x] Mock 서버 (FastAPI :8001)
- [x] WebSocket 브로드캐스트 (10Hz)
- [x] Supabase 테이블 5개 생성
- [x] ESP32-S3 설정 스크립트 (setup_device.py)
- [x] 시리얼 모니터 (monitor.py)
- [ ] ESP32-S3 실장비 연동 (배송 대기)

## Phase 2: Python Adapter / Gateway ✅

- [x] CSI Processor (amplitude/phase/motion_index)
- [x] Event Engine (presence/motion/fall/signal_weak)
- [x] WebSocket Manager
- [x] Supabase Client
- [x] Mock Generator (idle/presence/motion/fall/breathing)
- [x] API Gateway 라우트 (devices/zones/events)
- [x] Docker Compose 설정
- [ ] 실장비 CSI 연동 (ESP32-S3 배송 후)

## Phase 3: React 2D 관제 UI ✅

- [x] Vite + React + TypeScript 초기화
- [x] Tailwind CSS 다크모드 100%
- [x] Zustand 스토어 4개
- [x] WebSocket 훅 (auto-reconnect, callbacksRef)
- [x] Dashboard 페이지
- [x] KPI 카드 (4종)
- [x] 2D Floor View (SVG)
- [x] Alert Panel
- [x] Device List
- [x] Signal Chart (Recharts)
- [x] Devices 페이지
- [x] Events 페이지
- [x] Settings 페이지 (시나리오 제어)
- [x] 네비게이션 바
- [x] useMemo로 Zustand 무한루프 수정

## Phase 4: 3D Observatory 통합 ✅

- [x] RuView Observatory UI 복사
- [x] iframe bridge 구현
- [x] 전체화면 / 새탭 열기
- [x] postMessage 리스너
- [x] 경로 수정 (CSS/JS)
- [ ] React ↔ Observatory 상태 동기화 (2차)
- [ ] React Three Fiber 이관 (백로그)

## Phase 5: 자동 배포 및 외부 시연 ✅

- [x] Cloudflare Pages 프로젝트 생성
- [x] 빌드 + 배포 (ruview-monitor.pages.dev)
- [x] _redirects SPA 라우팅
- [x] 자동 WS URL 감지 (localhost vs deployed)
- [ ] Cloudflare Tunnel 설정 (예정)
- [ ] Cloudflare Access 정책 (예정)

## Phase 6: 데모 시나리오 검증 🔧

- [x] 데모 시나리오 8개 작성
- [x] 발표자 스크립트 작성
- [ ] 시나리오 1: 시스템 개요 시연
- [ ] 시나리오 2: 재실 감지 시연
- [ ] 시나리오 3: 움직임 감지 시연
- [ ] 시나리오 4: 낙상 감지 시연
- [ ] 시나리오 5: 생체신호 시연
- [ ] 시나리오 6: 디바이스 관리 시연
- [ ] 시나리오 7: 3D Observatory 시연
- [ ] 시나리오 8: 외부 접속 시연
- [ ] 전체 데모 리허설

## 하드웨어 구매

- [x] ESP32 기본형 COM3 확인
- [ ] ESP32-S3-DevKitC-1 N16R8 구매 (추천: HG 23,000원)
- [ ] 2~3개 구매 (멀티스태틱 메쉬 테스트)

## 배포 URL

| 환경 | URL |
|------|-----|
| 로컬 React | http://localhost:5280 |
| 로컬 Mock | http://localhost:8001 |
| Production | https://ruview-monitor.pages.dev |
| GitHub | https://github.com/softj2019/ruview-mvp |
