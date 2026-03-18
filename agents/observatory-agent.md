# Observatory Agent

## Role
RuView Observatory 연동, React-embedded 3D route, Tesla-like scene overlay

## Tools
- Three.js (via RuView)
- React Three Fiber (2차)
- postMessage bridge

## Inputs
- RuView Observatory URL
- WebSocket data stream
- Device/zone state

## Outputs
- 3D observatory view embedded in React
- State synchronization between 2D and 3D
- Full screen mode

## Completion Criteria
- RuView 3D 화면이 React 앱 내에서 표시됨
- 2D 선택 → 3D 하이라이트 동기화
- 감지 이벤트 → 3D 시각 효과 반영
