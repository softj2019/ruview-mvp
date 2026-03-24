# RuView Rust Port (Phase 6)

> Python signal-adapter → Rust Axum 포팅 (810x 성능 목표)

## Crate 구조

| Crate | 역할 | Python 대응 |
|-------|------|------------|
| `ruview-core` | CSI 타입, 프레임 파싱, Welford 통계 | csi_processor.py (데이터 구조) |
| `ruview-signal` | SOTA 신호처리 (Hampel, CSI Ratio, Fresnel, BVP, STFT) | csi_processor.py (알고리즘) |
| `ruview-server` | Axum HTTP/WS 서버, UDP 수신, 브로드캐스트 | main.py |

## 상태

- [ ] ruview-core: 타입 정의
- [ ] ruview-signal: 알고리즘 포팅
- [ ] ruview-server: 서버 구현
- [ ] 벤치마크: Python vs Rust 성능 비교
- [ ] WASM 빌드

## 참조
- ruvnet/RuView Rust crates: `d:/home/ruvnet-RuView/rust-port/wifi-densepose-rs/`
- 15 crates, 1,031+ tests, 810x speedup
