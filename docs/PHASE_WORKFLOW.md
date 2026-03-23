# RuView 고도화 Phase Workflow

> 기준: ruvnet/RuView 심층 분석 + 현재 구현 상태 + 사용자 요건 + 갭 분석
> 갱신: 2026-03-23
> 참조: `d:/home/ruvnet-RuView` (ruvnet/RuView.git)

---

## 현재 상태 요약

| 항목 | 상태 | 비고 |
|------|------|------|
| ESP32 4대 | ✅ 온라인 | N1(-73), N2(-77), N3(-59), N4(-61) |
| presenceCount | ⚠️ 1명 | 실제 인원과 불일치 |
| 호흡 감지 | ⚠️ 가짜 양성 | 공실에서도 16-28 BPM |
| 심박 감지 | ❌ None | csi_processor.py placeholder |
| n_persons (vitals) | ⚠️ 0 | 캘리브레이션 문제 |
| 카메라 YOLO | ✅ 동작 | 30fps, 0.5 det_fps |
| 관측소 라이브 | ⚠️ 불안정 | health 응답 ~2초 |
| 노드 위치 | ⚠️ 미검증 | 물리 위치 ↔ node_id 미확인 |

---

## Phase 0: 기반 안정화 ⬅️ 현재 진행 중

### 0-1. 노드 물리 위치 검증 (⚡ 즉시)
- [ ] A5 위치 보드 전원 분리 → 어떤 node_id가 offline 되는지 확인
- [ ] A2 위치 보드 전원 분리 → 확인
- [ ] H1 위치 보드 전원 분리 → 확인
- [ ] G4 위치 보드 전원 분리 → 확인
- [ ] 검증 결과로 DEVICE_POSITIONS 최종 수정
- [ ] 검증 결과 메모리 저장

### 0-2. 빈 방 캘리브레이션 (⚡ 퇴근 후)
- [x] OTA 리부팅 스크립트 (`esp32/reboot_nodes.py`)
- [ ] 사무실 비었을 때 4대 동시 OTA 리부팅
- [ ] 60초 캘리브레이션 완료 확인
- [ ] n_persons > 0 정상 보고 확인
- [ ] 서버 adaptive breathing baseline 리셋 확인

### 0-3. 관측소 안정화
- [x] fetch 타임아웃 10초
- [x] fetch/json 분리
- [x] SETTINGS_VERSION 7
- [ ] signal-adapter health 응답 속도 개선 (현재 ~2초 → 목표 <500ms)
  - [ ] CSI 프레임 처리 병목 프로파일링
  - [ ] broadcast 빈도 throttling (매 프레임 → 초당 5회)
- [ ] 관측소 라이브 전환 최종 확인 (3회 연속 성공)

### 0-4. 서비스 자동화
- [ ] signal-adapter: nohup 시작 스크립트 작성
- [ ] camera-service: nohup 시작 스크립트 작성
- [ ] web-monitor: vite 시작 스크립트 작성
- [ ] 통합 `start_all.sh` 스크립트
- [ ] Windows 시작프로그램 또는 서비스 등록

### 0-5. 카메라 실측 캘리브레이션
- [x] MSMF import-time 초기화
- [x] YOLO 객체 감지 + 오버레이
- [x] 디지털 줌 (1x-5x)
- [ ] 카메라 각도 조정 (사람 상반신 + 하반신 모두 보이게)
- [ ] 4점 캘리브레이션 실측 (카메라 영상 좌표 ↔ 평면도 좌표)
- [ ] 캘리브레이션 결과 저장 (calibration.json)
- [ ] 해상도 640x480 → 1280x720 업그레이드

---

## Phase 1: CSI 신호처리 고도화 (예상 2주)

> 참조: `ruvnet-RuView/firmware/esp32-csi-node/main/edge_processing.c`
> 참조: `ruvnet-RuView/examples/ruview_live.py`

### 1-1. 서버 측 호흡/심박 추출 (csi_processor.py 개선) ✅ 완료

- [x] **위상 추출**: CSI I/Q → `atan2(Q, I)` per-subcarrier phase
- [x] **위상 언래핑**: 2π 불연속 제거
- [x] **Welford 온라인 통계**: per-subcarrier variance tracking
- [x] **Top-K 서브캐리어 선택**: 8개 최고 variance 서브캐리어
- [x] **Butterworth IIR 밴드패스**: 호흡 0.1-0.5Hz, 심박 0.8-2.0Hz
- [x] **Zero-crossing BPM 추정**
- [x] **FFT 스펙트럼 분석**: `scipy.signal.welch()`
- [x] 결과 검수: 호흡 10-25 BPM, 심박 56-90 BPM 실측

### 1-1b. SOTA 신호처리 알고리즘 (ruvnet 참조) — 진행 중

- [ ] **Hampel 필터**: 슬라이딩 윈도우 MAD 아웃라이어 제거 — `hampel.rs`
- [ ] **CSI Ratio**: 켤레 곱셈으로 위상 오프셋 제거 — `csi_ratio.rs` (SpotFi 2015)
- [ ] **Fresnel Zone 모델**: TX-RX 기하학 기반 호흡 신뢰도 — `fresnel.rs` (FarSense 2019)
- [ ] **CSI Spectrogram**: STFT 시간-주파수 분석 — `spectrogram.rs`
- [ ] **BVP (Body Velocity Profile)**: 신체 속도 프로파일 — `bvp.rs` (Widar 3.0)
- [ ] **서브캐리어 감도 선택**: variance ratio 기반 — `subcarrier_selection.rs`

### 1-2. 적응형 재실 감지 개선

**현재**: breathing baseline 30% 변화 → 가짜 양성 있음
**목표**: Welford z-score 기반 정확한 감지

- [ ] **per-subcarrier Welford z-score**: 캘리브레이션 후 z > 3 = 존재 감지
  - 참조: `edge_processing.c` adaptive calibration (1200 frames)
- [ ] **per-node confidence score**: 0.0-1.0 범위 확신도
  - z-score 기반 시그모이드 변환
- [ ] **빈 방 자동 캘리브레이션**: OTA 리부팅 + 60초 baseline
  - 크론 작업: 새벽 3시 자동 실행
- [ ] **다중 신호 융합**: amplitude + phase + RSSI 변화 종합
- [ ] 공실 테스트: 1시간 동안 false positive 0건 목표

### 1-3. 다중 인원 분리

**현재**: `n_persons = s_top_k_count / 2` (고정값)
**목표**: 실제 인원수 추정

- [ ] **서브캐리어 상관 행렬**: per-subcarrier phase correlation
  - 높은 상관 = 같은 사람의 영향
- [ ] **클러스터링**: K-means 또는 spectral clustering
  - 참조: `ruvector-attn-mincut` (Dynamic Min-Cut)
- [ ] **per-person 위상 히스토리**: 클러스터별 독립 BPM 추출
- [ ] **검증**: 1명, 2명, 3명 시나리오에서 정확도 측정

### 1-4. 채널 호핑 (펌웨어 수정 필요)

**현재**: 채널 6 고정
**목표**: 3채널 (1, 6, 11) 호핑으로 3배 대역폭

- [ ] 펌웨어 `csi_collector.c` 수정: 채널 호핑 활성화
  - 참조: `ruvnet-RuView/firmware/.../csi_collector.c` channel-hop 코드
- [ ] dwell time 설정 (50ms per channel)
- [ ] signal-adapter에서 per-channel CSI 분리 수신
- [ ] per-channel amplitude 스택킹으로 분해능 향상
- [ ] OTA 배포 (4대)

---

## Phase 2: 시각화 고도화 (예상 2주)

> 참조: `ruvnet-RuView/ui/components/`

### 2-1. 평면도 다중 존 지원

**현재**: 단일 zone-main
**목표**: 1001-1004호 독립 존

- [ ] zone 정의: 4개 room polygon → 4개 독립 존
- [ ] per-zone presenceCount 집계
- [ ] per-zone 히트맵 (존별 색상 구분)
- [ ] **존 간 이동 감지**: 노드 전환 패턴 → boundary crossing event
- [ ] **체류 시간**: per-zone 타이머 + 누적 통계
- [ ] 존 상태 API: `GET /api/zones` → 4개 존 반환

### 2-2. 3D 관측소 — ruvnet UI 컴포넌트 통합

- [ ] **body-model.js 통합**:
  - DensePose 24 body parts (현재 COCO 17만 지원)
  - confidence 기반 색상 (blue→cyan→green)
  - 최대 6명 동시 렌더링
  - 참조: `ruvnet-RuView/ui/components/body-model.js`

- [ ] **signal-viz.js 통합**:
  - CSI amplitude 히트맵 (30×40 grid)
  - Phase 플롯 (서브캐리어 × 위상)
  - Doppler 스펙트럼 (16바 동적 높이)
  - Motion indicator (동심원 펄스)
  - 참조: `ruvnet-RuView/ui/components/signal-viz.js`

- [ ] **gaussian-splats.js 통합**:
  - 신호 필드 Points 렌더링 (20×20 floor)
  - body disruption blob (64 particles)
  - 셰이더 기반 (custom vertex/fragment)
  - 참조: `ruvnet-RuView/ui/components/gaussian-splats.js`

- [ ] **피규어 자연스러운 이동**:
  - waypoint 기반 pathfinding
  - social distance 모델링 (0.6-1.2m)
  - 목적지 랜덤 선택 + 경로 탐색

- [ ] **실시간 바이탈 애니메이션**:
  - 심박: 가슴 글로우 펄스 (HR BPM 동기화)
  - 호흡: 복부 깊이 변화
  - SpO2: 색상 변화 (저하 시 파란색)

### 2-3. KPI 대시보드 강화

- [ ] 24시간 occupancy 트렌드 차트 (Recharts area chart)
- [ ] per-device 호흡/심박 스파크라인 (mini line chart)
- [ ] 이상 범위 시각 경고 (HR <40 or >130 = 빨간 테두리)
- [ ] 토스트 알림 (낙상, 이상징후, 노드 offline)
- [ ] CSV 내보내기 버튼

---

## Phase 3: 낙상 감지 고도화 (예상 3주)

> 참조: WiFall 논문 (Tan et al. 2016)
> 참조: `ruvnet-RuView/firmware/.../edge_processing.c` fall detection

### 3-1. 데이터 수집
- [ ] 낙상 시나리오 정의 (전방, 후방, 측면, 무릎 꺾임)
- [ ] 자원봉사자 + 매트리스 환경에서 50+ 낙상 녹화
- [ ] CSI raw 데이터 + 카메라 영상 동기 저장
- [ ] 정상 활동 (앉기, 일어서기, 걷기) 100+ 녹화

### 3-2. 특성 추출
- [ ] jerk (d³x/dt³) — 가속도의 변화율
- [ ] peak amplitude — 낙상 시 최대 진폭
- [ ] duration — 충격 지속 시간 (50-200ms)
- [ ] recovery slope — 낙상 후 신호 회복 기울기
- [ ] bi-modal signature — 급격한 상승 + 느린 회복

### 3-3. ML 모델
- [ ] 앙상블 분류기: SVM(RBF) + RandomForest + GBDT
- [ ] Cross-validation (5-fold)
- [ ] Precision/Recall 95%+ 목표
- [ ] 모델 직렬화 + 서버 배포

### 3-4. 알림 시스템
- [ ] 낙상 이벤트 → WebSocket broadcast
- [ ] 토스트 알림 + 사운드
- [ ] 이메일/SMS/카카오톡 연동 (선택)
- [ ] CSI + 카메라 교차 검증 (camera_fall_candidate)

---

## Phase 4: 카메라 CV 고도화 (develop 브랜치, 예상 2주)

### 4-1. 스켈레톤 감지
- [ ] YOLOv8-pose 모델 통합 (17 keypoints)
- [ ] 카메라 프레임 위에 스켈레톤 오버레이
- [ ] 자세 분류 (앉기/서기/걷기) from keypoints

### 4-2. 다중 객체 추적
- [ ] DeepSORT 또는 ByteTrack 통합
- [ ] 고유 person ID 할당 + 추적
- [ ] 궤적 smoothing (Kalman filter)
- [ ] re-ID: 프레임 이탈 후 재등장 매칭

### 4-3. 프라이버시
- [ ] 얼굴 블러 필터
- [ ] 실루엣 모드 (사람 형태만 표시)
- [ ] 원본 프레임 비저장 정책

### 4-4. WiFi-카메라 포즈 융합
- [ ] COCO keypoints (카메라) + CSI pose (WiFi) 융합
- [ ] 참조: `ruvnet-RuView/ui/pose-fusion.html`
- [ ] 신뢰도 가중 블렌딩

---

## Phase 5: 센서 융합 고도화 (예상 2주)

### 5-1. Kalman 가중 융합
- [ ] CSI 20% + 카메라 80% 가중 평균 (재실 인원)
- [ ] 참조: `ruvnet-RuView/scripts/mmwave_fusion_bridge.py`
- [ ] 시간 동기화 (timestamp ±500ms 매칭)
- [ ] confidence-based 모달리티 전환
  - 어두움 → CSI 100%
  - 밝음 → 카메라 80% + CSI 20%

### 5-2. 교차 검증
- [ ] 카메라 인원수 ≠ CSI 인원수 → 경고 이벤트
- [ ] 불일치 시 어느 쪽이 맞는지 히스토리 기반 판단
- [ ] 융합 신뢰도 점수 (0.0-1.0) API 노출

### 5-3. mmWave 확장 (선택적)
- [ ] ESP32-C6 + Seeed MR60BHA2 하드웨어 추가
- [ ] 48-byte fused vitals packet (ADR-063)
- [ ] 삼중 융합: WiFi CSI + 카메라 + 60GHz mmWave

---

## Phase 6: Rust 포팅 (장기, 예상 4주)

- [ ] signal-adapter → Rust Axum (810x 성능 목표)
- [ ] `wifi-densepose-signal` crate 구조 차용
- [ ] `wifi-densepose-vitals` crate 통합
- [ ] `wifi-densepose-sensing-server` 참조 아키텍처
- [ ] WASM 빌드 (브라우저 내 신호처리)
- [ ] 1,000+ 테스트 커버리지

---

## Phase 7: 배포/운영 (예상 2주)

- [ ] Docker Compose (signal-adapter + camera + web)
- [ ] docker/Dockerfile.signal-adapter 작성
- [ ] docker/Dockerfile.camera-service 작성
- [ ] Kubernetes 매니페스트 (HPA, limits)
- [ ] Prometheus + Grafana 모니터링
- [ ] Supabase 자동 백업 (일 1회)
- [ ] SSL/TLS (ESP32 → adapter mTLS)
- [ ] Blue-Green 배포 전략
- [ ] CI/CD: GitHub Actions (ruvnet 참조)

---

## 추가 제안: ruvnet/RuView에서 발견된 고도화 방안

### A. Claude Flow V3 오케스트레이션 도입
- [ ] `.claude-flow/config.yaml` 설정 (hierarchical-mesh, max 15 agents)
- [ ] 에이전트 팀 구성: coder, reviewer, tester, planner
- [ ] 패턴 학습: ReasoningBank + HNSW 벡터 검색
- [ ] 효과: 개발 속도 향상, 반복 실수 방지

### B. WASM 엣지 프로그래밍 (ADR-040)
- [ ] ESP32에서 WASM 모듈 실행 (커스텀 이상감지)
- [ ] 제스처 인식 DTW 템플릿
- [ ] 서버 없이 엣지에서 실시간 분석

### C. Gaussian Splat 신호 필드
- [ ] 3D 공간에 CSI 에너지를 splat 렌더링
- [ ] 사람 위치에서 신호 왜곡 시각화
- [ ] ruvnet 셰이더 코드 재활용

### D. HRV(심박변이도) 분석
- [ ] SDNN, RMSSD, PNN50, LF/HF 비율
- [ ] 참조: `ruvnet-RuView/examples/ruview_live.py` HRVAnalyzer
- [ ] 스트레스 레벨 추정 (LF/HF > 2.0 = 높은 스트레스)

### E. Swarm Mesh 네트워킹 (ADR-057)
- [ ] 다수 사무실/층 간 ESP32 메시 연결
- [ ] Raft 합의 + CRDT 충돌 해결
- [ ] 확장: 건물 전체 모니터링

### F. 통과벽 감지 (Fresnel Zone)
- [ ] 벽 너머 존재 감지 (최대 5m)
- [ ] 참조: FarSense (MobiCom 2019)
- [ ] Fresnel zone 모델링 + SVD room eigenstructure

---

## ruvnet/RuView 참조 파일 색인

| 분류 | 파일 경로 | 용도 | Phase |
|------|----------|------|-------|
| **DSP** | `firmware/.../edge_processing.c/h` | Biquad, Welford, 위상언래핑, 낙상 | 1 |
| **DSP** | `examples/ruview_live.py` | Python WelfordStats, HRV, 이상감지 | 1 |
| **DSP** | `rust-port/.../wifi-densepose-signal/` | RuvSense 14모듈 | 6 |
| **UI** | `ui/components/body-model.js` | 3D 스켈레톤 (6명, DensePose 24) | 2 |
| **UI** | `ui/components/signal-viz.js` | CSI 히트맵 + 위상 + 도플러 | 2 |
| **UI** | `ui/components/gaussian-splats.js` | 신호 필드 Points 셰이더 | 2,A |
| **UI** | `ui/observatory.html` + `ui/observatory/js/` | 풀스크린 관측소 | 2 |
| **융합** | `scripts/mmwave_fusion_bridge.py` | Kalman 80/20 융합 | 5 |
| **융합** | `ui/pose-fusion.html` | 카메라+WiFi 포즈 융합 | 4 |
| **ADR** | `docs/adr/ADR-018-*.md` | ESP32 바이너리 프레임 포맷 | 1 |
| **ADR** | `docs/adr/ADR-029-*.md` | 다채널 멀티스태틱 센싱 | 1 |
| **ADR** | `docs/adr/ADR-039-*.md` | 듀얼코어 엣지 인텔리전스 | 1 |
| **ADR** | `docs/adr/ADR-047-*.md` | Three.js 관측소 설계 | 2 |
| **ADR** | `docs/adr/ADR-063/064-*.md` | mmWave 융합 | 5 |
| **설정** | `.claude-flow/config.yaml` | Claude Flow V3 | A |
| **설정** | `CLAUDE.md` | 프로젝트 규칙 | 0 |
| **배포** | `docker/docker-compose.yml` | Rust+Python 컨테이너 | 7 |
| **CI/CD** | `.github/workflows/ci.yml` | 테스트+보안 파이프라인 | 7 |
