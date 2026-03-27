# Blue-Green Deployment — ruView

무중단(zero-downtime) 배포를 위한 Blue-Green 전략 구현입니다.

## 개요

| 슬롯 | api-gateway | signal-adapter |
|------|-------------|----------------|
| Blue (기본 활성) | :8000 | :8001 |
| Green (대기) | :8010 | :8011 |

배포 흐름:
1. 비활성 슬롯에 새 컨테이너 시작
2. `/health` 엔드포인트 헬스 체크 (최대 10회 재시도)
3. Nginx upstream 전환 (`nginx -s reload`)
4. 10초 드레인 후 이전 슬롯 종료
5. 헬스 체크 실패 시 자동 롤백

## 파일 구조

```
infra/blue-green/
├── deploy.sh     # 자동 블루-그린 배포 스크립트
├── nginx.conf    # Nginx upstream 설정
└── README.md     # 이 파일
```

## 사용법

### 1. 기본 배포 (비활성 슬롯으로 자동 전환)

```bash
cd infra/blue-green
chmod +x deploy.sh
./deploy.sh
```

출력 예시:
```
[DEPLOY] Current active slot: blue
[DEPLOY] Deploying to inactive slot: green
[DEPLOY] Starting green environment (api:8010, adapter:8011)...
[DEPLOY] Health-checking api-gateway[green] at http://localhost:8010/health ...
[DEPLOY] api-gateway[green] is healthy (attempt 1/10)
[DEPLOY] Switching Nginx upstream to green ...
[DEPLOY] Draining in-flight requests from blue (10s)...
[DEPLOY] Stopping blue environment...
[DEPLOY] Blue-green deployment complete.
  Active slot : green
  api-gateway : http://localhost:8010/health
  signal-adapter: http://localhost:8011/health
```

### 2. 특정 슬롯으로 배포

```bash
./deploy.sh blue    # blue 슬롯으로 배포
./deploy.sh green   # green 슬롯으로 배포
```

### 3. 수동 롤백

헬스 체크 실패 시 자동 롤백되지만, 수동 롤백도 가능합니다:

```bash
# nginx.conf에서 upstream 주석 수동 편집 후:
nginx -s reload

# 또는 특정 슬롯 강제 배포:
./deploy.sh blue
```

### 4. 현재 활성 슬롯 확인

```bash
# nginx.conf upstream 블록 확인
grep -A2 "upstream api_gateway" infra/blue-green/nginx.conf
```

## 사전 요구사항

- Docker + Docker Compose
- Nginx (로컬 설치 또는 Docker 컨테이너)
- `curl` (헬스 체크용)

## 환경 변수

`.env` 파일에서 다음 변수를 설정할 수 있습니다:

```env
# .env (프로젝트 루트)
API_GATEWAY_PORT=8000        # blue 기본값
SIGNAL_ADAPTER_PORT=8001     # blue 기본값
```

## CI/CD 통합

GitHub Actions에서 자동 배포:

```yaml
# .github/workflows/deploy.yml
- name: Blue-Green Deploy
  run: |
    chmod +x infra/blue-green/deploy.sh
    ./infra/blue-green/deploy.sh
```

## Nginx 수동 설치 (로컬 테스트)

```bash
# Ubuntu/Debian
sudo apt install nginx
sudo nginx -c "$(pwd)/infra/blue-green/nginx.conf"

# macOS (Homebrew)
brew install nginx
nginx -c "$(pwd)/infra/blue-green/nginx.conf"
```
