# GitHub Issue Drafts

2026-03-20 기준으로 아래 후속 이슈를 실제 GitHub에 등록했습니다.

## Registered Issues

- `#1` [signal-adapter: 라이브 이벤트와 디바이스/존 payload 타입 계약 정리](https://github.com/softj2019/ruview-mvp/issues/1)
- `#2` [observatory: 라이브 vitals 신뢰도를 실제 센서 신호와 연동](https://github.com/softj2019/ruview-mvp/issues/2)
- `#3` [observatory: 3D 인물 배치를 안정적인 라이브 매핑 기반으로 개선](https://github.com/softj2019/ruview-mvp/issues/3)

## Summary

### Issue #1

- 대상: `services/signal-adapter/main.py`, `apps/web-monitor/src/App.tsx`, `apps/web-monitor/src/stores/*`, `apps/web-monitor/public/observatory/js/main.js`
- 주제: WebSocket 메시지 타입과 payload shape 계약 정리
- 목적: React 대시보드와 observatory가 동일한 데이터 계약을 기준으로 동작하도록 정리

### Issue #2

- 대상: `apps/web-monitor/public/observatory/js/main.js`
- 주제: 라이브 vitals confidence를 실제 센서 상태와 연동
- 목적: stale/low-confidence vitals를 구분하고, confidence가 하드웨어 상태를 더 정확히 반영하도록 개선

### Issue #3

- 대상: `apps/web-monitor/public/observatory/js/main.js`
- 주제: 3D 인물 배치를 안정적인 라이브 매핑 기반으로 개선
- 목적: 인물 배치 흔들림을 줄이고 node/device/event와의 연결을 더 일관되게 만들기

## Commit Rule

앞으로 이 후속 작업을 커밋할 때는 관련 이슈 번호를 커밋 메시지에 함께 기록합니다.

예시:

- `fix: observatory vitals confidence 보정 (#2)`
- `refactor: ws payload 타입 계약 정리 (#1)`
- `feat: 3D 인물 매핑 안정화 (#3)`
