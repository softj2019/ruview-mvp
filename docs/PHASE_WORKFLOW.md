# RuView 고도화 Phase Workflow

> 기준: ruvnet/RuView 분석 + 현재 구현 상태 + 사용자 요건
> 갱신: 2026-03-23

---

## Phase 0: 기반 안정화 (현재)

### 인프라
- [x] ESP32 4대 프로비저닝 (ARCHIVSOFT_2.4G, 10.0.0.217)
- [x] signal-adapter (FastAPI :8001) 구동
- [x] web-monitor (Vite :5280) 구동
- [x] camera-service (FastAPI :8002) 구동
- [x] 3D 관측소 Three.js 렌더링
- [x] WebSocket 실시간 데이터 스트리밍
- [ ] Docker 컨테이너화 (signal-adapter, camera-service)
- [ ] PM2 또는 systemd 서비스 등록 (자동 재시작)

### 노드 배치 검증
- [x] 노드 위치 격자 매핑 (A5, A2, H1, G4)
- [ ] 전원 뽑기 테스트로 물리 위치 ↔ node_id 검증
- [ ] RSSI 기반 위치 교차 확인
- [ ] 라우터(F5) 위치 반영

### 관측소 라이브 전환
- [x] auto-detect 타임아웃 10초
- [x] fetch/json 파싱 분리
- [x] SETTINGS_VERSION 갱신
- [ ] 안정적 라이브 전환 최종 확인

### 카메라
- [x] MSMF import-time 초기화 해결
- [x] YOLO 객체 감지 + MJPEG 오버레이
- [x] 디지털 줌 (1x-5x)
- [ ] 카메라 각도 조정 (사람 전체 보이도록)
- [ ] 카메라-평면도 4점 캘리브레이션 실측

---

## Phase 1: CSI 신호처리 고도화 (ruvnet/RuView 참조)

### 호흡/심박 추출 (firmware → server)
- [ ] Biquad IIR 밴드패스 필터 (호흡: 0.1-0.5Hz, 심박: 0.8-2.0Hz)
- [ ] 위상 언래핑 (2π 불연속 제거) — `edge_processing.c:134-140` 참조
- [ ] Zero-crossing BPM 추정 — `edge_processing.c:179-206` 참조
- [ ] Welford 온라인 통계 (mean, variance, z-score) — `edge_processing.c:146-165` 참조
- [ ] csi_processor.py에서 breathing_rate, heart_rate 실측값 반환 (현재 None)
- [ ] FFT 기반 스펙트럼 분석 추가 (scipy.signal.welch)

### 적응형 재실 감지
- [x] adaptive breathing baseline (30% 변화 감지)
- [ ] Welford z-score 기반 presence threshold (mean ± 3σ)
- [ ] 빈 방 캘리브레이션 자동화 (OTA 리부팅 스크립트)
- [ ] per-node presence confidence score

### 다중 인원 분리
- [ ] 서브캐리어 variance 클러스터링 (Dynamic Min-Cut 참조)
- [ ] per-person 위상 히스토리 분리
- [ ] 인원수 ↔ 서브캐리어 그룹 매핑
- [ ] ruvnet의 `ruvector-attn-mincut` 알고리즘 검토/적용

### 채널 호핑
- [ ] 다채널 CSI 수집 (ch1, ch6, ch11) — ADR-029 참조
- [ ] per-channel amplitude 스택킹
- [ ] TDM 슬롯 조정 (4노드 × 3채널)

---

## Phase 2: 시각화 고도화 (ruvnet/RuView UI 참조)

### 평면도 개선
- [x] 1001-1004호 렌더링 + 문 표시
- [x] 드래그드롭 노드 위치 조정
- [x] CSI 히트맵 (motion_energy 기반)
- [x] 호흡 감지 빨간 도트
- [x] n_persons 보라색 인디케이터
- [ ] per-room 존 분리 (4개 독립 존)
- [ ] 존 간 이동 감지 (boundary crossing)
- [ ] 커스텀 평면도 이미지 업로드
- [ ] 체류 시간 분석 (per-zone dwell time)

### 3D 관측소 개선
- [ ] `body-model.js` 참조 — DensePose 24 body parts 지원
- [ ] `signal-viz.js` 참조 — CSI 히트맵 + 위상 플롯 + 도플러 스펙트럼
- [ ] `gaussian-splats.js` 참조 — 신호 필드 Points 렌더링
- [ ] 피규어 자연스러운 이동 (waypoint pathfinding)
- [ ] 실시간 심박 애니메이션 (가슴 글로우 펄스)
- [ ] 포즈 추론 (CSI motion → standing/sitting/fallen 분류)
- [ ] 사무실 가구 배치 (책상, 의자 콜라이더)
- [ ] 시나리오별 조명 변경

### KPI/대시보드
- [x] presenceCount → zone store 정합
- [ ] 24시간 트렌드 차트 (occupancy 패턴)
- [ ] per-device 호흡/심박 스파크라인
- [ ] 이상 범위 알림 (HR <40 or >130)
- [ ] 토스트 알림 (낙상, 이상징후)

---

## Phase 3: 낙상 감지 고도화

- [ ] 다중 특성 추출: jerk (d³x/dt³), peak amplitude, duration, recovery slope
- [ ] 낙상 시그니처: 급격한 상승(50-200ms) + 느린 회복(2-5s)
- [ ] 앙상블 분류기 (SVM + RandomForest + GBDT) — WiFall 논문 참조
- [ ] 라벨링 데이터 수집 (자원봉사자 매트리스 낙상 테스트)
- [ ] CSI + 카메라 교차 검증 (camera_fall_candidate)
- [ ] 낙상 쿨다운 5초 + 3프레임 연속 감지 (현재 구현)
- [ ] 낙상 후 알림: 이메일/SMS/카카오톡

---

## Phase 4: 카메라 CV 고도화 (develop 브랜치)

- [x] YOLO 객체 감지 + bbox 오버레이
- [ ] YOLOv8-pose 통합 (스켈레톤 keypoints)
- [ ] DeepSORT / YOLO-NAS 다중 객체 추적 (MOT)
- [ ] 인원 re-ID (재식별, 의상 색상 히스토그램)
- [ ] 행동 분류 (앉기/서기/걷기)
- [ ] 프라이버시 필터 (얼굴 블러, 실루엣 모드)
- [ ] 카메라-WiFi 포즈 융합 (`pose-fusion.html` 참조)
- [ ] 다중 카메라 스티칭

---

## Phase 5: 센서 융합 고도화

### CSI + 카메라 후기 융합
- [x] POST /api/camera/detections → presenceCount 교차검증
- [ ] Kalman 가중 융합 (카메라 80% + CSI 20%) — mmwave_fusion_bridge.py 참조
- [ ] 시간 동기화 (timestamp 기반 매칭)
- [ ] 신뢰도 기반 모달리티 선택 (어둠→CSI, 밝음→카메라)

### mmWave 확장 (선택)
- [ ] ESP32-C6 + Seeed MR60BHA2 (60GHz FMCW) 추가
- [ ] ADR-063/064 fused vitals packet (48 bytes)
- [ ] 카메라 + CSI + mmWave 삼중 융합

---

## Phase 6: Rust 포팅 (장기)

- [ ] signal-adapter Python → Rust Axum 포팅 (810x 성능)
- [ ] ruvnet의 15 Rust crate 구조 참조
- [ ] wifi-densepose-signal 신호처리 모듈 통합
- [ ] wifi-densepose-vitals 바이탈 추출 통합
- [ ] WASM 빌드 (브라우저 내 신호처리)

---

## Phase 7: 배포/운영

- [ ] Docker Compose (signal-adapter + camera + web)
- [ ] Kubernetes 매니페스트 (HPA, resource limits)
- [ ] Prometheus + Grafana 모니터링
- [ ] Supabase 자동 백업
- [ ] SSL/TLS (ESP32 → adapter mTLS)
- [ ] Blue-Green 배포 전략

---

## ruvnet/RuView 참조 파일 색인

| 분류 | 파일 | 용도 |
|------|------|------|
| **신호처리** | `firmware/esp32-csi-node/main/edge_processing.c/h` | 듀얼코어 DSP, 위상 언래핑, Biquad, Welford |
| **신호처리** | `rust-port/.../wifi-densepose-signal/` | RuvSense 14모듈 (Hampel, Fresnel, BVP) |
| **신호처리** | `examples/ruview_live.py` | Python 참조 구현 (WelfordStats, HRV) |
| **UI** | `ui/components/body-model.js` | COCO 17 → 3D 스켈레톤 (6명, DensePose 24) |
| **UI** | `ui/components/signal-viz.js` | CSI 히트맵 + 위상 플롯 + 도플러 |
| **UI** | `ui/components/gaussian-splats.js` | 신호 필드 Points 렌더링 |
| **UI** | `ui/observatory.html` | 풀스크린 관측소 |
| **융합** | `scripts/mmwave_fusion_bridge.py` | Kalman 80/20 융합 |
| **아키텍처** | `docs/adr/ADR-029-multistatic.md` | 다채널 + 다노드 융합 전략 |
| **아키텍처** | `docs/adr/ADR-047-observatory.md` | Three.js 시각화 설계 |
| **아키텍처** | `docs/adr/ADR-018-binary-frame.md` | ESP32 프레임 포맷 |
| **설정** | `.claude-flow/config.yaml` | Claude Flow V3 오케스트레이션 |
| **설정** | `CLAUDE.md` | 프로젝트 규칙 + 크레이트 매핑 |
| **CI/CD** | `.github/workflows/ci.yml` | 테스트 + 보안 스캔 |
| **배포** | `docker/docker-compose.yml` | Rust sensing-server + Python WS |
