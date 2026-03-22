---
name: camera-cv-agent
description: USB 카메라 + YOLO 객체 감지 + 평면도 오버레이 담당 에이전트
---

# Camera CV Agent

## 담당 범위
- `services/camera-service/` 전체
- `apps/web-monitor/src/components/camera/` 컴포넌트
- 카메라-평면도 좌표 캘리브레이션

## 현재 상태
- camera_worker.py: MSMF 백엔드 — Windows CMD 포그라운드에서만 동작
- detector.py: YOLOv8n 구현 완료
- main.py: MJPEG 스트림 + WS detections + 캘리브레이션 API
- CameraFeed.tsx: 대시보드 컴포넌트 구현 완료

## 해결 필요 이슈
1. **MSMF 포그라운드 제약**: 백그라운드/nohup에서 카메라 프레임 캡처 불가
   - 해결 방안: ffmpeg 설치, DirectShow 디바이스명 사용, 또는 Windows Service로 실행
2. **카메라 시작 자동화**: 서비스 시작 시 worker 자동 실행
3. **캘리브레이션 UI**: 카메라 스냅샷 위에 4점 클릭으로 좌표 매핑

## 시작 방법
```cmd
cd d:\home\ruView\services\camera-service
set OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS=0
python camera_worker.py
```
별도 터미널: `python -m uvicorn main:app --host 0.0.0.0 --port 8002`

## signal-adapter 연동
- POST /api/camera/detections → CSI+카메라 후기 융합
- camera_person_count → presenceCount 교차 검증
