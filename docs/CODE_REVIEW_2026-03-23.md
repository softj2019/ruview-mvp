# 정밀 코드 검토 결과 (2026-03-23)

## 검토 범위
- signal-adapter: main.py, csi_processor.py, event_engine.py, ws_manager.py, supabase_client.py
- 프론트엔드: App.tsx, FloorView.tsx, CameraFeed.tsx, KpiCards.tsx, SignalChart.tsx, stores 3개, useWebSocket.ts
- 관측소: main.js, figure-pool.js, hud-controller.js
- ruvnet/RuView 비교: 알고리즘 포팅 정확성, 펌웨어, 문서

## P1 Critical (9건)

| # | 파일 | 이슈 | 상태 |
|---|------|------|------|
| 1 | main.py:595 | Semaphore TOCTOU 경쟁조건 | ✅ 수정 (카운터 방식) |
| 2 | csi_processor.py:65 | Welford variance count→count-1 | ✅ 수정 |
| 3 | main.py:303 | Baseline drift Welford 오염 | ✅ 수정 (threshold 직접) |
| 4 | csi_processor.py | WelfordStats.count 무한 증가 → 감도 저하 | ⬜ windowed Welford 필요 |
| 5 | main.py | 인증 없는 mutation API | ⬜ API key 추가 필요 |
| 6 | FloorView.tsx:111 | handlePointerUp stale devices closure | ⬜ getState() 사용 |
| 7 | main.js:1020 | 400개 MeshBasicMaterial 메모리 | ⬜ InstancedMesh 전환 |
| 8 | main.js:400 | keyboard listener 미해제 | ⬜ cleanup 추가 |
| 9 | App.tsx:37-50 | `as never` 타입 안전성 우회 | ⬜ discriminated union |

## P2 Important (19건)

### signal-adapter
- dead code: `_estimate_presence_from_csi()` 미사용
- Supabase insert try/except 없음
- `import time` 핫패스 내부
- event_engine: signal_weak 이벤트 폭주 (120/s)
- WS exception: WebSocketDisconnect만 catch
- `_per_sc_phase` 오프라인 디바이스 미정리
- `hasattr` dead code (이미 __init__에서 초기화)

### 프론트엔드
- signalStore: 배열 spread GC 압력 (300개)
- CameraFeed: zoom stale closure
- FloorView: heatmap 불필요 재계산 (모든 device 변경 시)
- useWebSocket: CONNECTING 상태 미처리
- CameraFeed: CalibrationPanel absolute 위치 문제

### 관측소
- _buildLiveFrame: device-level vitals 미사용 (lastVitals만)
- _csiAmplitudeHistory.shift() O(n) (ring buffer 미사용)
- HUD pulse: 프레임율 0.016 하드코딩

## ruvnet/RuView 비교

### 정확히 포팅됨 (10개)
위상 언래핑, Welford, Top-K, Butterworth, Zero-crossing, FFT Welch,
Hampel, Fresnel Zone, CSI 히트맵, 채널 호핑

### 단순화 (2개)
- CSI Ratio: 참조 서브캐리어 선택 방식 다름 (기능적 OK)
- 다중인원: union-find 상관 클러스터링 (ruvnet: Dynamic Min-Cut)

### 미포팅 (3개)
- CSI Spectrogram (STFT) — spectrogram.rs
- Body Velocity Profile (BVP) — bvp.rs
- Subcarrier sensitivity selection — subcarrier_selection.rs

### 문서 상태
- PHASE_WORKFLOW.md: 완료 항목 미체크
- README.md: 없음
- .env: 민감정보 포함 (push 안 됨)
