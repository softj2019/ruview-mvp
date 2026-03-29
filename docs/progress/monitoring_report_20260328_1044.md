# ruView 정기 모니터링 리포트
**시각**: 2026-03-28 10:44 KST
**Learning Report**: #113
**서비스**: signal-adapter=hardware | camera=✅ | 노드=5/6 온라인

---

## 노드별 센싱 상태

| 노드 | 상태 | 존 | presence | n_persons | pose_conf | 호흡(bpm) | 심박(bpm) |
|------|------|----|---------:|----------:|----------:|----------:|----------:|
| node-2 | ✅ online | zone-1001 | 0.026 | 0 | 0.00 | 0.0 | 0.0 |
| node-1 | ✅ online | zone-1001 | 0.029 | 0 | 0.00 | 0.0 | 87.1 |
| node-4 | ✅ online | zone-1004 | 0.030 | 0 | 0.00 | 27.5 | 70.6 |
| node-5 | ✅ online | zone-1003 | 0.026 | 0 | 0.00 | 21.7 | 91.1 |
| node-3 | ✅ online | zone-1004 | 0.027 | 0 | 0.00 | 0.0 | 77.7 |

**재실 감지 신뢰도**: 0/5 노드 신뢰 (presence≥0.15)

---

## 캘리브레이션 / 학습 상태

- Welford 캘리브레이션: ✅ 완료
- 리포트: Learning Report #113
- 낙상 모델 로드: ✅
- 학습 샘플: **150건** / 목표 150건
  - 낙상 75건 | 정상 75건

---

## 감지된 문제 (5건)

- [LOW_PRESENCE] node-2 presence_score=0.026 (노이즈 수준)
- [LOW_PRESENCE] node-1 presence_score=0.029 (노이즈 수준)
- [LOW_PRESENCE] node-4 presence_score=0.030 (노이즈 수준)
- [LOW_PRESENCE] node-5 presence_score=0.026 (노이즈 수준)
- [LOW_PRESENCE] node-3 presence_score=0.027 (노이즈 수준)

---

## 미해결 개선 이슈 (GitHub)

- #7 [센싱] presence_score 전 노드 노이즈 수준 (0.02~0.17)
- #5 [센싱] node-6 오프라인 지속 — 물리 점검 필요

---

## 조치 내역 (2026-03-28)

| 항목 | 상태 | 비고 |
|------|------|------|
| node-6 전원/WiFi 확인 | ⏳ 대기 | 물리 점검 필요 |
| 낙상 시뮬레이션 데이터 수집 | ✅ 완료 | training.csv 150건 확인 |
| AP 채널 고정 + 노드 높이 조정 | ⏳ 주말 예정 | |
| 재캘리브레이션 (empty-room) | ⏳ 현장 조치 후 | node-3 포함 필수 |
| GitHub #7 코멘트 업데이트 | ✅ 완료 | node-3 이상 기록 |

---

## 권장 조치

1. **즉시**: node-6 전원/WiFi 확인 및 재부팅
2. **금일 중**: 낙상 시뮬레이션 데이터 수집 (POST /api/fall/record)
3. **주말 중**: AP 채널 고정, 노드 높이 1.2~1.5m 재조정
4. **재캘리브레이션**: 노드 정리 후 `POST /api/calibration/empty-room`
