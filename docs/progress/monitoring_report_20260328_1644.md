# ruView 정기 모니터링 리포트
**시각**: 2026-03-28 16:44 KST
**서비스**: signal-adapter=hardware | camera=✅ | 노드=6/6 온라인

---

## 노드별 센싱 상태

| 노드 | 상태 | 존 | presence | n_persons | pose_conf | 호흡(bpm) | 심박(bpm) |
|------|------|----|---------:|----------:|----------:|----------:|----------:|
| node-5 | ✅ online | zone-1003 | 0.029 | 0 | 0.00 | 0.0 | 0.0 |
| node-1 | ✅ online | zone-1001 | 0.035 | 0 | 0.00 | 0.0 | 0.0 |
| node-3 | ✅ online | zone-1004 | 0.049 | 0 | 0.00 | 0.0 | 0.0 |
| node-2 | ✅ online | zone-1001 | 0.028 | 0 | 0.00 | 0.0 | 0.0 |
| node-6 | ✅ online | zone-1002 | 0.033 | 0 | 0.00 | 0.0 | 0.0 |
| node-4 | ✅ online | zone-1004 | 0.033 | 0 | 0.00 | 0.0 | 0.0 |

**재실 감지 신뢰도**: 0/6 노드 신뢰 (presence≥0.15)

---

## 캘리브레이션 / 학습 상태

- Welford 캘리브레이션: ✅ 완료
- 리포트: Learning Report #124
- 낙상 모델 로드: ✅
- 학습 샘플: **150건** / 목표 150건
  - 낙상 75건 | 정상 75건

---

## 감지된 문제 (6건)

- [LOW_PRESENCE] node-5 presence_score=0.029 (노이즈 수준)
- [LOW_PRESENCE] node-1 presence_score=0.035 (노이즈 수준)
- [LOW_PRESENCE] node-3 presence_score=0.049 (노이즈 수준)
- [LOW_PRESENCE] node-2 presence_score=0.028 (노이즈 수준)
- [LOW_PRESENCE] node-6 presence_score=0.033 (노이즈 수준)
- [LOW_PRESENCE] node-4 presence_score=0.033 (노이즈 수준)

---

## 미해결 개선 이슈 (GitHub)

- #10 [센싱] node-4 presence_score 반복 급등 (zone-1004)
- #7 [센싱] presence_score 전 노드 노이즈 수준 (0.02~0.17)
- #5 [센싱] node-6 오프라인 지속 — 물리 점검 필요

---

## 조치 내역 (2026-03-28)

| 항목 | 상태 | 비고 |
|------|------|------|
| node-6 전원/WiFi 확인 | ✅ 복구 | 16:44 온라인 확인 → #5 클로즈 |
| 낙상 시뮬레이션 데이터 수집 | ✅ 완료 | 150/150건 달성 (낙상 75, 정상 75) |
| AP 채널 고정 + 노드 높이 조정 | ⏳ 주말 예정 | 전 노드 LOW_PRESENCE 지속 |
| 재캘리브레이션 (empty-room) | ⏳ 현장 조치 후 | 노드 재조정 후 실행 |

---

## 권장 조치

1. **주말 중**: AP 채널 고정, 노드 높이 1.2~1.5m 재조정 — 저신뢰 노드 6개
2. **재캘리브레이션**: 노드 정리 후 `POST /api/calibration/empty-room`
