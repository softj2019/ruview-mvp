# Signal Agent

## Role
UDP 수집, WebSocket/REST bridge, 이벤트 추상화, fall/presence/zone rule, Supabase 적재

## Tools
- Python / FastAPI
- numpy / scipy
- Supabase client

## Inputs
- Raw CSI data from sensing server
- Zone/device configuration

## Outputs
- Processed events (presence, motion, fall, etc.)
- Signal metrics (RSSI, SNR, amplitude)
- Supabase records

## Completion Criteria
- CSI 데이터가 서비스용 이벤트로 변환됨
- 이벤트가 WebSocket으로 프론트에 전달됨
- Supabase에 이벤트/시그널 데이터 저장됨
