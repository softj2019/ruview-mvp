# RuView 고도화 Phase Workflow

> 기준: ruvnet/RuView 전수조사 + 정밀 코드 검토 + 사용자 요건
> 갱신: 2026-03-23 (52 commits)
> 참조: `d:/home/ruvnet-RuView` (ruvnet/RuView.git)

---

## 현재 상태 요약

| 항목 | 상태 | 비고 |
|------|------|------|
| ESP32 | 6대 온라인 (4개 호실 커버) | Node 2,3 간헐 offline |
| 호흡/심박 | ✅ 서버 추출 (FFT+Butterworth) | br:14-27, hr:70-90 |
| 자세 감지 | ✅ 카메라+CSI 융합 | standing(0.95) 확인 |
| 다중인원 | ✅ 상관 클러스터링 | est_p 1-5 |
| 4개 존 | ✅ per-zone presenceCount | |
| 카메라 | ✅ YOLOv8-pose + 스켈레톤 | 30fps |
| 관측소 | ⚠️ 라이브 불안정 | localStorage 캐시 |
| SOTA 알고리즘 | ✅ Hampel/CSI Ratio/Fresnel/STFT | |
| 코드 검토 | ✅ P1 9/9 수정 | |

---

## Phase 0: 기반 안정화

- [x] 0-1. ESP32 6대 프로비저닝 + 채널 호핑 펌웨어
- [x] 0-2. start_all.sh 서비스 자동화
- [x] 0-3. 브로드캐스트 throttling (500ms) + 백프레셔
- [x] 0-4. numpy CSI 파싱 + executor 비블로킹
- [x] 0-5. offline vitals 리셋
- [ ] 0-6. 노드 물리 위치 검증 (전원 뽑기)
- [ ] 0-7. 빈 방 캘리브레이션 (퇴근 후)
- [ ] 0-8. 관측소 라이브 전환 안정화

---

## Phase 1: CSI 신호처리 ✅ 완료

- [x] 1-1. 서버 호흡/심박 추출 (Butterworth+FFT+Zero-crossing)
- [x] 1-1b. SOTA: Hampel 필터, CSI Ratio, Fresnel Zone
- [x] 1-1c. CSI Spectrogram (STFT) + doppler_velocity
- [x] 1-2. Welford z-score 재실 감지 (자동 캘리브레이션)
- [x] 1-3. 다중인원 분리 (서브캐리어 상관 클러스터링)
- [x] 1-4. 채널 호핑 펌웨어 (ch1/6/11, 50ms dwell)
- [ ] 1-5. BVP (Body Velocity Profile) — Widar 3.0 포팅
- [ ] 1-6. 서브캐리어 감도 선택 (subcarrier_selection.rs)

---

## Phase 2: 시각화 ✅ 대부분 완료

- [x] 2-1. 4개 존 (1001-1004) + per-zone presence 색상
- [x] 2-2. 관측소 CSI 히트맵 패널 (30×40, Canvas texture)
- [x] 2-3. 관측소 신호필드 floor (InstancedMesh)
- [x] 2-4. 관측소 바이탈 애니메이션 (심박 글로우 + 호흡 복부)
- [x] 2-5. 관측소 위상 플롯 패널 (30 서브캐리어 라인)
- [x] 2-6. 관측소 도플러 스펙트럼 패널 (16바)
- [x] 2-7. KPI 바이탈 카드 + 신호차트 강화
- [x] 2-8. 평면도 라벨 강화 (RSSI+BPM+HR) + 히트맵 범례
- [x] 2-9. confidence 기반 피규어 색상
- [x] 2-10. ring buffer 최적화

### 2-11. ruvnet UI 미적용 컴포넌트 (NEW)

#### 관측소 추가 (HIGH)
- [ ] **Vitals Oracle** — 호흡 링(violet) + 심박 링(crimson) + 글로우 orb
  - 참조: `ruvnet-RuView/ui/observatory/js/vitals-oracle.js` (6.5KB)
- [ ] **Phase Constellation** — CSI 위상 별자리 시각화
  - 참조: `ruvnet-RuView/ui/observatory/js/phase-constellation.js` (5.8KB)
- [ ] **Presence Cartography** — 재실 히트맵 커버리지 맵
  - 참조: `ruvnet-RuView/ui/observatory/js/presence-cartography.js` (5.8KB)
- [ ] **Dashboard HUD 오버레이** — FPS, 레이턴시, 인원수, 감지 모드
  - 참조: `ruvnet-RuView/ui/components/dashboard-hud.js` (15KB)

#### 대시보드 추가 (HIGH)
- [ ] **SensingTab** — 3D Gaussian 뷰포트, RSSI 스파크라인, 분류 뱃지
  - 참조: `ruvnet-RuView/ui/components/SensingTab.js` (10KB)
  - React 컴포넌트로 변환, `/sensing` 라우트 추가
- [ ] **DashboardTab 강화** — 시스템 상태(CPU/Mem), 데이터소스, 컴포넌트 상태
  - 참조: `ruvnet-RuView/ui/components/DashboardTab.js` (14KB)

#### 대시보드 추가 (MEDIUM)
- [ ] **HardwareTab** — 안테나 배열 시각화, CSI 실시간 표시
  - 참조: `ruvnet-RuView/ui/components/HardwareTab.js` (5.5KB)
  - React 컴포넌트, `/hardware` 라우트
- [ ] **PoseDetectionCanvas** — 스켈레톤 렌더링, 트레일, 설정
  - 참조: `ruvnet-RuView/ui/components/PoseDetectionCanvas.js` (40KB)

#### Pose Fusion 전용 뷰 (HIGH)
- [ ] **Pose Fusion UI** — 비디오+CSI 이중 모달, 신뢰도 바
  - 참조: `ruvnet-RuView/ui/pose-fusion/` (17KB + 6 sub-modules)
  - 별도 `/pose-fusion` 라우트 또는 대시보드 섹션

#### 서비스 강화 (HIGH)
- [ ] **WebSocket heartbeat + exponential backoff**
  - 참조: `ruvnet-RuView/ui/services/websocket.service.js` (23KB)
  - useWebSocket.ts 개선: 30s heartbeat, [1,2,4,8,16,30s] backoff
- [ ] **Backend auto-detector**
  - 참조: `ruvnet-RuView/ui/utils/backend-detector.js` (3KB)

---

## Phase 3: 낙상 감지 고도화

- [ ] 3-1. 낙상 시나리오 데이터 수집 (50+ 낙상, 100+ 정상)
- [ ] 3-2. 특성 추출 (jerk, peak amplitude, duration, recovery)
- [ ] 3-3. 앙상블 ML (SVM + RF + GBDT)
- [ ] 3-4. CSI + 카메라 교차 검증
- [ ] 3-5. 알림 시스템 (토스트, 이메일/SMS)

---

## Phase 4: 카메라 CV 고도화 (develop 브랜치)

- [x] 4-1. YOLOv8-pose 스켈레톤 감지
- [x] 4-2. classify_pose (sitting/standing/walking/lying)
- [x] 4-3. 카메라+CSI 자세 융합
- [ ] 4-4. DeepSORT / ByteTrack 다중 객체 추적
- [ ] 4-5. 인원 re-ID (재식별)
- [ ] 4-6. 프라이버시 필터 (얼굴 블러)
- [ ] 4-7. 다중 카메라 스티칭

---

## Phase 5: 센서 융합 고도화

- [x] 5-1. 카메라+CSI 자세 융합 (_fuse_poses)
- [x] 5-2. POST /api/camera/detections + pose_update broadcast
- [ ] 5-3. Kalman 가중 시간 동기화
- [ ] 5-4. 신뢰도 기반 모달리티 전환 (어둠→CSI, 밝음→카메라)
- [ ] 5-5. mmWave 확장 (ESP32-C6 + MR60BHA2)

---

## Phase 6: Rust 포팅 (장기)

- [ ] 6-1. signal-adapter → Rust Axum (810x 성능)
- [ ] 6-2. wifi-densepose-signal crate 통합
- [ ] 6-3. wifi-densepose-vitals crate 통합
- [ ] 6-4. WASM 빌드 (브라우저 내 신호처리)
- [ ] 6-5. 1,000+ 테스트

---

## Phase 7: 배포/운영

- [ ] 7-1. Docker Compose (signal-adapter + camera + web)
- [ ] 7-2. README.md 작성
- [ ] 7-3. ADR 문서화 (주요 결정 10건+)
- [ ] 7-4. Prometheus + Grafana 모니터링
- [ ] 7-5. CI/CD GitHub Actions
- [ ] 7-6. Blue-Green 배포

---

## 추가 제안 (ruvnet 참조)

- [ ] A. Claude Flow V3 오케스트레이션 도입
- [ ] B. WASM 엣지 프로그래밍 (ADR-040)
- [ ] C. HRV(심박변이도) 분석 (SDNN, RMSSD, PNN50)
- [ ] D. Swarm Mesh 네트워킹 (ADR-057/066)
- [ ] E. 통과벽 감지 (Fresnel Zone, 최대 5m)
- [ ] F. LiveDemoTab (A/B 비교, 모델 관리, 학습) — 65KB

---

## 코드 검토 이력

| 날짜 | P1 | P2 | P3 | 문서 |
|------|-----|-----|-----|------|
| 2026-03-23 | 9/9 수정 | 19건 (10 수정) | 20건 | CODE_REVIEW_2026-03-23.md |

---

## ruvnet/RuView 참조 파일 색인

| 분류 | 파일 | Phase |
|------|------|-------|
| DSP | `firmware/.../edge_processing.c/h` | 1 |
| DSP | `examples/ruview_live.py` | 1 |
| DSP | `rust-port/.../wifi-densepose-signal/` | 6 |
| UI | `ui/components/body-model.js` (15KB) | 2 |
| UI | `ui/components/signal-viz.js` (19KB) | 2 |
| UI | `ui/components/gaussian-splats.js` (16KB) | 2 |
| UI | `ui/components/dashboard-hud.js` (15KB) | 2-11 |
| UI | `ui/components/SensingTab.js` (10KB) | 2-11 |
| UI | `ui/components/DashboardTab.js` (14KB) | 2-11 |
| UI | `ui/components/LiveDemoTab.js` (65KB) | F |
| UI | `ui/components/HardwareTab.js` (5.5KB) | 2-11 |
| UI | `ui/components/PoseDetectionCanvas.js` (40KB) | 2-11 |
| UI | `ui/observatory/js/vitals-oracle.js` (6.5KB) | 2-11 |
| UI | `ui/observatory/js/phase-constellation.js` (5.8KB) | 2-11 |
| UI | `ui/observatory/js/presence-cartography.js` (5.8KB) | 2-11 |
| UI | `ui/pose-fusion/` (17KB+subs) | 2-11 |
| 서비스 | `ui/services/websocket.service.js` (23KB) | 2-11 |
| 서비스 | `ui/utils/backend-detector.js` (3KB) | 2-11 |
| 융합 | `scripts/mmwave_fusion_bridge.py` | 5 |
| ADR | `docs/adr/` (67건) | 7 |
| 배포 | `docker/docker-compose.yml` | 7 |
