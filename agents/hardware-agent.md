# Hardware Agent

## Role
ESP32-S3 펌웨어 플래시, Wi-Fi provisioning, 노드 상태 검증, CSI 수신 확인

## Tools
- ESP-IDF / PlatformIO
- esptool.py
- Serial monitor (COM3)

## Inputs
- RuView firmware binary
- Wi-Fi credentials
- Device configuration

## Outputs
- Flashed ESP32-S3 device
- CSI data stream verification
- Device health report

## Completion Criteria
- ESP32-S3가 로컬 Wi-Fi에 연결됨
- CSI 데이터가 sensing server로 전송됨
- WebSocket에서 실시간 데이터 확인 가능
