# RuView Q1 MVP 전체 실행 프롬프트

> **대상 모델**: Claude Code Opus 4.6 (1M context)
> **프로젝트**: RuView - 오픈소스 기반 CSI 재실/낙상 감지 서비스 MVP
> **작성일**: 2026-03-18
> **예상 실행 시간**: 단계별 순차 실행, 전체 2-4시간

---

## 개요

이 문서는 Claude Code 에이전트가 **한 번의 세션**에서 RuView MVP 전체 인프라를 구축하기 위한 초장문 실행 프롬프트이다. 저장소 생성부터 Cloudflare 배포, Supabase 스키마, React 관제 UI, Python Signal Adapter, Docker 통합, CI/CD까지 모두 포함한다.

### 전제 조건

- Windows 11 환경, bash 셸 사용
- GitHub CLI (`gh`) 설치 완료
- Node.js 18+ 및 pnpm 설치 완료
- Python 3.11+ 및 pip 설치 완료
- Docker Desktop 설치 완료
- Cloudflare CLI (`wrangler`, `cloudflared`) 설치 완료
- ESP32-S3 보드가 COM3 (CP2102)에 연결됨
- `.env` 파일에 `GITHUB_TOKEN` 저장됨
- 작업 디렉토리: `D:/home/ruView`

### 환경변수 참조 규칙

모든 시크릿과 환경변수는 프로젝트 루트의 `.env` 파일에서 관리한다. 절대로 코드에 하드코딩하지 않는다.

```
GITHUB_TOKEN=ghp_xxxxxxxxxxxx
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_ANON_KEY=eyJhbGci...
SUPABASE_SERVICE_ROLE_KEY=eyJhbGci...
CLOUDFLARE_ACCOUNT_ID=xxxxxxxxxxxx
CLOUDFLARE_API_TOKEN=xxxxxxxxxxxx
CLOUDFLARE_TUNNEL_TOKEN=xxxxxxxxxxxx
VITE_SUPABASE_URL=${SUPABASE_URL}
VITE_SUPABASE_ANON_KEY=${SUPABASE_ANON_KEY}
VITE_API_WS_URL=wss://api.dev.example.com/ws
```

---

## Phase 0: 사전 검증

> **완료 기준**: 모든 CLI 도구가 정상 동작하고, 환경변수가 로드 가능한 상태

### 단계 0.1 - 도구 버전 확인

**도구**: `Bash`

```bash
echo "=== 환경 검증 시작 ==="
echo "--- Node.js ---" && node --version
echo "--- pnpm ---" && pnpm --version
echo "--- Python ---" && python --version
echo "--- pip ---" && pip --version
echo "--- Docker ---" && docker --version
echo "--- GitHub CLI ---" && gh --version
echo "--- Git ---" && git --version
echo "=== 환경 검증 완료 ==="
```

실패하는 도구가 있으면 즉시 중단하고 사용자에게 설치를 요청한다.

### 단계 0.2 - .env 파일 확인

**도구**: `Bash`

```bash
if [ -f "D:/home/ruView/.env" ]; then
    echo ".env 파일 존재 확인"
    # GITHUB_TOKEN 존재 여부만 확인 (값은 출력하지 않음)
    if grep -q "GITHUB_TOKEN=" "D:/home/ruView/.env"; then
        echo "GITHUB_TOKEN 설정됨"
    else
        echo "ERROR: GITHUB_TOKEN이 .env에 없습니다"
    fi
else
    echo "ERROR: .env 파일이 없습니다. 프로젝트 루트에 .env를 생성해주세요."
fi
```

### 단계 0.3 - GitHub 인증 확인

**도구**: `Bash`

```bash
source "D:/home/ruView/.env" 2>/dev/null
export GITHUB_TOKEN
gh auth status
```

---

## Phase 1: 저장소 Bootstrap

> **완료 기준**: GitHub 원격 저장소가 생성되고, 브랜치 전략/보호 규칙/라벨/마일스톤/템플릿이 모두 설정됨

### 단계 1.1 - Git 저장소 초기화

**도구**: `Bash`

```bash
cd "D:/home/ruView"
git init
git checkout -b main
```

### 단계 1.2 - .gitignore 작성

**도구**: `Write`

파일 경로: `D:/home/ruView/.gitignore`

```gitignore
# Dependencies
node_modules/
__pycache__/
*.pyc
.venv/
venv/

# Build outputs
dist/
build/
*.egg-info/

# Environment
.env
.env.local
.env.*.local

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Docker
docker-compose.override.yml

# Cloudflare
.wrangler/

# ESP32
.pio/

# Logs
*.log
logs/

# Coverage
coverage/
htmlcov/
.coverage

# Temporary
tmp/
temp/
```

### 단계 1.3 - GitHub 원격 저장소 생성

**도구**: `Bash`

```bash
source "D:/home/ruView/.env"
export GITHUB_TOKEN

cd "D:/home/ruView"
gh repo create ruview-mvp \
  --public \
  --description "RuView - Open-source CSI-based presence/fall detection service MVP" \
  --homepage "https://ruview.dev" \
  --source . \
  --remote origin \
  --push
```

### 단계 1.4 - 브랜치 전략 설정

**도구**: `Bash`

```bash
cd "D:/home/ruView"

# develop 브랜치 생성
git checkout -b develop
git push -u origin develop

# feature 브랜치 네이밍 규칙 문서는 CONTRIBUTING.md에서 관리
# 브랜치 전략:
#   main     - 프로덕션 릴리즈
#   develop  - 통합 개발
#   feat/*   - 기능 개발
#   fix/*    - 버그 수정
#   infra/*  - 인프라 변경
#   docs/*   - 문서 변경

git checkout main
```

### 단계 1.5 - 브랜치 보호 규칙 설정

**도구**: `Bash`

```bash
source "D:/home/ruView/.env"
export GITHUB_TOKEN
REPO="ruview-mvp"
OWNER=$(gh api user --jq '.login')

# main 브랜치 보호
gh api repos/$OWNER/$REPO/branches/main/protection \
  --method PUT \
  --input - <<'EOF'
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["lint", "test", "build"]
  },
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "required_approving_review_count": 1,
    "dismiss_stale_reviews": true
  },
  "restrictions": null
}
EOF

# develop 브랜치 보호
gh api repos/$OWNER/$REPO/branches/develop/protection \
  --method PUT \
  --input - <<'EOF'
{
  "required_status_checks": {
    "strict": false,
    "contexts": ["lint"]
  },
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "required_approving_review_count": 1
  },
  "restrictions": null
}
EOF
```

### 단계 1.6 - 라벨 생성

**도구**: `Bash`

```bash
source "D:/home/ruView/.env"
export GITHUB_TOKEN
REPO="ruview-mvp"
OWNER=$(gh api user --jq '.login')

declare -A LABELS=(
  ["agent:hardware"]="0E8A16:Hardware Agent 관련"
  ["agent:signal"]="1D76DB:Signal Agent 관련"
  ["agent:frontend"]="5319E7:Frontend Agent 관련"
  ["agent:observatory"]="D93F0B:Observatory Agent 관련"
  ["agent:devops"]="006B75:DevOps Agent 관련"
  ["agent:qa"]="BFD4F2:QA Agent 관련"
  ["priority:critical"]="B60205:긴급"
  ["priority:high"]="D93F0B:높음"
  ["priority:medium"]="FBCA04:보통"
  ["priority:low"]="0E8A16:낮음"
  ["type:feature"]="A2EEEF:새 기능"
  ["type:bugfix"]="D73A4A:버그 수정"
  ["type:infra"]="C5DEF5:인프라"
  ["type:docs"]="0075CA:문서"
  ["type:refactor"]="E4E669:리팩토링"
  ["status:in-progress"]="EDEDED:진행 중"
  ["status:review"]="FBCA04:리뷰 대기"
  ["status:blocked"]="B60205:블로킹"
  ["phase:q1-mvp"]="6F42C1:Q1 MVP 스코프"
)

for label in "${!LABELS[@]}"; do
  IFS=':' read -r color desc <<< "${LABELS[$label]}"
  gh label create "$label" \
    --repo "$OWNER/$REPO" \
    --color "$color" \
    --description "$desc" \
    --force 2>/dev/null || echo "라벨 생성/갱신: $label"
done
```

### 단계 1.7 - 마일스톤 생성

**도구**: `Bash`

```bash
source "D:/home/ruView/.env"
export GITHUB_TOKEN
REPO="ruview-mvp"
OWNER=$(gh api user --jq '.login')

gh api repos/$OWNER/$REPO/milestones --method POST \
  --input - <<'EOF'
{
  "title": "Q1 MVP - Core Infrastructure",
  "description": "모노레포 구조, CI/CD, Cloudflare, Supabase, 기본 관제 UI",
  "due_on": "2026-03-31T23:59:59Z"
}
EOF

gh api repos/$OWNER/$REPO/milestones --method POST \
  --input - <<'EOF'
{
  "title": "Q1 MVP - Signal Pipeline",
  "description": "ESP32 CSI 수집 → Signal Adapter → Supabase 적재 → 실시간 관제",
  "due_on": "2026-04-15T23:59:59Z"
}
EOF

gh api repos/$OWNER/$REPO/milestones --method POST \
  --input - <<'EOF'
{
  "title": "Q1 MVP - Observatory Integration",
  "description": "RuView Three.js Observatory 하이브리드 UI 통합",
  "due_on": "2026-04-30T23:59:59Z"
}
EOF
```

### 단계 1.8 - Issue 템플릿 생성

**도구**: `Write`

파일 경로: `D:/home/ruView/.github/ISSUE_TEMPLATE/feature_request.yml`

```yaml
name: Feature Request
description: 새로운 기능을 제안합니다
title: "[feat]: "
labels: ["type:feature"]
body:
  - type: dropdown
    id: agent
    attributes:
      label: 담당 에이전트
      options:
        - Hardware
        - Signal
        - Frontend
        - Observatory
        - DevOps
        - QA
    validations:
      required: true
  - type: textarea
    id: description
    attributes:
      label: 기능 설명
      description: 구현하려는 기능을 상세히 설명해주세요
    validations:
      required: true
  - type: textarea
    id: acceptance
    attributes:
      label: 완료 기준
      description: 이 기능이 완료되었다고 판단할 수 있는 기준
    validations:
      required: true
  - type: textarea
    id: context
    attributes:
      label: 추가 맥락
      description: 관련 스크린샷, 다이어그램, 참고 링크 등
```

**도구**: `Write`

파일 경로: `D:/home/ruView/.github/ISSUE_TEMPLATE/bug_report.yml`

```yaml
name: Bug Report
description: 버그를 보고합니다
title: "[bug]: "
labels: ["type:bugfix"]
body:
  - type: dropdown
    id: agent
    attributes:
      label: 관련 에이전트
      options:
        - Hardware
        - Signal
        - Frontend
        - Observatory
        - DevOps
        - QA
    validations:
      required: true
  - type: textarea
    id: description
    attributes:
      label: 버그 설명
      description: 발생한 문제를 상세히 설명해주세요
    validations:
      required: true
  - type: textarea
    id: reproduce
    attributes:
      label: 재현 방법
      description: 단계별로 재현 방법을 기술해주세요
    validations:
      required: true
  - type: textarea
    id: expected
    attributes:
      label: 기대 동작
    validations:
      required: true
  - type: textarea
    id: environment
    attributes:
      label: 환경 정보
      description: OS, 브라우저, Node 버전 등
```

### 단계 1.9 - PR 템플릿 생성

**도구**: `Write`

파일 경로: `D:/home/ruView/.github/pull_request_template.md`

```markdown
## 변경 사항
<!-- 이 PR에서 변경된 내용을 요약해주세요 -->

## 관련 이슈
<!-- closes #이슈번호 -->

## 담당 에이전트
<!-- Hardware / Signal / Frontend / Observatory / DevOps / QA -->

## 체크리스트
- [ ] 코드 린트 통과
- [ ] 테스트 작성/통과
- [ ] 문서 업데이트 (필요시)
- [ ] 스크린샷 첨부 (UI 변경시)

## 테스트 방법
<!-- 리뷰어가 이 PR을 테스트할 수 있는 방법 -->
```

### 단계 1.10 - CODEOWNERS 생성

**도구**: `Write`

파일 경로: `D:/home/ruView/.github/CODEOWNERS`

```
# 기본 소유자
* @ruview-core

# 에이전트별 코드 소유권
/apps/web-monitor/          @agent-frontend
/apps/api-gateway/          @agent-frontend @agent-signal
/services/signal-adapter/   @agent-signal
/vendor/ruview-upstream/    @agent-observatory
/infra/                     @agent-devops
/agents/                    @agent-qa
/.github/                   @agent-devops
/docs/                      @agent-qa
```

### 단계 1.11 - CONTRIBUTING.md 생성

**도구**: `Write`

파일 경로: `D:/home/ruView/CONTRIBUTING.md`

```markdown
# Contributing to RuView

## 브랜치 네이밍 규칙

| 접두사 | 용도 | 예시 |
|--------|------|------|
| `feat/` | 새 기능 | `feat/floor-map-component` |
| `fix/` | 버그 수정 | `fix/websocket-reconnect` |
| `infra/` | 인프라 변경 | `infra/docker-compose-update` |
| `docs/` | 문서 변경 | `docs/api-reference` |
| `refactor/` | 리팩토링 | `refactor/signal-pipeline` |

## 커밋 메시지 규칙

```
<type>(<scope>): <subject>

<body>

<footer>
```

- **type**: feat, fix, docs, style, refactor, test, chore, infra
- **scope**: web-monitor, api-gateway, signal-adapter, observatory, devops, ci

## 에이전트별 작업 흐름

1. 이슈 확인 → 라벨 및 에이전트 태그 확인
2. `develop`에서 feature 브랜치 생성
3. 작업 완료 후 PR 생성 → `develop`으로 머지
4. QA Agent 검증 후 `main`으로 릴리즈
```

---

## Phase 2: 모노레포 디렉토리 구조 생성

> **완료 기준**: 전체 디렉토리 구조가 생성되고, 각 패키지의 초기 설정 파일이 존재

### 단계 2.1 - 전체 디렉토리 생성

**도구**: `Bash`

```bash
cd "D:/home/ruView"

# 앱 디렉토리
mkdir -p apps/web-monitor/src/{components,hooks,lib,pages,stores,styles,types}
mkdir -p apps/web-monitor/public
mkdir -p apps/api-gateway/src/{routes,middleware,services,types}

# 서비스 디렉토리
mkdir -p services/signal-adapter/src/{core,adapters,models,api}
mkdir -p services/signal-adapter/tests

# 벤더 디렉토리
mkdir -p vendor/ruview-upstream

# 인프라 디렉토리
mkdir -p infra/docker
mkdir -p infra/cloudflare
mkdir -p infra/github
mkdir -p infra/supabase/migrations
mkdir -p infra/supabase/seed

# 에이전트 문서
mkdir -p agents

# 문서 디렉토리
mkdir -p docs/architecture
mkdir -p docs/ci-cd
mkdir -p docs/protocol
mkdir -p docs/progress

# 공유 패키지
mkdir -p packages/shared-types/src
mkdir -p packages/eslint-config
mkdir -p packages/tsconfig

echo "디렉토리 구조 생성 완료"
find . -type d | head -60
```

### 단계 2.2 - 루트 pnpm workspace 설정

**도구**: `Write`

파일 경로: `D:/home/ruView/pnpm-workspace.yaml`

```yaml
packages:
  - "apps/*"
  - "packages/*"
  - "services/*"
```

### 단계 2.3 - 루트 package.json

**도구**: `Write`

파일 경로: `D:/home/ruView/package.json`

```json
{
  "name": "ruview-mvp",
  "version": "0.1.0",
  "private": true,
  "description": "RuView - Open-source CSI-based presence/fall detection service MVP",
  "scripts": {
    "dev": "pnpm -r --parallel run dev",
    "dev:web": "pnpm --filter @ruview/web-monitor dev",
    "dev:api": "pnpm --filter @ruview/api-gateway dev",
    "build": "pnpm -r run build",
    "build:web": "pnpm --filter @ruview/web-monitor build",
    "lint": "pnpm -r run lint",
    "test": "pnpm -r run test",
    "clean": "pnpm -r run clean",
    "format": "prettier --write \"**/*.{ts,tsx,js,jsx,json,md,yml,yaml}\""
  },
  "devDependencies": {
    "prettier": "^3.2.0",
    "turbo": "^2.0.0"
  },
  "engines": {
    "node": ">=18.0.0",
    "pnpm": ">=8.0.0"
  },
  "packageManager": "pnpm@9.0.0"
}
```

### 단계 2.4 - Turbo 설정

**도구**: `Write`

파일 경로: `D:/home/ruView/turbo.json`

```json
{
  "$schema": "https://turbo.build/schema.json",
  "globalDependencies": [".env"],
  "pipeline": {
    "build": {
      "dependsOn": ["^build"],
      "outputs": ["dist/**", "build/**"]
    },
    "dev": {
      "cache": false,
      "persistent": true
    },
    "lint": {
      "dependsOn": ["^build"]
    },
    "test": {
      "dependsOn": ["build"],
      "outputs": ["coverage/**"]
    },
    "clean": {
      "cache": false
    }
  }
}
```

### 단계 2.5 - 공유 TypeScript 설정

**도구**: `Write`

파일 경로: `D:/home/ruView/packages/tsconfig/base.json`

```json
{
  "$schema": "https://json.schemastore.org/tsconfig",
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "declaration": true,
    "declarationMap": true,
    "sourceMap": true
  },
  "exclude": ["node_modules", "dist", "build"]
}
```

**도구**: `Write`

파일 경로: `D:/home/ruView/packages/tsconfig/react.json`

```json
{
  "$schema": "https://json.schemastore.org/tsconfig",
  "extends": "./base.json",
  "compilerOptions": {
    "jsx": "react-jsx",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "noEmit": true
  }
}
```

**도구**: `Write`

파일 경로: `D:/home/ruView/packages/tsconfig/package.json`

```json
{
  "name": "@ruview/tsconfig",
  "version": "0.0.0",
  "private": true,
  "files": ["base.json", "react.json"]
}
```

### 단계 2.6 - 공유 타입 패키지

**도구**: `Write`

파일 경로: `D:/home/ruView/packages/shared-types/src/index.ts`

```typescript
// ===== Device Types =====
export interface Device {
  id: string;
  name: string;
  mac_address: string;
  zone_id: string;
  status: DeviceStatus;
  firmware_version: string;
  last_seen_at: string;
  created_at: string;
  updated_at: string;
}

export type DeviceStatus = 'online' | 'offline' | 'error' | 'updating';

// ===== Zone Types =====
export interface Zone {
  id: string;
  name: string;
  floor: number;
  coordinates: ZoneCoordinate[];
  device_ids: string[];
  created_at: string;
  updated_at: string;
}

export interface ZoneCoordinate {
  x: number;
  y: number;
}

// ===== Event Types =====
export interface SensingEvent {
  id: string;
  device_id: string;
  zone_id: string;
  event_type: EventType;
  confidence: number;
  payload: Record<string, unknown>;
  timestamp: string;
  created_at: string;
}

export type EventType =
  | 'presence_detected'
  | 'presence_lost'
  | 'fall_detected'
  | 'fall_confirmed'
  | 'movement_detected'
  | 'breathing_detected'
  | 'zone_enter'
  | 'zone_exit';

// ===== Alert Types =====
export interface Alert {
  id: string;
  event_id: string;
  zone_id: string;
  alert_type: AlertType;
  severity: AlertSeverity;
  message: string;
  acknowledged: boolean;
  acknowledged_by?: string;
  acknowledged_at?: string;
  created_at: string;
}

export type AlertType = 'fall' | 'no_presence' | 'device_offline' | 'anomaly';
export type AlertSeverity = 'critical' | 'warning' | 'info';

// ===== Signal Log Types =====
export interface SignalLog {
  id: string;
  device_id: string;
  raw_csi: number[];
  amplitude: number[];
  phase: number[];
  rssi: number;
  noise_floor: number;
  timestamp: string;
}

// ===== WebSocket Message Types =====
export interface WSMessage<T = unknown> {
  type: WSMessageType;
  topic: string;
  payload: T;
  timestamp: string;
}

export type WSMessageType =
  | 'event'
  | 'signal'
  | 'device_status'
  | 'alert'
  | 'heartbeat'
  | 'subscribe'
  | 'unsubscribe';

// ===== API Response Types =====
export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: ApiError;
  meta?: ApiMeta;
}

export interface ApiError {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

export interface ApiMeta {
  page?: number;
  per_page?: number;
  total?: number;
  total_pages?: number;
}

// ===== RuView Observatory Bridge Types =====
export interface ObservatoryConfig {
  containerId: string;
  width: number;
  height: number;
  zones: Zone[];
  devices: Device[];
  theme: 'light' | 'dark';
}

export interface ObservatoryEvent {
  type: 'zone_click' | 'device_click' | 'viewport_change';
  payload: Record<string, unknown>;
}
```

**도구**: `Write`

파일 경로: `D:/home/ruView/packages/shared-types/package.json`

```json
{
  "name": "@ruview/shared-types",
  "version": "0.1.0",
  "private": true,
  "main": "./src/index.ts",
  "types": "./src/index.ts",
  "scripts": {
    "lint": "tsc --noEmit",
    "clean": "rm -rf dist"
  },
  "devDependencies": {
    "typescript": "^5.4.0"
  }
}
```

**도구**: `Write`

파일 경로: `D:/home/ruView/packages/shared-types/tsconfig.json`

```json
{
  "extends": "@ruview/tsconfig/base.json",
  "compilerOptions": {
    "outDir": "./dist",
    "rootDir": "./src"
  },
  "include": ["src"]
}
```

---

## Phase 3: Bootstrap 스크립트 작성

> **완료 기준**: `infra/github/bootstrap-repos.sh`가 실행 가능하고, 전체 저장소 초기 설정을 자동화

### 단계 3.1 - bootstrap-repos.sh 작성

**도구**: `Write`

파일 경로: `D:/home/ruView/infra/github/bootstrap-repos.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# RuView MVP - GitHub Repository Bootstrap Script
#
# 사용법: ./infra/github/bootstrap-repos.sh
#
# 이 스크립트는 다음을 수행합니다:
#   1. GitHub 원격 저장소 생성
#   2. 브랜치 전략 설정 (main, develop)
#   3. 브랜치 보호 규칙 적용
#   4. 라벨 생성
#   5. 마일스톤 생성
#   6. 초기 이슈 생성
###############################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# .env 로드
if [ -f "$PROJECT_ROOT/.env" ]; then
    set -a
    source "$PROJECT_ROOT/.env"
    set +a
else
    echo "ERROR: .env 파일을 찾을 수 없습니다: $PROJECT_ROOT/.env"
    exit 1
fi

# 필수 환경변수 확인
: "${GITHUB_TOKEN:?GITHUB_TOKEN이 설정되지 않았습니다}"

export GITHUB_TOKEN

REPO_NAME="ruview-mvp"
REPO_DESC="RuView - Open-source CSI-based presence/fall detection service MVP"

echo "============================================"
echo "  RuView MVP - Repository Bootstrap"
echo "============================================"

# ----- 1. 저장소 생성 -----
echo ""
echo "[1/6] GitHub 저장소 생성..."

if gh repo view "$REPO_NAME" &>/dev/null; then
    echo "  저장소가 이미 존재합니다. 건너뜁니다."
else
    cd "$PROJECT_ROOT"

    if [ ! -d .git ]; then
        git init
        git checkout -b main
    fi

    gh repo create "$REPO_NAME" \
        --public \
        --description "$REPO_DESC" \
        --source . \
        --remote origin \
        --push

    echo "  저장소 생성 완료: $REPO_NAME"
fi

OWNER=$(gh api user --jq '.login')
FULL_REPO="$OWNER/$REPO_NAME"

# ----- 2. 브랜치 설정 -----
echo ""
echo "[2/6] 브랜치 전략 설정..."

cd "$PROJECT_ROOT"

# develop 브랜치
if git show-ref --verify --quiet refs/heads/develop 2>/dev/null; then
    echo "  develop 브랜치가 이미 존재합니다."
else
    git checkout -b develop
    git push -u origin develop
    echo "  develop 브랜치 생성 완료"
fi

git checkout main

# ----- 3. 브랜치 보호 -----
echo ""
echo "[3/6] 브랜치 보호 규칙 설정..."

# main 보호
gh api "repos/$FULL_REPO/branches/main/protection" \
    --method PUT \
    --silent \
    --input - <<'PROTECTION_JSON'
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["lint", "test", "build"]
  },
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "required_approving_review_count": 1,
    "dismiss_stale_reviews": true
  },
  "restrictions": null
}
PROTECTION_JSON
echo "  main 브랜치 보호 설정 완료"

# develop 보호
gh api "repos/$FULL_REPO/branches/develop/protection" \
    --method PUT \
    --silent \
    --input - <<'PROTECTION_JSON'
{
  "required_status_checks": {
    "strict": false,
    "contexts": ["lint"]
  },
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "required_approving_review_count": 1
  },
  "restrictions": null
}
PROTECTION_JSON
echo "  develop 브랜치 보호 설정 완료"

# ----- 4. 라벨 생성 -----
echo ""
echo "[4/6] 라벨 생성..."

declare -a LABEL_NAMES=(
    "agent:hardware"    "agent:signal"      "agent:frontend"
    "agent:observatory" "agent:devops"      "agent:qa"
    "priority:critical" "priority:high"     "priority:medium"    "priority:low"
    "type:feature"      "type:bugfix"       "type:infra"
    "type:docs"         "type:refactor"
    "status:in-progress" "status:review"    "status:blocked"
    "phase:q1-mvp"
)

declare -a LABEL_COLORS=(
    "0E8A16" "1D76DB" "5319E7"
    "D93F0B" "006B75" "BFD4F2"
    "B60205" "D93F0B" "FBCA04" "0E8A16"
    "A2EEEF" "D73A4A" "C5DEF5"
    "0075CA" "E4E669"
    "EDEDED" "FBCA04" "B60205"
    "6F42C1"
)

declare -a LABEL_DESCS=(
    "Hardware Agent" "Signal Agent" "Frontend Agent"
    "Observatory Agent" "DevOps Agent" "QA Agent"
    "긴급" "높음" "보통" "낮음"
    "새 기능" "버그 수정" "인프라"
    "문서" "리팩토링"
    "진행 중" "리뷰 대기" "블로킹"
    "Q1 MVP 스코프"
)

for i in "${!LABEL_NAMES[@]}"; do
    gh label create "${LABEL_NAMES[$i]}" \
        --repo "$FULL_REPO" \
        --color "${LABEL_COLORS[$i]}" \
        --description "${LABEL_DESCS[$i]}" \
        --force 2>/dev/null
    echo "  라벨: ${LABEL_NAMES[$i]}"
done

# ----- 5. 마일스톤 생성 -----
echo ""
echo "[5/6] 마일스톤 생성..."

create_milestone() {
    local title="$1"
    local desc="$2"
    local due="$3"

    gh api "repos/$FULL_REPO/milestones" \
        --method POST \
        --silent \
        --field title="$title" \
        --field description="$desc" \
        --field due_on="$due" 2>/dev/null || echo "  (이미 존재할 수 있음)"
    echo "  마일스톤: $title"
}

create_milestone "Q1 MVP - Core Infrastructure" \
    "모노레포 구조, CI/CD, Cloudflare, Supabase, 기본 관제 UI" \
    "2026-03-31T23:59:59Z"

create_milestone "Q1 MVP - Signal Pipeline" \
    "ESP32 CSI 수집 → Signal Adapter → Supabase 적재 → 실시간 관제" \
    "2026-04-15T23:59:59Z"

create_milestone "Q1 MVP - Observatory Integration" \
    "RuView Three.js Observatory 하이브리드 UI 통합" \
    "2026-04-30T23:59:59Z"

# ----- 6. 초기 이슈 생성 -----
echo ""
echo "[6/6] 초기 이슈 생성..."

create_issue() {
    local title="$1"
    local body="$2"
    local labels="$3"

    gh issue create \
        --repo "$FULL_REPO" \
        --title "$title" \
        --body "$body" \
        --label "$labels" 2>/dev/null
    echo "  이슈: $title"
}

create_issue "[infra] 모노레포 디렉토리 구조 및 CI/CD 초기 설정" \
    "Phase 2에서 정의된 모노레포 구조를 생성하고, GitHub Actions CI/CD를 설정합니다." \
    "type:infra,agent:devops,phase:q1-mvp"

create_issue "[feat] React 관제 앱 초기 셋업 (Vite + Tailwind + shadcn/ui)" \
    "apps/web-monitor에 Vite + React + TypeScript + Tailwind + shadcn/ui 스택 초기화" \
    "type:feature,agent:frontend,phase:q1-mvp"

create_issue "[feat] Python Signal Adapter 초기 셋업 (FastAPI)" \
    "services/signal-adapter에 FastAPI 기반 신호 처리 서비스 구현" \
    "type:feature,agent:signal,phase:q1-mvp"

create_issue "[infra] Cloudflare Pages + Tunnel 설정" \
    "web-monitor를 Cloudflare Pages에 배포하고, Tunnel로 로컬 API를 외부 공개" \
    "type:infra,agent:devops,phase:q1-mvp"

create_issue "[infra] Supabase 프로젝트 및 스키마 설정" \
    "Supabase 프로젝트 생성, 테이블 스키마, RLS, Realtime 설정" \
    "type:infra,agent:devops,phase:q1-mvp"

echo ""
echo "============================================"
echo "  Bootstrap 완료!"
echo "  저장소: https://github.com/$FULL_REPO"
echo "============================================"
```

### 단계 3.2 - 스크립트 실행 권한 부여

**도구**: `Bash`

```bash
chmod +x "D:/home/ruView/infra/github/bootstrap-repos.sh"
```

---

## Phase 4: Cloudflare 설정

> **완료 기준**: Pages 설정 파일, Tunnel 설정 파일, 환경변수 예시 파일이 모두 생성됨

### 단계 4.1 - Cloudflare Pages 환경변수 예시

**도구**: `Write`

파일 경로: `D:/home/ruView/infra/cloudflare/pages.env.example`

```bash
# ============================================
# Cloudflare Pages 환경변수 설정
# ============================================
# 이 파일을 참고하여 Cloudflare Pages 대시보드에서 환경변수를 설정하세요.
# 절대로 이 파일에 실제 값을 입력하지 마세요.

# ----- Production (main 브랜치) -----
# Cloudflare Pages > Settings > Environment variables > Production

VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIs...
VITE_API_BASE_URL=https://api.ruview.dev
VITE_API_WS_URL=wss://api.ruview.dev/ws
VITE_ENVIRONMENT=production

# ----- Preview (develop 브랜치) -----
# Cloudflare Pages > Settings > Environment variables > Preview

VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIs...
VITE_API_BASE_URL=https://api.dev.ruview.dev
VITE_API_WS_URL=wss://api.dev.ruview.dev/ws
VITE_ENVIRONMENT=preview

# ----- Pages 프로젝트 설정 -----
# Build command:        pnpm --filter @ruview/web-monitor build
# Build output:         apps/web-monitor/dist
# Root directory:       /
# Production branch:    main
# Preview branch:       develop
```

### 단계 4.2 - Cloudflare Pages 배포 스크립트

**도구**: `Write`

파일 경로: `D:/home/ruView/infra/cloudflare/setup-pages.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# Cloudflare Pages 프로젝트 설정 스크립트
#
# 사전 조건:
#   - wrangler CLI 설치 및 로그인 완료 (wrangler login)
#   - .env에 CLOUDFLARE_ACCOUNT_ID 설정
###############################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

source "$PROJECT_ROOT/.env"

PROJECT_NAME="ruview-web-monitor"

echo "=== Cloudflare Pages 프로젝트 설정 ==="

# Pages 프로젝트 생성
echo "[1/3] Pages 프로젝트 생성..."
wrangler pages project create "$PROJECT_NAME" \
    --production-branch main \
    2>/dev/null || echo "  프로젝트가 이미 존재합니다."

# GitHub 연결 안내
echo ""
echo "[2/3] GitHub 연결"
echo "  Cloudflare 대시보드에서 수동으로 GitHub 저장소를 연결해야 합니다:"
echo "  1. https://dash.cloudflare.com > Pages > $PROJECT_NAME"
echo "  2. Settings > Builds & deployments > Connect to Git"
echo "  3. GitHub 저장소 선택: ruview-mvp"
echo "  4. Build settings:"
echo "     - Framework: None"
echo "     - Build command: pnpm --filter @ruview/web-monitor build"
echo "     - Build output directory: apps/web-monitor/dist"
echo "     - Root directory: /"
echo "  5. Branch deployments:"
echo "     - Production: main"
echo "     - Preview: develop"

# 환경변수 설정 안내
echo ""
echo "[3/3] 환경변수 설정"
echo "  infra/cloudflare/pages.env.example를 참고하여"
echo "  Cloudflare 대시보드에서 환경변수를 설정해주세요."

echo ""
echo "=== Pages 설정 완료 ==="
```

### 단계 4.3 - Cloudflare Tunnel 설정 예시

**도구**: `Write`

파일 경로: `D:/home/ruView/infra/cloudflare/tunnel-config.example.yml`

```yaml
# ============================================
# Cloudflare Tunnel 설정 (예시)
# ============================================
#
# 사용법:
#   1. cloudflared tunnel login
#   2. cloudflared tunnel create ruview-dev
#   3. 이 파일을 ~/.cloudflared/config.yml로 복사
#   4. tunnel, credentials-file 값을 실제 값으로 교체
#   5. DNS 레코드 생성:
#      cloudflared tunnel route dns ruview-dev api.dev.example.com
#      cloudflared tunnel route dns ruview-dev sense.dev.example.com
#   6. cloudflared tunnel run ruview-dev
#
# 주의: 이 파일에 실제 터널 ID나 시크릿을 넣지 마세요.

tunnel: <YOUR_TUNNEL_ID>
credentials-file: /home/<user>/.cloudflared/<YOUR_TUNNEL_ID>.json

ingress:
  # API Gateway (FastAPI)
  - hostname: api.dev.example.com
    service: http://localhost:8000
    originRequest:
      connectTimeout: 10s
      noTLSVerify: false

  # Sensing Server (RuView 관제)
  - hostname: sense.dev.example.com
    service: http://localhost:3000
    originRequest:
      connectTimeout: 10s

  # WebSocket 지원 (API Gateway WS)
  - hostname: ws.dev.example.com
    service: http://localhost:8000
    originRequest:
      connectTimeout: 30s

  # Catch-all (필수)
  - service: http_status:404
```

### 단계 4.4 - Cloudflare Tunnel 설정 스크립트

**도구**: `Write`

파일 경로: `D:/home/ruView/infra/cloudflare/setup-tunnel.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# Cloudflare Tunnel 설정 스크립트
#
# 사전 조건:
#   - cloudflared 설치 완료
#   - cloudflared tunnel login 완료
###############################################################################

TUNNEL_NAME="ruview-dev"

echo "=== Cloudflare Tunnel 설정 ==="

# 1. 터널 생성
echo "[1/4] 터널 생성..."
if cloudflared tunnel list | grep -q "$TUNNEL_NAME"; then
    echo "  터널 '$TUNNEL_NAME'이 이미 존재합니다."
    TUNNEL_ID=$(cloudflared tunnel list --output json | python -c "
import sys, json
tunnels = json.load(sys.stdin)
for t in tunnels:
    if t['name'] == '$TUNNEL_NAME':
        print(t['id'])
        break
")
else
    TUNNEL_ID=$(cloudflared tunnel create "$TUNNEL_NAME" 2>&1 | grep -oP '[0-9a-f-]{36}')
    echo "  터널 생성 완료: $TUNNEL_ID"
fi

echo "  터널 ID: $TUNNEL_ID"

# 2. DNS 라우팅
echo ""
echo "[2/4] DNS 라우팅 설정..."
echo "  아래 명령을 실행하여 DNS를 설정해주세요:"
echo ""
echo "  cloudflared tunnel route dns $TUNNEL_NAME api.dev.example.com"
echo "  cloudflared tunnel route dns $TUNNEL_NAME sense.dev.example.com"
echo "  cloudflared tunnel route dns $TUNNEL_NAME ws.dev.example.com"

# 3. 설정 파일 생성 안내
echo ""
echo "[3/4] 설정 파일"
echo "  infra/cloudflare/tunnel-config.example.yml를 참고하여"
echo "  ~/.cloudflared/config.yml을 생성해주세요."
echo "  tunnel 값을 '$TUNNEL_ID'로 교체하세요."

# 4. 실행
echo ""
echo "[4/4] 터널 실행"
echo "  cloudflared tunnel run $TUNNEL_NAME"

echo ""
echo "=== Tunnel 설정 완료 ==="
```

### 단계 4.5 - 스크립트 실행 권한

**도구**: `Bash`

```bash
chmod +x "D:/home/ruView/infra/cloudflare/setup-pages.sh"
chmod +x "D:/home/ruView/infra/cloudflare/setup-tunnel.sh"
```

---

## Phase 5: Supabase 프로젝트 설정

> **완료 기준**: 전체 테이블 스키마 마이그레이션 SQL, RLS 정책, Realtime 활성화 SQL이 작성됨

### 단계 5.1 - 초기 스키마 마이그레이션

**도구**: `Write`

파일 경로: `D:/home/ruView/infra/supabase/migrations/001_initial_schema.sql`

```sql
-- ============================================
-- RuView MVP - 초기 데이터베이스 스키마
-- ============================================

-- UUID 확장
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ===== ENUM Types =====

CREATE TYPE device_status AS ENUM ('online', 'offline', 'error', 'updating');

CREATE TYPE event_type AS ENUM (
    'presence_detected',
    'presence_lost',
    'fall_detected',
    'fall_confirmed',
    'movement_detected',
    'breathing_detected',
    'zone_enter',
    'zone_exit'
);

CREATE TYPE alert_type AS ENUM ('fall', 'no_presence', 'device_offline', 'anomaly');
CREATE TYPE alert_severity AS ENUM ('critical', 'warning', 'info');

-- ===== devices 테이블 =====

CREATE TABLE IF NOT EXISTS devices (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name          VARCHAR(100) NOT NULL,
    mac_address   VARCHAR(17) NOT NULL UNIQUE,
    zone_id       UUID,
    status        device_status NOT NULL DEFAULT 'offline',
    firmware_version VARCHAR(20),
    config        JSONB DEFAULT '{}',
    last_seen_at  TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_devices_zone ON devices(zone_id);
CREATE INDEX idx_devices_status ON devices(status);
CREATE INDEX idx_devices_mac ON devices(mac_address);

-- ===== zones 테이블 =====

CREATE TABLE IF NOT EXISTS zones (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name          VARCHAR(100) NOT NULL,
    floor         INTEGER NOT NULL DEFAULT 1,
    coordinates   JSONB NOT NULL DEFAULT '[]',
    metadata      JSONB DEFAULT '{}',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- devices.zone_id FK 추가
ALTER TABLE devices
    ADD CONSTRAINT fk_devices_zone
    FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE SET NULL;

-- ===== events 테이블 =====

CREATE TABLE IF NOT EXISTS events (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    device_id     UUID NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    zone_id       UUID REFERENCES zones(id) ON DELETE SET NULL,
    event_type    event_type NOT NULL,
    confidence    REAL NOT NULL DEFAULT 0.0 CHECK (confidence >= 0 AND confidence <= 1),
    payload       JSONB DEFAULT '{}',
    timestamp     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_events_device ON events(device_id);
CREATE INDEX idx_events_zone ON events(zone_id);
CREATE INDEX idx_events_type ON events(event_type);
CREATE INDEX idx_events_timestamp ON events(timestamp DESC);

-- 파티셔닝을 위한 복합 인덱스
CREATE INDEX idx_events_device_timestamp ON events(device_id, timestamp DESC);

-- ===== signal_logs 테이블 =====
-- 고빈도 데이터이므로 TimescaleDB 사용 시 hypertable로 변환 권장

CREATE TABLE IF NOT EXISTS signal_logs (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    device_id     UUID NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    raw_csi       REAL[] DEFAULT '{}',
    amplitude     REAL[] DEFAULT '{}',
    phase         REAL[] DEFAULT '{}',
    rssi          REAL,
    noise_floor   REAL,
    subcarrier_count INTEGER,
    metadata      JSONB DEFAULT '{}',
    timestamp     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_signal_logs_device ON signal_logs(device_id);
CREATE INDEX idx_signal_logs_timestamp ON signal_logs(timestamp DESC);
CREATE INDEX idx_signal_logs_device_timestamp ON signal_logs(device_id, timestamp DESC);

-- ===== alerts 테이블 =====

CREATE TABLE IF NOT EXISTS alerts (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_id        UUID REFERENCES events(id) ON DELETE SET NULL,
    zone_id         UUID REFERENCES zones(id) ON DELETE SET NULL,
    alert_type      alert_type NOT NULL,
    severity        alert_severity NOT NULL DEFAULT 'info',
    message         TEXT NOT NULL,
    acknowledged    BOOLEAN NOT NULL DEFAULT FALSE,
    acknowledged_by VARCHAR(100),
    acknowledged_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_alerts_zone ON alerts(zone_id);
CREATE INDEX idx_alerts_type ON alerts(alert_type);
CREATE INDEX idx_alerts_severity ON alerts(severity);
CREATE INDEX idx_alerts_unacknowledged ON alerts(acknowledged) WHERE acknowledged = FALSE;
CREATE INDEX idx_alerts_created ON alerts(created_at DESC);

-- ===== updated_at 자동 갱신 트리거 =====

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_devices_updated_at
    BEFORE UPDATE ON devices
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_zones_updated_at
    BEFORE UPDATE ON zones
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
```

### 단계 5.2 - RLS 정책 마이그레이션

**도구**: `Write`

파일 경로: `D:/home/ruView/infra/supabase/migrations/002_rls_policies.sql`

```sql
-- ============================================
-- RuView MVP - Row Level Security 정책
-- ============================================
--
-- MVP 단계에서는 anon 키로 읽기만 허용하고,
-- service_role 키로 쓰기를 수행합니다.
-- 사용자 인증은 Phase 2에서 추가합니다.

-- RLS 활성화
ALTER TABLE devices ENABLE ROW LEVEL SECURITY;
ALTER TABLE zones ENABLE ROW LEVEL SECURITY;
ALTER TABLE events ENABLE ROW LEVEL SECURITY;
ALTER TABLE signal_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE alerts ENABLE ROW LEVEL SECURITY;

-- ===== devices 정책 =====

-- anon/authenticated: 읽기 허용
CREATE POLICY "devices_select_all"
    ON devices FOR SELECT
    TO anon, authenticated
    USING (true);

-- service_role: 모든 작업 허용 (Signal Adapter에서 사용)
CREATE POLICY "devices_all_service"
    ON devices FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- ===== zones 정책 =====

CREATE POLICY "zones_select_all"
    ON zones FOR SELECT
    TO anon, authenticated
    USING (true);

CREATE POLICY "zones_all_service"
    ON zones FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- ===== events 정책 =====

CREATE POLICY "events_select_all"
    ON events FOR SELECT
    TO anon, authenticated
    USING (true);

CREATE POLICY "events_insert_service"
    ON events FOR INSERT
    TO service_role
    WITH CHECK (true);

-- 이벤트는 수정/삭제 불가 (감사 로그 성격)
-- service_role만 DELETE 허용 (데이터 정리용)
CREATE POLICY "events_delete_service"
    ON events FOR DELETE
    TO service_role
    USING (true);

-- ===== signal_logs 정책 =====

-- signal_logs는 고빈도 데이터이므로 anon 읽기를 제한할 수 있음
-- MVP에서는 읽기 허용
CREATE POLICY "signal_logs_select_all"
    ON signal_logs FOR SELECT
    TO anon, authenticated
    USING (true);

CREATE POLICY "signal_logs_insert_service"
    ON signal_logs FOR INSERT
    TO service_role
    WITH CHECK (true);

CREATE POLICY "signal_logs_delete_service"
    ON signal_logs FOR DELETE
    TO service_role
    USING (true);

-- ===== alerts 정책 =====

CREATE POLICY "alerts_select_all"
    ON alerts FOR SELECT
    TO anon, authenticated
    USING (true);

CREATE POLICY "alerts_insert_service"
    ON alerts FOR INSERT
    TO service_role
    WITH CHECK (true);

-- 알림 확인(acknowledge)은 authenticated 사용자도 가능
CREATE POLICY "alerts_update_acknowledge"
    ON alerts FOR UPDATE
    TO anon, authenticated
    USING (true)
    WITH CHECK (true);

CREATE POLICY "alerts_all_service"
    ON alerts FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);
```

### 단계 5.3 - Realtime 활성화 마이그레이션

**도구**: `Write`

파일 경로: `D:/home/ruView/infra/supabase/migrations/003_realtime.sql`

```sql
-- ============================================
-- RuView MVP - Supabase Realtime 활성화
-- ============================================

-- Realtime 구독이 필요한 테이블에 대해 REPLICA IDENTITY 설정
-- Supabase Realtime은 WAL을 기반으로 하므로 FULL 설정 필요

ALTER TABLE devices REPLICA IDENTITY FULL;
ALTER TABLE events REPLICA IDENTITY FULL;
ALTER TABLE alerts REPLICA IDENTITY FULL;

-- Supabase 대시보드에서 Realtime 활성화:
-- 1. Database > Replication 이동
-- 2. 아래 테이블들에 대해 Realtime 토글 활성화:
--    - devices  (상태 변경 실시간 반영)
--    - events   (새 이벤트 실시간 수신)
--    - alerts   (새 알림 실시간 수신)
--
-- signal_logs는 고빈도 데이터이므로 Realtime 비활성화
-- (WebSocket을 통한 별도 스트리밍 사용)

-- Realtime 구독 예시 (클라이언트 코드):
--
-- supabase
--   .channel('events')
--   .on('postgres_changes', {
--     event: 'INSERT',
--     schema: 'public',
--     table: 'events'
--   }, (payload) => {
--     console.log('New event:', payload.new)
--   })
--   .subscribe()
```

### 단계 5.4 - 시드 데이터

**도구**: `Write`

파일 경로: `D:/home/ruView/infra/supabase/seed/001_sample_data.sql`

```sql
-- ============================================
-- RuView MVP - 샘플 시드 데이터
-- ============================================

-- 샘플 존
INSERT INTO zones (id, name, floor, coordinates) VALUES
    ('a0000000-0000-0000-0000-000000000001', '거실', 1,
     '[{"x": 0, "y": 0}, {"x": 500, "y": 0}, {"x": 500, "y": 400}, {"x": 0, "y": 400}]'),
    ('a0000000-0000-0000-0000-000000000002', '침실', 1,
     '[{"x": 500, "y": 0}, {"x": 800, "y": 0}, {"x": 800, "y": 400}, {"x": 500, "y": 400}]'),
    ('a0000000-0000-0000-0000-000000000003', '화장실', 1,
     '[{"x": 800, "y": 0}, {"x": 1000, "y": 0}, {"x": 1000, "y": 200}, {"x": 800, "y": 200}]')
ON CONFLICT DO NOTHING;

-- 샘플 디바이스
INSERT INTO devices (id, name, mac_address, zone_id, status, firmware_version) VALUES
    ('d0000000-0000-0000-0000-000000000001', 'ESP32-거실-01',
     'AA:BB:CC:DD:EE:01', 'a0000000-0000-0000-0000-000000000001',
     'online', '0.1.0'),
    ('d0000000-0000-0000-0000-000000000002', 'ESP32-침실-01',
     'AA:BB:CC:DD:EE:02', 'a0000000-0000-0000-0000-000000000002',
     'online', '0.1.0'),
    ('d0000000-0000-0000-0000-000000000003', 'ESP32-화장실-01',
     'AA:BB:CC:DD:EE:03', 'a0000000-0000-0000-0000-000000000003',
     'offline', '0.1.0')
ON CONFLICT DO NOTHING;
```

### 단계 5.5 - Supabase Edge Function (선택)

**도구**: `Write`

파일 경로: `D:/home/ruView/infra/supabase/functions/process-alert/index.ts`

```typescript
// ============================================
// RuView MVP - Alert 처리 Edge Function
// ============================================
//
// 트리거: events 테이블에 fall_detected 이벤트 삽입 시
// 동작: alerts 테이블에 알림 생성 + (선택) 외부 알림 발송
//
// 배포: supabase functions deploy process-alert

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

interface WebhookPayload {
  type: "INSERT";
  table: string;
  record: {
    id: string;
    device_id: string;
    zone_id: string;
    event_type: string;
    confidence: number;
    timestamp: string;
  };
  schema: string;
}

serve(async (req: Request) => {
  try {
    const payload: WebhookPayload = await req.json();

    // fall_detected 이벤트만 처리
    if (
      payload.record.event_type !== "fall_detected" &&
      payload.record.event_type !== "fall_confirmed"
    ) {
      return new Response(JSON.stringify({ skipped: true }), {
        headers: { "Content-Type": "application/json" },
      });
    }

    const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
    const supabaseKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
    const supabase = createClient(supabaseUrl, supabaseKey);

    // 알림 생성
    const severity =
      payload.record.event_type === "fall_confirmed" ? "critical" : "warning";

    const { data, error } = await supabase.from("alerts").insert({
      event_id: payload.record.id,
      zone_id: payload.record.zone_id,
      alert_type: "fall",
      severity,
      message: `낙상 감지 (confidence: ${(payload.record.confidence * 100).toFixed(1)}%)`,
    });

    if (error) {
      throw error;
    }

    // TODO: 외부 알림 발송 (Slack, LINE, SMS 등)

    return new Response(JSON.stringify({ success: true, data }), {
      headers: { "Content-Type": "application/json" },
    });
  } catch (err) {
    return new Response(
      JSON.stringify({ error: (err as Error).message }),
      {
        status: 500,
        headers: { "Content-Type": "application/json" },
      }
    );
  }
});
```

---

## Phase 6: React 관제 앱 (apps/web-monitor)

> **완료 기준**: Vite + React + TypeScript + Tailwind + shadcn/ui 앱이 빌드/실행되고, Supabase 연동, WebSocket hook, 2D Floor 컴포넌트, Observatory bridge가 구현됨

### 단계 6.1 - Vite + React + TypeScript 프로젝트 초기화

**도구**: `Bash`

```bash
cd "D:/home/ruView/apps/web-monitor"
pnpm create vite . --template react-ts -- --force
```

> 만약 디렉토리에 이미 파일이 있다면 `--force` 플래그로 덮어쓴다.

### 단계 6.2 - package.json 수정

**도구**: `Read` → `Edit`

파일: `D:/home/ruView/apps/web-monitor/package.json`

name을 `@ruview/web-monitor`로 변경하고, 아래 의존성을 추가:

```json
{
  "name": "@ruview/web-monitor",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite --port 3000",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "lint": "eslint . --ext ts,tsx --report-unused-disable-directives --max-warnings 0",
    "clean": "rm -rf dist node_modules"
  },
  "dependencies": {
    "@supabase/supabase-js": "^2.43.0",
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "react-router-dom": "^6.23.0",
    "zustand": "^4.5.0",
    "react-konva": "^18.2.0",
    "konva": "^9.3.0",
    "lucide-react": "^0.370.0",
    "clsx": "^2.1.0",
    "tailwind-merge": "^2.3.0",
    "date-fns": "^3.6.0"
  },
  "devDependencies": {
    "@ruview/shared-types": "workspace:*",
    "@ruview/tsconfig": "workspace:*",
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.2.0",
    "autoprefixer": "^10.4.19",
    "postcss": "^8.4.38",
    "tailwindcss": "^3.4.0",
    "typescript": "^5.4.0",
    "vite": "^5.2.0",
    "eslint": "^8.57.0"
  }
}
```

### 단계 6.3 - TypeScript 설정

**도구**: `Write`

파일 경로: `D:/home/ruView/apps/web-monitor/tsconfig.json`

```json
{
  "extends": "@ruview/tsconfig/react.json",
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"],
      "@ruview/shared-types": ["../../packages/shared-types/src"]
    }
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

**도구**: `Write`

파일 경로: `D:/home/ruView/apps/web-monitor/tsconfig.node.json`

```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true
  },
  "include": ["vite.config.ts"]
}
```

### 단계 6.4 - Vite 설정

**도구**: `Write`

파일 경로: `D:/home/ruView/apps/web-monitor/vite.config.ts`

```typescript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
});
```

### 단계 6.5 - Tailwind CSS 설정

**도구**: `Write`

파일 경로: `D:/home/ruView/apps/web-monitor/tailwind.config.js`

```javascript
/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))',
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))',
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))',
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))',
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))',
        },
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))',
        },
        // RuView 커스텀 색상
        ruview: {
          presence: '#22c55e',
          fall: '#ef4444',
          offline: '#6b7280',
          signal: '#3b82f6',
        },
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'ping-slow': 'ping 2s cubic-bezier(0, 0, 0.2, 1) infinite',
      },
    },
  },
  plugins: [],
};
```

**도구**: `Write`

파일 경로: `D:/home/ruView/apps/web-monitor/postcss.config.js`

```javascript
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
```

### 단계 6.6 - 글로벌 스타일

**도구**: `Write`

파일 경로: `D:/home/ruView/apps/web-monitor/src/styles/globals.css`

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    --background: 0 0% 100%;
    --foreground: 222.2 84% 4.9%;
    --card: 0 0% 100%;
    --card-foreground: 222.2 84% 4.9%;
    --primary: 221.2 83.2% 53.3%;
    --primary-foreground: 210 40% 98%;
    --secondary: 210 40% 96.1%;
    --secondary-foreground: 222.2 47.4% 11.2%;
    --muted: 210 40% 96.1%;
    --muted-foreground: 215.4 16.3% 46.9%;
    --accent: 210 40% 96.1%;
    --accent-foreground: 222.2 47.4% 11.2%;
    --destructive: 0 84.2% 60.2%;
    --destructive-foreground: 210 40% 98%;
    --border: 214.3 31.8% 91.4%;
    --input: 214.3 31.8% 91.4%;
    --ring: 221.2 83.2% 53.3%;
    --radius: 0.5rem;
  }

  .dark {
    --background: 222.2 84% 4.9%;
    --foreground: 210 40% 98%;
    --card: 222.2 84% 4.9%;
    --card-foreground: 210 40% 98%;
    --primary: 217.2 91.2% 59.8%;
    --primary-foreground: 222.2 47.4% 11.2%;
    --secondary: 217.2 32.6% 17.5%;
    --secondary-foreground: 210 40% 98%;
    --muted: 217.2 32.6% 17.5%;
    --muted-foreground: 215 20.2% 65.1%;
    --accent: 217.2 32.6% 17.5%;
    --accent-foreground: 210 40% 98%;
    --destructive: 0 62.8% 30.6%;
    --destructive-foreground: 210 40% 98%;
    --border: 217.2 32.6% 17.5%;
    --input: 217.2 32.6% 17.5%;
    --ring: 224.3 76.3% 48%;
  }
}

@layer base {
  * {
    @apply border-border;
  }
  body {
    @apply bg-background text-foreground;
    font-feature-settings: "rlig" 1, "calt" 1;
  }
}
```

### 단계 6.7 - Supabase 클라이언트

**도구**: `Write`

파일 경로: `D:/home/ruView/apps/web-monitor/src/lib/supabase.ts`

```typescript
import { createClient } from '@supabase/supabase-js';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

if (!supabaseUrl || !supabaseAnonKey) {
  console.warn(
    'Supabase 환경변수가 설정되지 않았습니다. .env 파일을 확인해주세요.'
  );
}

export const supabase = createClient(
  supabaseUrl || 'http://localhost:54321',
  supabaseAnonKey || 'placeholder-key'
);
```

### 단계 6.8 - Zustand 상태 관리 스토어

**도구**: `Write`

파일 경로: `D:/home/ruView/apps/web-monitor/src/stores/deviceStore.ts`

```typescript
import { create } from 'zustand';
import type { Device, DeviceStatus } from '@ruview/shared-types';
import { supabase } from '@/lib/supabase';

interface DeviceState {
  devices: Device[];
  selectedDeviceId: string | null;
  isLoading: boolean;
  error: string | null;

  // Actions
  fetchDevices: () => Promise<void>;
  selectDevice: (id: string | null) => void;
  updateDeviceStatus: (id: string, status: DeviceStatus) => void;
  subscribeToChanges: () => () => void;
}

export const useDeviceStore = create<DeviceState>((set, get) => ({
  devices: [],
  selectedDeviceId: null,
  isLoading: false,
  error: null,

  fetchDevices: async () => {
    set({ isLoading: true, error: null });
    try {
      const { data, error } = await supabase
        .from('devices')
        .select('*')
        .order('name');

      if (error) throw error;
      set({ devices: data as Device[], isLoading: false });
    } catch (err) {
      set({ error: (err as Error).message, isLoading: false });
    }
  },

  selectDevice: (id) => set({ selectedDeviceId: id }),

  updateDeviceStatus: (id, status) => {
    set((state) => ({
      devices: state.devices.map((d) =>
        d.id === id ? { ...d, status } : d
      ),
    }));
  },

  subscribeToChanges: () => {
    const channel = supabase
      .channel('devices-changes')
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table: 'devices' },
        (payload) => {
          const { eventType } = payload;
          if (eventType === 'UPDATE' || eventType === 'INSERT') {
            const updated = payload.new as Device;
            set((state) => ({
              devices: state.devices.some((d) => d.id === updated.id)
                ? state.devices.map((d) =>
                    d.id === updated.id ? updated : d
                  )
                : [...state.devices, updated],
            }));
          } else if (eventType === 'DELETE') {
            const deleted = payload.old as { id: string };
            set((state) => ({
              devices: state.devices.filter((d) => d.id !== deleted.id),
            }));
          }
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  },
}));
```

**도구**: `Write`

파일 경로: `D:/home/ruView/apps/web-monitor/src/stores/eventStore.ts`

```typescript
import { create } from 'zustand';
import type { SensingEvent, Alert } from '@ruview/shared-types';
import { supabase } from '@/lib/supabase';

interface EventState {
  events: SensingEvent[];
  alerts: Alert[];
  unacknowledgedCount: number;
  isLoading: boolean;

  // Actions
  fetchRecentEvents: (limit?: number) => Promise<void>;
  fetchAlerts: () => Promise<void>;
  acknowledgeAlert: (alertId: string, by: string) => Promise<void>;
  subscribeToEvents: () => () => void;
  subscribeToAlerts: () => () => void;
}

export const useEventStore = create<EventState>((set, get) => ({
  events: [],
  alerts: [],
  unacknowledgedCount: 0,
  isLoading: false,

  fetchRecentEvents: async (limit = 50) => {
    set({ isLoading: true });
    try {
      const { data, error } = await supabase
        .from('events')
        .select('*')
        .order('timestamp', { ascending: false })
        .limit(limit);

      if (error) throw error;
      set({ events: data as SensingEvent[], isLoading: false });
    } catch (err) {
      console.error('이벤트 조회 실패:', err);
      set({ isLoading: false });
    }
  },

  fetchAlerts: async () => {
    try {
      const { data, error } = await supabase
        .from('alerts')
        .select('*')
        .order('created_at', { ascending: false })
        .limit(100);

      if (error) throw error;
      const alerts = data as Alert[];
      set({
        alerts,
        unacknowledgedCount: alerts.filter((a) => !a.acknowledged).length,
      });
    } catch (err) {
      console.error('알림 조회 실패:', err);
    }
  },

  acknowledgeAlert: async (alertId, by) => {
    try {
      const { error } = await supabase
        .from('alerts')
        .update({
          acknowledged: true,
          acknowledged_by: by,
          acknowledged_at: new Date().toISOString(),
        })
        .eq('id', alertId);

      if (error) throw error;
      await get().fetchAlerts();
    } catch (err) {
      console.error('알림 확인 실패:', err);
    }
  },

  subscribeToEvents: () => {
    const channel = supabase
      .channel('events-realtime')
      .on(
        'postgres_changes',
        { event: 'INSERT', schema: 'public', table: 'events' },
        (payload) => {
          const newEvent = payload.new as SensingEvent;
          set((state) => ({
            events: [newEvent, ...state.events].slice(0, 100),
          }));
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  },

  subscribeToAlerts: () => {
    const channel = supabase
      .channel('alerts-realtime')
      .on(
        'postgres_changes',
        { event: 'INSERT', schema: 'public', table: 'alerts' },
        (payload) => {
          const newAlert = payload.new as Alert;
          set((state) => ({
            alerts: [newAlert, ...state.alerts],
            unacknowledgedCount: state.unacknowledgedCount + 1,
          }));
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  },
}));
```

### 단계 6.9 - WebSocket Hook

**도구**: `Write`

파일 경로: `D:/home/ruView/apps/web-monitor/src/hooks/useWebSocket.ts`

```typescript
import { useEffect, useRef, useCallback, useState } from 'react';
import type { WSMessage } from '@ruview/shared-types';

interface UseWebSocketOptions {
  url: string;
  onMessage?: (message: WSMessage) => void;
  onOpen?: () => void;
  onClose?: () => void;
  onError?: (error: Event) => void;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
  autoConnect?: boolean;
}

interface UseWebSocketReturn {
  isConnected: boolean;
  reconnectCount: number;
  send: (message: WSMessage) => void;
  connect: () => void;
  disconnect: () => void;
  subscribe: (topic: string) => void;
  unsubscribe: (topic: string) => void;
}

export function useWebSocket(options: UseWebSocketOptions): UseWebSocketReturn {
  const {
    url,
    onMessage,
    onOpen,
    onClose,
    onError,
    reconnectInterval = 3000,
    maxReconnectAttempts = 10,
    autoConnect = true,
  } = options;

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectCountRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout>>();
  const [isConnected, setIsConnected] = useState(false);
  const [reconnectCount, setReconnectCount] = useState(0);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    try {
      const ws = new WebSocket(url);

      ws.onopen = () => {
        setIsConnected(true);
        reconnectCountRef.current = 0;
        setReconnectCount(0);
        onOpen?.();
      };

      ws.onmessage = (event) => {
        try {
          const message: WSMessage = JSON.parse(event.data);
          onMessage?.(message);
        } catch (err) {
          console.error('WebSocket 메시지 파싱 오류:', err);
        }
      };

      ws.onclose = () => {
        setIsConnected(false);
        onClose?.();

        // 자동 재연결
        if (reconnectCountRef.current < maxReconnectAttempts) {
          reconnectCountRef.current += 1;
          setReconnectCount(reconnectCountRef.current);
          reconnectTimerRef.current = setTimeout(connect, reconnectInterval);
        }
      };

      ws.onerror = (error) => {
        onError?.(error);
      };

      wsRef.current = ws;
    } catch (err) {
      console.error('WebSocket 연결 오류:', err);
    }
  }, [url, onMessage, onOpen, onClose, onError, reconnectInterval, maxReconnectAttempts]);

  const disconnect = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
    }
    reconnectCountRef.current = maxReconnectAttempts; // 재연결 방지
    wsRef.current?.close();
    wsRef.current = null;
    setIsConnected(false);
  }, [maxReconnectAttempts]);

  const send = useCallback((message: WSMessage) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    } else {
      console.warn('WebSocket이 연결되지 않아 메시지를 보낼 수 없습니다.');
    }
  }, []);

  const subscribe = useCallback((topic: string) => {
    send({
      type: 'subscribe',
      topic,
      payload: {},
      timestamp: new Date().toISOString(),
    });
  }, [send]);

  const unsubscribe = useCallback((topic: string) => {
    send({
      type: 'unsubscribe',
      topic,
      payload: {},
      timestamp: new Date().toISOString(),
    });
  }, [send]);

  useEffect(() => {
    if (autoConnect) {
      connect();
    }
    return () => {
      disconnect();
    };
  }, [autoConnect, connect, disconnect]);

  return {
    isConnected,
    reconnectCount,
    send,
    connect,
    disconnect,
    subscribe,
    unsubscribe,
  };
}
```

### 단계 6.10 - 2D Floor 컴포넌트 (Konva)

**도구**: `Write`

파일 경로: `D:/home/ruView/apps/web-monitor/src/components/FloorMap.tsx`

```tsx
import React, { useMemo } from 'react';
import { Stage, Layer, Rect, Circle, Text, Group, Line } from 'react-konva';
import type { Zone, Device, SensingEvent } from '@ruview/shared-types';

interface FloorMapProps {
  width: number;
  height: number;
  zones: Zone[];
  devices: Device[];
  activeEvents?: SensingEvent[];
  selectedZoneId?: string | null;
  onZoneClick?: (zone: Zone) => void;
  onDeviceClick?: (device: Device) => void;
  scale?: number;
}

const STATUS_COLORS: Record<string, string> = {
  online: '#22c55e',
  offline: '#6b7280',
  error: '#ef4444',
  updating: '#f59e0b',
};

const EVENT_COLORS: Record<string, string> = {
  presence_detected: '#22c55e',
  presence_lost: '#9ca3af',
  fall_detected: '#ef4444',
  fall_confirmed: '#dc2626',
  movement_detected: '#3b82f6',
  breathing_detected: '#8b5cf6',
  zone_enter: '#06b6d4',
  zone_exit: '#f97316',
};

export const FloorMap: React.FC<FloorMapProps> = ({
  width,
  height,
  zones,
  devices,
  activeEvents = [],
  selectedZoneId,
  onZoneClick,
  onDeviceClick,
  scale = 1,
}) => {
  // 존별 활성 이벤트 매핑
  const zoneEventMap = useMemo(() => {
    const map = new Map<string, SensingEvent[]>();
    activeEvents.forEach((event) => {
      const existing = map.get(event.zone_id) || [];
      existing.push(event);
      map.set(event.zone_id, existing);
    });
    return map;
  }, [activeEvents]);

  // 존별 디바이스 매핑
  const zoneDeviceMap = useMemo(() => {
    const map = new Map<string, Device[]>();
    devices.forEach((device) => {
      if (device.zone_id) {
        const existing = map.get(device.zone_id) || [];
        existing.push(device);
        map.set(device.zone_id, existing);
      }
    });
    return map;
  }, [devices]);

  const getZoneFillColor = (zone: Zone): string => {
    const events = zoneEventMap.get(zone.id) || [];
    if (events.some((e) => e.event_type === 'fall_detected' || e.event_type === 'fall_confirmed')) {
      return 'rgba(239, 68, 68, 0.3)';
    }
    if (events.some((e) => e.event_type === 'presence_detected')) {
      return 'rgba(34, 197, 94, 0.2)';
    }
    if (zone.id === selectedZoneId) {
      return 'rgba(59, 130, 246, 0.2)';
    }
    return 'rgba(148, 163, 184, 0.1)';
  };

  return (
    <Stage width={width} height={height} scaleX={scale} scaleY={scale}>
      <Layer>
        {/* 배경 그리드 */}
        {Array.from({ length: Math.ceil(width / 50) }).map((_, i) => (
          <Line
            key={`grid-v-${i}`}
            points={[i * 50, 0, i * 50, height]}
            stroke="#e2e8f0"
            strokeWidth={0.5}
          />
        ))}
        {Array.from({ length: Math.ceil(height / 50) }).map((_, i) => (
          <Line
            key={`grid-h-${i}`}
            points={[0, i * 50, width, i * 50]}
            stroke="#e2e8f0"
            strokeWidth={0.5}
          />
        ))}

        {/* 존 렌더링 */}
        {zones.map((zone) => {
          const coords = zone.coordinates as Array<{ x: number; y: number }>;
          if (!coords || coords.length < 2) return null;

          const minX = Math.min(...coords.map((c) => c.x));
          const minY = Math.min(...coords.map((c) => c.y));
          const maxX = Math.max(...coords.map((c) => c.x));
          const maxY = Math.max(...coords.map((c) => c.y));

          return (
            <Group key={zone.id}>
              {/* 존 영역 */}
              <Rect
                x={minX}
                y={minY}
                width={maxX - minX}
                height={maxY - minY}
                fill={getZoneFillColor(zone)}
                stroke={zone.id === selectedZoneId ? '#3b82f6' : '#94a3b8'}
                strokeWidth={zone.id === selectedZoneId ? 2 : 1}
                cornerRadius={4}
                onClick={() => onZoneClick?.(zone)}
                onTap={() => onZoneClick?.(zone)}
              />
              {/* 존 이름 */}
              <Text
                x={minX + 8}
                y={minY + 8}
                text={zone.name}
                fontSize={14}
                fontStyle="bold"
                fill="#475569"
              />
            </Group>
          );
        })}

        {/* 디바이스 렌더링 */}
        {devices.map((device) => {
          const zone = zones.find((z) => z.id === device.zone_id);
          if (!zone) return null;

          const coords = zone.coordinates as Array<{ x: number; y: number }>;
          if (!coords || coords.length < 2) return null;

          const centerX = coords.reduce((sum, c) => sum + c.x, 0) / coords.length;
          const centerY = coords.reduce((sum, c) => sum + c.y, 0) / coords.length;

          return (
            <Group key={device.id}>
              {/* 디바이스 아이콘 */}
              <Circle
                x={centerX}
                y={centerY}
                radius={12}
                fill={STATUS_COLORS[device.status] || '#6b7280'}
                stroke="#ffffff"
                strokeWidth={2}
                shadowBlur={device.status === 'online' ? 8 : 0}
                shadowColor={STATUS_COLORS[device.status]}
                onClick={() => onDeviceClick?.(device)}
                onTap={() => onDeviceClick?.(device)}
              />
              {/* 디바이스 이름 */}
              <Text
                x={centerX - 30}
                y={centerY + 18}
                text={device.name}
                fontSize={10}
                fill="#64748b"
                align="center"
                width={60}
              />
            </Group>
          );
        })}
      </Layer>
    </Stage>
  );
};
```

### 단계 6.11 - Observatory Bridge 컴포넌트

**도구**: `Write`

파일 경로: `D:/home/ruView/apps/web-monitor/src/components/ObservatoryBridge.tsx`

```tsx
import React, { useEffect, useRef, useState } from 'react';
import type { ObservatoryConfig, ObservatoryEvent } from '@ruview/shared-types';

interface ObservatoryBridgeProps {
  config: ObservatoryConfig;
  onEvent?: (event: ObservatoryEvent) => void;
  className?: string;
}

/**
 * RuView Three.js Observatory를 iframe으로 임베딩하고,
 * postMessage API를 통해 양방향 통신을 수행하는 브릿지 컴포넌트.
 *
 * Observatory는 vendor/ruview-upstream에서 별도로 빌드되어
 * 정적 파일로 서빙됩니다.
 */
export const ObservatoryBridge: React.FC<ObservatoryBridgeProps> = ({
  config,
  onEvent,
  className,
}) => {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [isReady, setIsReady] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Observatory iframe으로부터 메시지 수신
  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      // origin 검증 (프로덕션에서는 실제 도메인으로 교체)
      // if (event.origin !== expectedOrigin) return;

      try {
        const data = event.data;

        if (data.type === 'observatory:ready') {
          setIsReady(true);
          // 초기 설정 전송
          sendToObservatory('config', config);
        } else if (data.type === 'observatory:event') {
          onEvent?.(data.payload as ObservatoryEvent);
        } else if (data.type === 'observatory:error') {
          setError(data.payload?.message || 'Observatory 오류');
        }
      } catch (err) {
        console.error('Observatory 메시지 처리 오류:', err);
      }
    };

    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, [config, onEvent]);

  // Observatory iframe으로 메시지 전송
  const sendToObservatory = (type: string, payload: unknown) => {
    if (iframeRef.current?.contentWindow) {
      iframeRef.current.contentWindow.postMessage(
        { type: `monitor:${type}`, payload },
        '*' // 프로덕션에서는 특정 origin으로 제한
      );
    }
  };

  // config 변경 시 Observatory에 전달
  useEffect(() => {
    if (isReady) {
      sendToObservatory('config', config);
    }
  }, [config, isReady]);

  // 존/디바이스 데이터 업데이트 메서드
  const updateZones = (zones: ObservatoryConfig['zones']) => {
    sendToObservatory('zones:update', zones);
  };

  const updateDevices = (devices: ObservatoryConfig['devices']) => {
    sendToObservatory('devices:update', devices);
  };

  const highlightZone = (zoneId: string) => {
    sendToObservatory('zone:highlight', { zoneId });
  };

  return (
    <div className={`relative ${className || ''}`}>
      {!isReady && (
        <div className="absolute inset-0 flex items-center justify-center bg-muted/50 z-10">
          <div className="text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-2" />
            <p className="text-sm text-muted-foreground">Observatory 로딩 중...</p>
          </div>
        </div>
      )}

      {error && (
        <div className="absolute top-2 right-2 bg-destructive/10 text-destructive text-sm px-3 py-1 rounded z-20">
          {error}
        </div>
      )}

      <iframe
        ref={iframeRef}
        src="/observatory/index.html"
        title="RuView Observatory"
        className="w-full h-full border-0"
        sandbox="allow-scripts allow-same-origin"
      />
    </div>
  );
};

// Hook으로도 제공
export function useObservatoryBridge() {
  const [isReady, setIsReady] = useState(false);

  const sendMessage = (type: string, payload: unknown) => {
    const iframe = document.querySelector(
      'iframe[title="RuView Observatory"]'
    ) as HTMLIFrameElement;
    iframe?.contentWindow?.postMessage(
      { type: `monitor:${type}`, payload },
      '*'
    );
  };

  return { isReady, sendMessage };
}
```

### 단계 6.12 - 페이지 컴포넌트

**도구**: `Write`

파일 경로: `D:/home/ruView/apps/web-monitor/src/pages/DashboardPage.tsx`

```tsx
import React, { useEffect, useState } from 'react';
import { FloorMap } from '@/components/FloorMap';
import { useDeviceStore } from '@/stores/deviceStore';
import { useEventStore } from '@/stores/eventStore';
import type { Zone, Device } from '@ruview/shared-types';

export const DashboardPage: React.FC = () => {
  const { devices, fetchDevices, subscribeToChanges } = useDeviceStore();
  const { events, alerts, unacknowledgedCount, fetchRecentEvents, fetchAlerts, subscribeToEvents, subscribeToAlerts } = useEventStore();
  const [selectedZoneId, setSelectedZoneId] = useState<string | null>(null);

  useEffect(() => {
    fetchDevices();
    fetchRecentEvents();
    fetchAlerts();

    const unsubDevices = subscribeToChanges();
    const unsubEvents = subscribeToEvents();
    const unsubAlerts = subscribeToAlerts();

    return () => {
      unsubDevices();
      unsubEvents();
      unsubAlerts();
    };
  }, []);

  // TODO: zones는 별도 스토어에서 관리
  const zones: Zone[] = [];

  return (
    <div className="flex h-screen bg-background">
      {/* 사이드바 */}
      <aside className="w-64 border-r bg-card p-4 overflow-y-auto">
        <h2 className="text-lg font-semibold mb-4">디바이스</h2>
        <div className="space-y-2">
          {devices.map((device) => (
            <div
              key={device.id}
              className="flex items-center gap-2 p-2 rounded-md hover:bg-accent cursor-pointer"
            >
              <div
                className={`w-2 h-2 rounded-full ${
                  device.status === 'online'
                    ? 'bg-green-500'
                    : device.status === 'error'
                    ? 'bg-red-500'
                    : 'bg-gray-400'
                }`}
              />
              <span className="text-sm">{device.name}</span>
            </div>
          ))}
        </div>

        <h2 className="text-lg font-semibold mt-6 mb-4">
          알림
          {unacknowledgedCount > 0 && (
            <span className="ml-2 bg-destructive text-destructive-foreground text-xs px-2 py-0.5 rounded-full">
              {unacknowledgedCount}
            </span>
          )}
        </h2>
        <div className="space-y-2">
          {alerts.slice(0, 10).map((alert) => (
            <div
              key={alert.id}
              className={`p-2 rounded-md text-sm ${
                !alert.acknowledged
                  ? 'bg-destructive/10 border border-destructive/20'
                  : 'bg-muted'
              }`}
            >
              <p className="font-medium">{alert.message}</p>
              <p className="text-xs text-muted-foreground mt-1">
                {new Date(alert.created_at).toLocaleString('ko-KR')}
              </p>
            </div>
          ))}
        </div>
      </aside>

      {/* 메인 영역 */}
      <main className="flex-1 p-6">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold">RuView 관제 대시보드</h1>
          <div className="flex items-center gap-4">
            <span className="text-sm text-muted-foreground">
              디바이스: {devices.filter((d) => d.status === 'online').length}/{devices.length}
            </span>
          </div>
        </div>

        {/* Floor Map */}
        <div className="bg-card rounded-lg border p-4 mb-6">
          <h3 className="text-sm font-medium mb-3">평면도</h3>
          <FloorMap
            width={800}
            height={500}
            zones={zones}
            devices={devices}
            activeEvents={events.slice(0, 20)}
            selectedZoneId={selectedZoneId}
            onZoneClick={(zone) => setSelectedZoneId(zone.id)}
          />
        </div>

        {/* 최근 이벤트 */}
        <div className="bg-card rounded-lg border p-4">
          <h3 className="text-sm font-medium mb-3">최근 이벤트</h3>
          <div className="space-y-1 max-h-64 overflow-y-auto">
            {events.slice(0, 20).map((event) => (
              <div
                key={event.id}
                className="flex items-center gap-3 py-1.5 text-sm border-b last:border-0"
              >
                <span className="w-32 text-muted-foreground">
                  {new Date(event.timestamp).toLocaleTimeString('ko-KR')}
                </span>
                <span className="font-mono text-xs bg-muted px-1.5 py-0.5 rounded">
                  {event.event_type}
                </span>
                <span className="text-muted-foreground">
                  confidence: {(event.confidence * 100).toFixed(0)}%
                </span>
              </div>
            ))}
          </div>
        </div>
      </main>
    </div>
  );
};
```

### 단계 6.13 - App.tsx 및 라우터 설정

**도구**: `Write`

파일 경로: `D:/home/ruView/apps/web-monitor/src/App.tsx`

```tsx
import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { DashboardPage } from '@/pages/DashboardPage';

const App: React.FC = () => {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        {/* TODO: 추가 라우트 */}
        {/* <Route path="/devices" element={<DevicesPage />} /> */}
        {/* <Route path="/zones" element={<ZonesPage />} /> */}
        {/* <Route path="/observatory" element={<ObservatoryPage />} /> */}
        {/* <Route path="/settings" element={<SettingsPage />} /> */}
      </Routes>
    </BrowserRouter>
  );
};

export default App;
```

**도구**: `Write`

파일 경로: `D:/home/ruView/apps/web-monitor/src/main.tsx`

```tsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './styles/globals.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

### 단계 6.14 - .env.example

**도구**: `Write`

파일 경로: `D:/home/ruView/apps/web-monitor/.env.example`

```bash
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIs...
VITE_API_BASE_URL=http://localhost:8000
VITE_API_WS_URL=ws://localhost:8000/ws
VITE_ENVIRONMENT=development
```

---

## Phase 7: Python Signal Adapter (services/signal-adapter)

> **완료 기준**: FastAPI 앱이 실행되고, RuView WebSocket 수신, 이벤트 추상화, Supabase 적재가 동작

### 단계 7.1 - Python 프로젝트 구조 설정

**도구**: `Write`

파일 경로: `D:/home/ruView/services/signal-adapter/pyproject.toml`

```toml
[project]
name = "ruview-signal-adapter"
version = "0.1.0"
description = "RuView Signal Adapter - CSI signal processing and event abstraction"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.111.0",
    "uvicorn[standard]>=0.29.0",
    "websockets>=12.0",
    "httpx>=0.27.0",
    "supabase>=2.4.0",
    "pydantic>=2.7.0",
    "pydantic-settings>=2.2.0",
    "numpy>=1.26.0",
    "scipy>=1.13.0",
    "python-dotenv>=1.0.0",
    "structlog>=24.1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.1.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=5.0.0",
    "ruff>=0.4.0",
    "mypy>=1.10.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

### 단계 7.2 - 설정 모듈

**도구**: `Write`

파일 경로: `D:/home/ruView/services/signal-adapter/src/__init__.py`

```python
```

**도구**: `Write`

파일 경로: `D:/home/ruView/services/signal-adapter/src/core/__init__.py`

```python
```

**도구**: `Write`

파일 경로: `D:/home/ruView/services/signal-adapter/src/core/config.py`

```python
"""Signal Adapter 설정."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """애플리케이션 설정.

    환경변수 또는 .env 파일에서 로드됩니다.
    """

    # App
    app_name: str = "RuView Signal Adapter"
    app_version: str = "0.1.0"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8001

    # RuView Sensing Server WebSocket
    ruview_ws_url: str = "ws://localhost:9000/ws"
    ruview_reconnect_interval: float = 3.0
    ruview_max_reconnect_attempts: int = 50

    # Supabase
    supabase_url: str = ""
    supabase_service_role_key: str = ""

    # Signal Processing
    csi_window_size: int = 50  # CSI 윈도우 크기 (샘플 수)
    fall_confidence_threshold: float = 0.7
    presence_confidence_threshold: float = 0.5
    signal_log_batch_size: int = 10  # 배치 적재 크기
    signal_log_flush_interval: float = 2.0  # 배치 플러시 간격 (초)

    # API Gateway
    api_gateway_url: str = "http://localhost:8000"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


settings = Settings()
```

### 단계 7.3 - 이벤트 모델

**도구**: `Write`

파일 경로: `D:/home/ruView/services/signal-adapter/src/models/__init__.py`

```python
```

**도구**: `Write`

파일 경로: `D:/home/ruView/services/signal-adapter/src/models/events.py`

```python
"""이벤트 및 신호 데이터 모델."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class EventType(str, Enum):
    PRESENCE_DETECTED = "presence_detected"
    PRESENCE_LOST = "presence_lost"
    FALL_DETECTED = "fall_detected"
    FALL_CONFIRMED = "fall_confirmed"
    MOVEMENT_DETECTED = "movement_detected"
    BREATHING_DETECTED = "breathing_detected"
    ZONE_ENTER = "zone_enter"
    ZONE_EXIT = "zone_exit"


class RawCSIData(BaseModel):
    """RuView에서 수신한 원본 CSI 데이터."""

    device_id: str
    mac_address: str
    csi_values: list[float]
    rssi: float
    noise_floor: float | None = None
    subcarrier_count: int = 52
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProcessedSignal(BaseModel):
    """전처리된 신호 데이터."""

    device_id: str
    amplitude: list[float]
    phase: list[float]
    rssi: float
    noise_floor: float | None = None
    features: dict[str, float] = Field(default_factory=dict)
    timestamp: datetime


class SensingEvent(BaseModel):
    """감지 이벤트."""

    device_id: str
    zone_id: str | None = None
    event_type: EventType
    confidence: float = Field(ge=0.0, le=1.0)
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SignalLogEntry(BaseModel):
    """Supabase에 적재할 신호 로그."""

    device_id: str
    raw_csi: list[float]
    amplitude: list[float]
    phase: list[float]
    rssi: float
    noise_floor: float | None = None
    subcarrier_count: int = 52
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime
```

### 단계 7.4 - 신호 처리 엔진

**도구**: `Write`

파일 경로: `D:/home/ruView/services/signal-adapter/src/core/signal_processor.py`

```python
"""CSI 신호 처리 및 이벤트 추상화 엔진."""

import numpy as np
import structlog
from collections import deque

from ..models.events import (
    EventType,
    ProcessedSignal,
    RawCSIData,
    SensingEvent,
)
from .config import settings

logger = structlog.get_logger()


class SignalProcessor:
    """CSI 신호를 처리하여 이벤트를 생성하는 엔진.

    알고리즘 개요:
    1. 원본 CSI → 진폭/위상 분리
    2. 슬라이딩 윈도우에서 통계 특징 추출
    3. 특징 기반 이벤트 분류 (규칙 기반, 추후 ML로 교체)
    """

    def __init__(self):
        self.window_size = settings.csi_window_size
        self.fall_threshold = settings.fall_confidence_threshold
        self.presence_threshold = settings.presence_confidence_threshold

        # 디바이스별 슬라이딩 윈도우
        self._windows: dict[str, deque[ProcessedSignal]] = {}
        # 디바이스별 이전 상태
        self._prev_state: dict[str, str] = {}

    def _get_window(self, device_id: str) -> deque[ProcessedSignal]:
        if device_id not in self._windows:
            self._windows[device_id] = deque(maxlen=self.window_size)
        return self._windows[device_id]

    def extract_amplitude_phase(self, csi_values: list[float]) -> tuple[list[float], list[float]]:
        """CSI 복소수 값에서 진폭과 위상을 분리.

        CSI 데이터가 [I1, Q1, I2, Q2, ...] 형식이라고 가정.
        """
        if len(csi_values) < 2:
            return [], []

        amplitude = []
        phase = []

        for i in range(0, len(csi_values) - 1, 2):
            real = csi_values[i]
            imag = csi_values[i + 1]
            amp = np.sqrt(real**2 + imag**2)
            ph = np.arctan2(imag, real)
            amplitude.append(float(amp))
            phase.append(float(ph))

        return amplitude, phase

    def process_raw(self, raw: RawCSIData) -> ProcessedSignal:
        """원본 CSI 데이터를 전처리."""
        amplitude, phase = self.extract_amplitude_phase(raw.csi_values)

        processed = ProcessedSignal(
            device_id=raw.device_id,
            amplitude=amplitude,
            phase=phase,
            rssi=raw.rssi,
            noise_floor=raw.noise_floor,
            timestamp=raw.timestamp,
            features={},
        )

        # 윈도우에 추가
        window = self._get_window(raw.device_id)
        window.append(processed)

        # 특징 추출
        if len(window) >= 5:
            processed.features = self._extract_features(window)

        return processed

    def _extract_features(self, window: deque[ProcessedSignal]) -> dict[str, float]:
        """슬라이딩 윈도우에서 통계 특징 추출."""
        amplitudes = [s.amplitude for s in window if s.amplitude]
        if not amplitudes:
            return {}

        # 서브캐리어별 평균 진폭 시계열
        min_len = min(len(a) for a in amplitudes)
        if min_len == 0:
            return {}

        amp_matrix = np.array([a[:min_len] for a in amplitudes])

        # 특징
        mean_amp = float(np.mean(amp_matrix))
        std_amp = float(np.std(amp_matrix))
        variance_over_time = float(np.mean(np.var(amp_matrix, axis=0)))
        max_change = float(np.max(np.abs(np.diff(amp_matrix, axis=0)))) if len(amp_matrix) > 1 else 0.0

        # RSSI 변화
        rssi_values = [s.rssi for s in window]
        rssi_std = float(np.std(rssi_values))

        return {
            "mean_amplitude": mean_amp,
            "std_amplitude": std_amp,
            "variance_over_time": variance_over_time,
            "max_change": max_change,
            "rssi_std": rssi_std,
            "window_size": float(len(window)),
        }

    def detect_events(self, processed: ProcessedSignal) -> list[SensingEvent]:
        """전처리된 신호에서 이벤트를 감지.

        규칙 기반 분류 (MVP). 추후 ML 모델로 교체 예정.
        """
        events: list[SensingEvent] = []
        features = processed.features

        if not features:
            return events

        device_id = processed.device_id
        prev_state = self._prev_state.get(device_id, "unknown")

        variance = features.get("variance_over_time", 0)
        max_change = features.get("max_change", 0)
        mean_amp = features.get("mean_amplitude", 0)

        # ----- 낙상 감지 -----
        # 급격한 진폭 변화 후 안정화
        if max_change > 50 and variance > 30:
            confidence = min(1.0, max_change / 100.0)
            if confidence >= self.fall_threshold:
                events.append(
                    SensingEvent(
                        device_id=device_id,
                        event_type=EventType.FALL_DETECTED,
                        confidence=confidence,
                        payload={
                            "max_change": max_change,
                            "variance": variance,
                        },
                        timestamp=processed.timestamp,
                    )
                )
                logger.warning("낙상 감지", device_id=device_id, confidence=confidence)

        # ----- 재실 감지 -----
        if variance > 5 and mean_amp > 10:
            confidence = min(1.0, variance / 20.0)
            if confidence >= self.presence_threshold and prev_state != "presence":
                events.append(
                    SensingEvent(
                        device_id=device_id,
                        event_type=EventType.PRESENCE_DETECTED,
                        confidence=confidence,
                        payload={"variance": variance, "mean_amplitude": mean_amp},
                        timestamp=processed.timestamp,
                    )
                )
                self._prev_state[device_id] = "presence"
        elif variance < 2 and prev_state == "presence":
            events.append(
                SensingEvent(
                    device_id=device_id,
                    event_type=EventType.PRESENCE_LOST,
                    confidence=0.8,
                    payload={"variance": variance},
                    timestamp=processed.timestamp,
                )
            )
            self._prev_state[device_id] = "empty"

        # ----- 움직임 감지 -----
        if 10 < variance < 30 and mean_amp > 10:
            events.append(
                SensingEvent(
                    device_id=device_id,
                    event_type=EventType.MOVEMENT_DETECTED,
                    confidence=min(1.0, variance / 30.0),
                    payload={"variance": variance},
                    timestamp=processed.timestamp,
                )
            )

        return events
```

### 단계 7.5 - Supabase 어댑터

**도구**: `Write`

파일 경로: `D:/home/ruView/services/signal-adapter/src/adapters/__init__.py`

```python
```

**도구**: `Write`

파일 경로: `D:/home/ruView/services/signal-adapter/src/adapters/supabase_adapter.py`

```python
"""Supabase 데이터 적재 어댑터."""

import asyncio
from collections import deque
from datetime import datetime

import structlog
from supabase import create_client, Client

from ..core.config import settings
from ..models.events import SensingEvent, SignalLogEntry

logger = structlog.get_logger()


class SupabaseAdapter:
    """Supabase에 이벤트와 신호 로그를 적재하는 어댑터."""

    def __init__(self):
        self._client: Client | None = None
        self._signal_buffer: deque[dict] = deque()
        self._flush_task: asyncio.Task | None = None

    async def connect(self):
        """Supabase 클라이언트 초기화."""
        if not settings.supabase_url or not settings.supabase_service_role_key:
            logger.warning("Supabase 설정이 없습니다. 데이터 적재가 비활성화됩니다.")
            return

        self._client = create_client(
            settings.supabase_url,
            settings.supabase_service_role_key,
        )
        logger.info("Supabase 연결 완료")

        # 배치 플러시 태스크 시작
        self._flush_task = asyncio.create_task(self._periodic_flush())

    async def disconnect(self):
        """연결 해제 및 잔여 버퍼 플러시."""
        if self._flush_task:
            self._flush_task.cancel()
        await self._flush_signal_buffer()

    async def insert_event(self, event: SensingEvent) -> dict | None:
        """이벤트를 events 테이블에 삽입."""
        if not self._client:
            logger.debug("Supabase 미연결, 이벤트 스킵", event_type=event.event_type)
            return None

        try:
            data = {
                "device_id": event.device_id,
                "zone_id": event.zone_id,
                "event_type": event.event_type.value,
                "confidence": event.confidence,
                "payload": event.payload,
                "timestamp": event.timestamp.isoformat(),
            }

            result = self._client.table("events").insert(data).execute()
            logger.info(
                "이벤트 적재 완료",
                event_type=event.event_type,
                device_id=event.device_id,
            )
            return result.data[0] if result.data else None

        except Exception as e:
            logger.error("이벤트 적재 실패", error=str(e))
            return None

    async def buffer_signal_log(self, entry: SignalLogEntry):
        """신호 로그를 버퍼에 추가 (배치 적재)."""
        self._signal_buffer.append({
            "device_id": entry.device_id,
            "raw_csi": entry.raw_csi,
            "amplitude": entry.amplitude,
            "phase": entry.phase,
            "rssi": entry.rssi,
            "noise_floor": entry.noise_floor,
            "subcarrier_count": entry.subcarrier_count,
            "metadata": entry.metadata,
            "timestamp": entry.timestamp.isoformat(),
        })

        if len(self._signal_buffer) >= settings.signal_log_batch_size:
            await self._flush_signal_buffer()

    async def _flush_signal_buffer(self):
        """버퍼에 쌓인 신호 로그를 일괄 적재."""
        if not self._client or not self._signal_buffer:
            return

        batch = list(self._signal_buffer)
        self._signal_buffer.clear()

        try:
            self._client.table("signal_logs").insert(batch).execute()
            logger.debug("신호 로그 배치 적재 완료", count=len(batch))
        except Exception as e:
            logger.error("신호 로그 배치 적재 실패", error=str(e), count=len(batch))
            # 실패한 데이터를 다시 버퍼에 넣지 않음 (데이터 유실 허용, MVP 단계)

    async def _periodic_flush(self):
        """주기적으로 신호 버퍼를 플러시."""
        while True:
            await asyncio.sleep(settings.signal_log_flush_interval)
            await self._flush_signal_buffer()

    async def update_device_status(self, device_id: str, status: str):
        """디바이스 상태 업데이트."""
        if not self._client:
            return

        try:
            self._client.table("devices").update({
                "status": status,
                "last_seen_at": datetime.utcnow().isoformat(),
            }).eq("id", device_id).execute()
        except Exception as e:
            logger.error("디바이스 상태 업데이트 실패", error=str(e))
```

### 단계 7.6 - RuView WebSocket 수신기

**도구**: `Write`

파일 경로: `D:/home/ruView/services/signal-adapter/src/adapters/ruview_receiver.py`

```python
"""RuView Sensing Server WebSocket 수신기."""

import asyncio
import json

import structlog
import websockets
from websockets.exceptions import ConnectionClosed

from ..core.config import settings
from ..core.signal_processor import SignalProcessor
from ..models.events import RawCSIData, SignalLogEntry
from .supabase_adapter import SupabaseAdapter

logger = structlog.get_logger()


class RuViewReceiver:
    """RuView Sensing Server의 WebSocket에서 CSI 데이터를 수신하고 처리."""

    def __init__(
        self,
        processor: SignalProcessor,
        supabase: SupabaseAdapter,
    ):
        self.processor = processor
        self.supabase = supabase
        self._running = False
        self._reconnect_count = 0

    async def start(self):
        """WebSocket 수신 루프 시작."""
        self._running = True
        logger.info("RuView 수신기 시작", url=settings.ruview_ws_url)

        while self._running:
            try:
                await self._connect_and_receive()
            except ConnectionClosed:
                logger.warning("RuView 연결 종료, 재연결 시도...")
            except Exception as e:
                logger.error("RuView 수신 오류", error=str(e))

            if not self._running:
                break

            self._reconnect_count += 1
            if self._reconnect_count > settings.ruview_max_reconnect_attempts:
                logger.error("최대 재연결 시도 초과")
                break

            await asyncio.sleep(settings.ruview_reconnect_interval)

    async def stop(self):
        """수신 루프 중지."""
        self._running = False

    async def _connect_and_receive(self):
        """WebSocket 연결 및 데이터 수신."""
        async with websockets.connect(settings.ruview_ws_url) as ws:
            logger.info("RuView WebSocket 연결 성공")
            self._reconnect_count = 0

            async for message in ws:
                await self._handle_message(message)

    async def _handle_message(self, message: str):
        """수신한 메시지 처리."""
        try:
            data = json.loads(message)

            # RuView 메시지 형식에 따라 파싱
            # TODO: 실제 RuView 프로토콜에 맞춰 조정
            raw = RawCSIData(
                device_id=data.get("device_id", "unknown"),
                mac_address=data.get("mac", "00:00:00:00:00:00"),
                csi_values=data.get("csi", []),
                rssi=data.get("rssi", -100),
                noise_floor=data.get("noise_floor"),
                subcarrier_count=data.get("subcarrier_count", 52),
                metadata=data.get("metadata", {}),
            )

            # 신호 처리
            processed = self.processor.process_raw(raw)

            # 신호 로그 버퍼에 추가
            log_entry = SignalLogEntry(
                device_id=raw.device_id,
                raw_csi=raw.csi_values,
                amplitude=processed.amplitude,
                phase=processed.phase,
                rssi=raw.rssi,
                noise_floor=raw.noise_floor,
                subcarrier_count=raw.subcarrier_count,
                timestamp=raw.timestamp,
            )
            await self.supabase.buffer_signal_log(log_entry)

            # 이벤트 감지
            events = self.processor.detect_events(processed)
            for event in events:
                await self.supabase.insert_event(event)

                # API Gateway로 이벤트 전달 (WebSocket relay)
                # TODO: 구현

        except json.JSONDecodeError:
            logger.warning("JSON 파싱 실패", message=message[:100])
        except Exception as e:
            logger.error("메시지 처리 오류", error=str(e))
```

### 단계 7.7 - FastAPI 앱

**도구**: `Write`

파일 경로: `D:/home/ruView/services/signal-adapter/src/api/__init__.py`

```python
```

**도구**: `Write`

파일 경로: `D:/home/ruView/services/signal-adapter/src/api/app.py`

```python
"""Signal Adapter FastAPI 애플리케이션."""

import asyncio
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..adapters.ruview_receiver import RuViewReceiver
from ..adapters.supabase_adapter import SupabaseAdapter
from ..core.config import settings
from ..core.signal_processor import SignalProcessor

logger = structlog.get_logger()

# 전역 인스턴스
processor = SignalProcessor()
supabase_adapter = SupabaseAdapter()
receiver = RuViewReceiver(processor, supabase_adapter)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 시 리소스 관리."""
    # Startup
    logger.info("Signal Adapter 시작", version=settings.app_version)
    await supabase_adapter.connect()

    # RuView 수신기를 백그라운드 태스크로 시작
    receiver_task = asyncio.create_task(receiver.start())

    yield

    # Shutdown
    logger.info("Signal Adapter 종료")
    await receiver.stop()
    await supabase_adapter.disconnect()
    receiver_task.cancel()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프로덕션에서는 제한
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    """헬스 체크."""
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
    }


@app.get("/status")
async def status():
    """서비스 상태."""
    return {
        "ruview_connected": receiver._running and receiver._reconnect_count == 0,
        "supabase_connected": supabase_adapter._client is not None,
        "window_devices": list(processor._windows.keys()),
        "signal_buffer_size": len(supabase_adapter._signal_buffer),
    }
```

### 단계 7.8 - 진입점

**도구**: `Write`

파일 경로: `D:/home/ruView/services/signal-adapter/src/main.py`

```python
"""Signal Adapter 진입점."""

import uvicorn

from .core.config import settings


def main():
    uvicorn.run(
        "src.api.app:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info",
    )


if __name__ == "__main__":
    main()
```

### 단계 7.9 - Dockerfile

**도구**: `Write`

파일 경로: `D:/home/ruView/services/signal-adapter/Dockerfile`

```dockerfile
FROM python:3.11-slim AS builder

WORKDIR /app

# 시스템 의존성
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성 설치
COPY pyproject.toml .
RUN pip install --no-cache-dir .

FROM python:3.11-slim

WORKDIR /app

# 런타임 의존성만 복사
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY src/ ./src/

EXPOSE 8001

CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8001"]
```

### 단계 7.10 - .env.example

**도구**: `Write`

파일 경로: `D:/home/ruView/services/signal-adapter/.env.example`

```bash
# Signal Adapter 환경변수
DEBUG=true
HOST=0.0.0.0
PORT=8001

# RuView Sensing Server
RUVIEW_WS_URL=ws://localhost:9000/ws

# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIs...

# Signal Processing
CSI_WINDOW_SIZE=50
FALL_CONFIDENCE_THRESHOLD=0.7
PRESENCE_CONFIDENCE_THRESHOLD=0.5
```

### 단계 7.11 - 테스트

**도구**: `Write`

파일 경로: `D:/home/ruView/services/signal-adapter/tests/__init__.py`

```python
```

**도구**: `Write`

파일 경로: `D:/home/ruView/services/signal-adapter/tests/test_signal_processor.py`

```python
"""Signal Processor 단위 테스트."""

import pytest
from datetime import datetime

from src.core.signal_processor import SignalProcessor
from src.models.events import RawCSIData, EventType


@pytest.fixture
def processor():
    return SignalProcessor()


def make_raw_csi(device_id: str = "test-device", csi_values: list[float] | None = None) -> RawCSIData:
    """테스트용 CSI 데이터 생성."""
    if csi_values is None:
        # I/Q 쌍으로 26개 서브캐리어 (52개 값)
        import random
        csi_values = [random.uniform(-50, 50) for _ in range(52)]

    return RawCSIData(
        device_id=device_id,
        mac_address="AA:BB:CC:DD:EE:01",
        csi_values=csi_values,
        rssi=-45.0,
        timestamp=datetime.utcnow(),
    )


class TestSignalProcessor:
    def test_extract_amplitude_phase(self, processor: SignalProcessor):
        """진폭/위상 분리 테스트."""
        csi = [3.0, 4.0, 1.0, 0.0]  # (3+4j), (1+0j)
        amplitude, phase = processor.extract_amplitude_phase(csi)

        assert len(amplitude) == 2
        assert len(phase) == 2
        assert abs(amplitude[0] - 5.0) < 0.01  # sqrt(9+16)
        assert abs(amplitude[1] - 1.0) < 0.01  # sqrt(1+0)

    def test_process_raw(self, processor: SignalProcessor):
        """원본 CSI 처리 테스트."""
        raw = make_raw_csi()
        processed = processor.process_raw(raw)

        assert processed.device_id == "test-device"
        assert len(processed.amplitude) > 0
        assert len(processed.phase) > 0

    def test_window_accumulation(self, processor: SignalProcessor):
        """윈도우 축적 테스트."""
        for _ in range(10):
            raw = make_raw_csi()
            processor.process_raw(raw)

        window = processor._get_window("test-device")
        assert len(window) == 10

    def test_feature_extraction(self, processor: SignalProcessor):
        """특징 추출 테스트 (윈도우 5개 이상)."""
        for _ in range(6):
            raw = make_raw_csi()
            processed = processor.process_raw(raw)

        assert "mean_amplitude" in processed.features
        assert "std_amplitude" in processed.features
        assert "variance_over_time" in processed.features
```

---

## Phase 8: API Gateway (apps/api-gateway)

> **완료 기준**: FastAPI 기반 API Gateway가 실행되고, REST endpoint, WebSocket relay, 기본 인증 미들웨어가 구현됨

### 단계 8.1 - API Gateway 프로젝트 설정

**도구**: `Write`

파일 경로: `D:/home/ruView/apps/api-gateway/package.json`

```json
{
  "name": "@ruview/api-gateway",
  "version": "0.1.0",
  "private": true,
  "description": "RuView API Gateway - REST + WebSocket relay"
}
```

> API Gateway는 Python (FastAPI) 기반으로 구현한다.

**도구**: `Write`

파일 경로: `D:/home/ruView/apps/api-gateway/pyproject.toml`

```toml
[project]
name = "ruview-api-gateway"
version = "0.1.0"
description = "RuView API Gateway - REST endpoints and WebSocket relay"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.111.0",
    "uvicorn[standard]>=0.29.0",
    "supabase>=2.4.0",
    "pydantic>=2.7.0",
    "pydantic-settings>=2.2.0",
    "python-dotenv>=1.0.0",
    "python-jose[cryptography]>=3.3.0",
    "httpx>=0.27.0",
    "structlog>=24.1.0",
    "websockets>=12.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.1.0",
    "pytest-asyncio>=0.23.0",
    "ruff>=0.4.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

### 단계 8.2 - API Gateway 설정

**도구**: `Write`

파일 경로: `D:/home/ruView/apps/api-gateway/src/__init__.py`

```python
```

**도구**: `Write`

파일 경로: `D:/home/ruView/apps/api-gateway/src/config.py`

```python
"""API Gateway 설정."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "RuView API Gateway"
    app_version: str = "0.1.0"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000

    # Supabase
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""

    # JWT (Supabase JWT)
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"

    # Signal Adapter
    signal_adapter_url: str = "http://localhost:8001"

    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


settings = Settings()
```

### 단계 8.3 - 인증 미들웨어

**도구**: `Write`

파일 경로: `D:/home/ruView/apps/api-gateway/src/middleware/__init__.py`

```python
```

**도구**: `Write`

파일 경로: `D:/home/ruView/apps/api-gateway/src/middleware/auth.py`

```python
"""인증 미들웨어.

MVP 단계에서는 Supabase anon key 또는 API key 기반 인증을 사용합니다.
Phase 2에서 JWT 기반 사용자 인증으로 전환합니다.
"""

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from ..config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str | None = Security(api_key_header)) -> str:
    """API 키 검증.

    MVP 단계에서는 Supabase anon key를 API key로 사용합니다.
    """
    if not api_key:
        # MVP: API key 없이도 접근 허용 (개발 편의)
        if settings.debug:
            return "anonymous"
        raise HTTPException(status_code=401, detail="API key가 필요합니다")

    if api_key == settings.supabase_anon_key:
        return "supabase_anon"

    if settings.debug:
        return "debug"

    raise HTTPException(status_code=403, detail="유효하지 않은 API key입니다")
```

### 단계 8.4 - REST 라우트

**도구**: `Write`

파일 경로: `D:/home/ruView/apps/api-gateway/src/routes/__init__.py`

```python
```

**도구**: `Write`

파일 경로: `D:/home/ruView/apps/api-gateway/src/routes/devices.py`

```python
"""디바이스 관련 REST 엔드포인트."""

from fastapi import APIRouter, Depends, HTTPException
from supabase import create_client

from ..config import settings
from ..middleware.auth import verify_api_key

router = APIRouter(prefix="/api/v1/devices", tags=["devices"])


def get_supabase():
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


@router.get("")
async def list_devices(user: str = Depends(verify_api_key)):
    """디바이스 목록 조회."""
    client = get_supabase()
    result = client.table("devices").select("*").order("name").execute()
    return {"data": result.data, "count": len(result.data)}


@router.get("/{device_id}")
async def get_device(device_id: str, user: str = Depends(verify_api_key)):
    """디바이스 상세 조회."""
    client = get_supabase()
    result = client.table("devices").select("*").eq("id", device_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="디바이스를 찾을 수 없습니다")
    return {"data": result.data}


@router.get("/{device_id}/events")
async def get_device_events(
    device_id: str,
    limit: int = 50,
    user: str = Depends(verify_api_key),
):
    """디바이스의 최근 이벤트 조회."""
    client = get_supabase()
    result = (
        client.table("events")
        .select("*")
        .eq("device_id", device_id)
        .order("timestamp", desc=True)
        .limit(limit)
        .execute()
    )
    return {"data": result.data, "count": len(result.data)}
```

**도구**: `Write`

파일 경로: `D:/home/ruView/apps/api-gateway/src/routes/zones.py`

```python
"""존 관련 REST 엔드포인트."""

from fastapi import APIRouter, Depends, HTTPException
from supabase import create_client

from ..config import settings
from ..middleware.auth import verify_api_key

router = APIRouter(prefix="/api/v1/zones", tags=["zones"])


def get_supabase():
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


@router.get("")
async def list_zones(user: str = Depends(verify_api_key)):
    """존 목록 조회."""
    client = get_supabase()
    result = client.table("zones").select("*").order("floor").order("name").execute()
    return {"data": result.data, "count": len(result.data)}


@router.get("/{zone_id}")
async def get_zone(zone_id: str, user: str = Depends(verify_api_key)):
    """존 상세 조회."""
    client = get_supabase()
    result = client.table("zones").select("*").eq("id", zone_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="존을 찾을 수 없습니다")
    return {"data": result.data}


@router.get("/{zone_id}/devices")
async def get_zone_devices(zone_id: str, user: str = Depends(verify_api_key)):
    """존에 속한 디바이스 조회."""
    client = get_supabase()
    result = client.table("devices").select("*").eq("zone_id", zone_id).execute()
    return {"data": result.data, "count": len(result.data)}
```

**도구**: `Write`

파일 경로: `D:/home/ruView/apps/api-gateway/src/routes/events.py`

```python
"""이벤트/알림 관련 REST 엔드포인트."""

from fastapi import APIRouter, Depends, HTTPException
from supabase import create_client

from ..config import settings
from ..middleware.auth import verify_api_key

router = APIRouter(prefix="/api/v1", tags=["events"])


def get_supabase():
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


@router.get("/events")
async def list_events(
    limit: int = 50,
    offset: int = 0,
    event_type: str | None = None,
    user: str = Depends(verify_api_key),
):
    """이벤트 목록 조회."""
    client = get_supabase()
    query = client.table("events").select("*", count="exact")

    if event_type:
        query = query.eq("event_type", event_type)

    result = query.order("timestamp", desc=True).range(offset, offset + limit - 1).execute()
    return {
        "data": result.data,
        "count": len(result.data),
        "total": result.count,
    }


@router.get("/alerts")
async def list_alerts(
    acknowledged: bool | None = None,
    severity: str | None = None,
    limit: int = 50,
    user: str = Depends(verify_api_key),
):
    """알림 목록 조회."""
    client = get_supabase()
    query = client.table("alerts").select("*")

    if acknowledged is not None:
        query = query.eq("acknowledged", acknowledged)
    if severity:
        query = query.eq("severity", severity)

    result = query.order("created_at", desc=True).limit(limit).execute()
    return {"data": result.data, "count": len(result.data)}


@router.patch("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    user: str = Depends(verify_api_key),
):
    """알림 확인 처리."""
    client = get_supabase()
    from datetime import datetime

    result = (
        client.table("alerts")
        .update({
            "acknowledged": True,
            "acknowledged_by": user,
            "acknowledged_at": datetime.utcnow().isoformat(),
        })
        .eq("id", alert_id)
        .execute()
    )

    if not result.data:
        raise HTTPException(status_code=404, detail="알림을 찾을 수 없습니다")

    return {"data": result.data[0]}
```

### 단계 8.5 - WebSocket Relay

**도구**: `Write`

파일 경로: `D:/home/ruView/apps/api-gateway/src/services/__init__.py`

```python
```

**도구**: `Write`

파일 경로: `D:/home/ruView/apps/api-gateway/src/services/ws_manager.py`

```python
"""WebSocket 연결 관리 및 메시지 릴레이."""

import json
from collections import defaultdict

import structlog
from fastapi import WebSocket

logger = structlog.get_logger()


class WebSocketManager:
    """클라이언트 WebSocket 연결을 관리하고, 토픽 기반 메시지를 릴레이."""

    def __init__(self):
        # 토픽별 구독 클라이언트
        self._subscriptions: dict[str, set[WebSocket]] = defaultdict(set)
        # 전체 연결
        self._connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self._connections.add(websocket)
        logger.info("WebSocket 클라이언트 연결", total=len(self._connections))

    def disconnect(self, websocket: WebSocket):
        self._connections.discard(websocket)
        # 모든 토픽에서 구독 제거
        for topic_subs in self._subscriptions.values():
            topic_subs.discard(websocket)
        logger.info("WebSocket 클라이언트 연결 해제", total=len(self._connections))

    def subscribe(self, websocket: WebSocket, topic: str):
        self._subscriptions[topic].add(websocket)
        logger.debug("토픽 구독", topic=topic)

    def unsubscribe(self, websocket: WebSocket, topic: str):
        self._subscriptions[topic].discard(websocket)

    async def broadcast(self, topic: str, message: dict):
        """특정 토픽의 모든 구독자에게 메시지 전송."""
        subscribers = self._subscriptions.get(topic, set())
        dead_connections = set()

        for ws in subscribers:
            try:
                await ws.send_json(message)
            except Exception:
                dead_connections.add(ws)

        # 죽은 연결 정리
        for ws in dead_connections:
            self.disconnect(ws)

    async def broadcast_all(self, message: dict):
        """모든 연결에 메시지 전송."""
        dead_connections = set()

        for ws in self._connections:
            try:
                await ws.send_json(message)
            except Exception:
                dead_connections.add(ws)

        for ws in dead_connections:
            self.disconnect(ws)

    async def handle_client_message(self, websocket: WebSocket, data: str):
        """클라이언트로부터 수신한 메시지 처리."""
        try:
            message = json.loads(data)
            msg_type = message.get("type")

            if msg_type == "subscribe":
                self.subscribe(websocket, message.get("topic", "default"))
            elif msg_type == "unsubscribe":
                self.unsubscribe(websocket, message.get("topic", "default"))
            elif msg_type == "heartbeat":
                await websocket.send_json({"type": "heartbeat", "status": "ok"})
            else:
                logger.debug("알 수 없는 메시지 타입", type=msg_type)

        except json.JSONDecodeError:
            logger.warning("JSON 파싱 실패")


# 싱글톤
ws_manager = WebSocketManager()
```

### 단계 8.6 - API Gateway 메인 앱

**도구**: `Write`

파일 경로: `D:/home/ruView/apps/api-gateway/src/app.py`

```python
"""API Gateway FastAPI 애플리케이션."""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routes import devices, events, zones
from .services.ws_manager import ws_manager

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("API Gateway 시작", version=settings.app_version)
    yield
    logger.info("API Gateway 종료")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# REST 라우트 등록
app.include_router(devices.router)
app.include_router(zones.router)
app.include_router(events.router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": settings.app_name, "version": settings.app_version}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 엔드포인트.

    클라이언트가 연결하면 토픽을 구독하고, 해당 토픽의 이벤트를 실시간으로 수신합니다.
    """
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await ws_manager.handle_client_message(websocket, data)
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
```

### 단계 8.7 - API Gateway Dockerfile

**도구**: `Write`

파일 경로: `D:/home/ruView/apps/api-gateway/Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY src/ ./src/

EXPOSE 8000

CMD ["uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## Phase 9: Docker 통합

> **완료 기준**: docker-compose up으로 전체 로컬 개발 환경이 실행됨

### 단계 9.1 - docker-compose.yml

**도구**: `Write`

파일 경로: `D:/home/ruView/infra/docker/docker-compose.yml`

```yaml
version: "3.9"

services:
  # ===== API Gateway =====
  api-gateway:
    build:
      context: ../../
      dockerfile: apps/api-gateway/Dockerfile
    ports:
      - "8000:8000"
    env_file:
      - ../../.env
    environment:
      - DEBUG=true
      - HOST=0.0.0.0
      - PORT=8000
    depends_on:
      - signal-adapter
    restart: unless-stopped
    networks:
      - ruview-net

  # ===== Signal Adapter =====
  signal-adapter:
    build:
      context: ../../
      dockerfile: services/signal-adapter/Dockerfile
    ports:
      - "8001:8001"
    env_file:
      - ../../.env
    environment:
      - DEBUG=true
      - HOST=0.0.0.0
      - PORT=8001
      - RUVIEW_WS_URL=ws://host.docker.internal:9000/ws
    restart: unless-stopped
    networks:
      - ruview-net
    extra_hosts:
      - "host.docker.internal:host-gateway"

  # ===== Web Monitor (개발 모드) =====
  web-monitor:
    build:
      context: ../../
      dockerfile: infra/docker/Dockerfile.web-dev
    ports:
      - "3000:3000"
    volumes:
      - ../../apps/web-monitor/src:/app/apps/web-monitor/src
      - ../../apps/web-monitor/public:/app/apps/web-monitor/public
    env_file:
      - ../../.env
    environment:
      - VITE_API_BASE_URL=http://localhost:8000
      - VITE_API_WS_URL=ws://localhost:8000/ws
    depends_on:
      - api-gateway
    networks:
      - ruview-net

networks:
  ruview-net:
    driver: bridge
```

### 단계 9.2 - Web Monitor 개발용 Dockerfile

**도구**: `Write`

파일 경로: `D:/home/ruView/infra/docker/Dockerfile.web-dev`

```dockerfile
FROM node:18-alpine

WORKDIR /app

# pnpm 설치
RUN corepack enable && corepack prepare pnpm@9.0.0 --activate

# 워크스페이스 루트 파일 복사
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml* ./

# 패키지 파일 복사
COPY packages/ ./packages/
COPY apps/web-monitor/package.json ./apps/web-monitor/

# 의존성 설치
RUN pnpm install --frozen-lockfile || pnpm install

# 소스 복사
COPY apps/web-monitor/ ./apps/web-monitor/

WORKDIR /app/apps/web-monitor

EXPOSE 3000

CMD ["pnpm", "dev", "--host", "0.0.0.0"]
```

---

## Phase 10: GitHub Actions CI/CD

> **완료 기준**: push/PR 시 lint, test, build가 실행되고, main 머지 시 Cloudflare Pages 배포가 트리거됨

### 단계 10.1 - Lint & Test 워크플로우

**도구**: `Write`

파일 경로: `D:/home/ruView/.github/workflows/ci.yml`

```yaml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  lint:
    name: Lint
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: pnpm/action-setup@v3
        with:
          version: 9

      - uses: actions/setup-node@v4
        with:
          node-version: 18
          cache: pnpm

      - run: pnpm install --frozen-lockfile

      - name: TypeScript 타입 체크
        run: pnpm --filter @ruview/web-monitor exec tsc --noEmit

      - name: ESLint
        run: pnpm --filter @ruview/web-monitor lint

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Python lint (ruff)
        run: |
          pip install ruff
          ruff check services/signal-adapter/
          ruff check apps/api-gateway/

  test:
    name: Test
    runs-on: ubuntu-latest
    needs: lint
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Signal Adapter 테스트
        working-directory: services/signal-adapter
        run: |
          pip install -e ".[dev]"
          pytest --cov=src tests/ -v

  build:
    name: Build
    runs-on: ubuntu-latest
    needs: lint
    steps:
      - uses: actions/checkout@v4

      - uses: pnpm/action-setup@v3
        with:
          version: 9

      - uses: actions/setup-node@v4
        with:
          node-version: 18
          cache: pnpm

      - run: pnpm install --frozen-lockfile

      - name: Web Monitor 빌드
        run: pnpm --filter @ruview/web-monitor build
        env:
          VITE_SUPABASE_URL: ${{ secrets.VITE_SUPABASE_URL }}
          VITE_SUPABASE_ANON_KEY: ${{ secrets.VITE_SUPABASE_ANON_KEY }}

      - name: 빌드 아티팩트 업로드
        uses: actions/upload-artifact@v4
        with:
          name: web-monitor-dist
          path: apps/web-monitor/dist/
```

### 단계 10.2 - Cloudflare Pages 배포 워크플로우

**도구**: `Write`

파일 경로: `D:/home/ruView/.github/workflows/deploy-pages.yml`

```yaml
name: Deploy to Cloudflare Pages

on:
  push:
    branches: [main, develop]
    paths:
      - "apps/web-monitor/**"
      - "packages/**"
      - ".github/workflows/deploy-pages.yml"

jobs:
  deploy:
    name: Deploy
    runs-on: ubuntu-latest
    permissions:
      contents: read
      deployments: write

    steps:
      - uses: actions/checkout@v4

      - uses: pnpm/action-setup@v3
        with:
          version: 9

      - uses: actions/setup-node@v4
        with:
          node-version: 18
          cache: pnpm

      - run: pnpm install --frozen-lockfile

      - name: 빌드
        run: pnpm --filter @ruview/web-monitor build
        env:
          VITE_SUPABASE_URL: ${{ secrets.VITE_SUPABASE_URL }}
          VITE_SUPABASE_ANON_KEY: ${{ secrets.VITE_SUPABASE_ANON_KEY }}
          VITE_API_BASE_URL: ${{ github.ref == 'refs/heads/main' && secrets.PROD_API_URL || secrets.DEV_API_URL }}
          VITE_API_WS_URL: ${{ github.ref == 'refs/heads/main' && secrets.PROD_WS_URL || secrets.DEV_WS_URL }}

      - name: Cloudflare Pages 배포
        uses: cloudflare/wrangler-action@v3
        with:
          apiToken: ${{ secrets.CLOUDFLARE_API_TOKEN }}
          accountId: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
          command: pages deploy apps/web-monitor/dist --project-name=ruview-web-monitor --branch=${{ github.ref_name }}
```

### 단계 10.3 - Docker 이미지 빌드 워크플로우

**도구**: `Write`

파일 경로: `D:/home/ruView/.github/workflows/docker-build.yml`

```yaml
name: Docker Build

on:
  push:
    branches: [main]
    paths:
      - "apps/api-gateway/**"
      - "services/signal-adapter/**"
      - "infra/docker/**"

jobs:
  build-api-gateway:
    name: Build API Gateway
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Docker 빌드
        run: |
          docker build -t ruview-api-gateway:latest -f apps/api-gateway/Dockerfile .

  build-signal-adapter:
    name: Build Signal Adapter
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Docker 빌드
        run: |
          docker build -t ruview-signal-adapter:latest -f services/signal-adapter/Dockerfile .
```

---

## Phase 11: 에이전트 문서

> **완료 기준**: 6개 에이전트 각각의 역할, 도구, 입출력, 완료 기준이 문서화됨

### 단계 11.1 - Hardware Agent

**도구**: `Write`

파일 경로: `D:/home/ruView/agents/hardware-agent.md`

```markdown
# Hardware Agent

## 역할
ESP32-S3 기반 CSI 센싱 디바이스의 펌웨어 개발, 배포, 모니터링을 담당합니다.

## 담당 영역
- ESP32-S3 펌웨어 (ESP-IDF / Arduino)
- Wi-Fi CSI 수집 설정
- 시리얼 통신 (COM3, CP2102)
- OTA 업데이트

## 사용 도구
- **PlatformIO**: 펌웨어 빌드 및 업로드
- **ESP-IDF**: CSI 수집 API
- **Bash**: 시리얼 모니터링, 디바이스 플래싱

## 입력
- 하드웨어 사양서 (ESP32-S3 데이터시트)
- CSI 수집 요구사항 (서브캐리어 수, 샘플링 레이트)
- Wi-Fi AP 설정 정보

## 출력
- 컴파일된 펌웨어 바이너리
- CSI 데이터 스트림 (WebSocket)
- 디바이스 상태 리포트

## 완료 기준
- [ ] ESP32-S3가 Wi-Fi AP에 연결되어 CSI 데이터를 수집
- [ ] WebSocket으로 CSI 데이터를 Signal Adapter에 전송
- [ ] 디바이스 상태(온라인/오프라인/에러)가 정확히 보고됨
- [ ] OTA 업데이트 메커니즘 동작
```

### 단계 11.2 - Signal Agent

**도구**: `Write`

파일 경로: `D:/home/ruView/agents/signal-agent.md`

```markdown
# Signal Agent

## 역할
CSI 신호 처리, 이벤트 추상화, 데이터 적재를 담당합니다.

## 담당 영역
- services/signal-adapter 전체
- CSI 신호 전처리 (진폭/위상 분리, 노이즈 필터링)
- 이벤트 감지 엔진 (재실, 낙상, 움직임)
- Supabase 데이터 적재

## 사용 도구
- **Python**: FastAPI, NumPy, SciPy
- **Bash**: 서비스 실행, 테스트
- **Write/Edit**: 코드 작성/수정

## 입력
- ESP32에서 수신한 원본 CSI 데이터 (WebSocket)
- 이벤트 분류 임계값 설정

## 출력
- 전처리된 신호 데이터 (signal_logs 테이블)
- 감지 이벤트 (events 테이블)
- 이벤트 알림 (alerts 테이블)

## 완료 기준
- [ ] RuView WebSocket에서 CSI 데이터 수신 성공
- [ ] 진폭/위상 분리 및 특징 추출 동작
- [ ] 재실/낙상/움직임 이벤트 감지 동작
- [ ] Supabase에 이벤트 및 신호 로그 적재
- [ ] 단위 테스트 커버리지 80% 이상
```

### 단계 11.3 - Frontend Agent

**도구**: `Write`

파일 경로: `D:/home/ruView/agents/frontend-agent.md`

```markdown
# Frontend Agent

## 역할
React 기반 관제 대시보드 UI 개발을 담당합니다.

## 담당 영역
- apps/web-monitor 전체
- 실시간 대시보드 UI
- 2D Floor Map 컴포넌트
- Supabase Realtime 연동
- WebSocket 통신

## 사용 도구
- **Bash**: pnpm 명령, Vite 개발 서버
- **Write/Edit**: React 컴포넌트, 스토어, 훅 작성

## 입력
- UI/UX 디자인 사양
- API 엔드포인트 명세
- Supabase 스키마

## 출력
- 빌드된 정적 웹 앱 (dist/)
- Cloudflare Pages 배포

## 완료 기준
- [ ] 대시보드 페이지에 디바이스 목록, 알림, 이벤트 로그 표시
- [ ] 2D Floor Map에 존과 디바이스 상태 실시간 표시
- [ ] Supabase Realtime으로 이벤트/알림 실시간 수신
- [ ] 반응형 레이아웃 (데스크톱/태블릿)
- [ ] Cloudflare Pages 배포 성공
```

### 단계 11.4 - Observatory Agent

**도구**: `Write`

파일 경로: `D:/home/ruView/agents/observatory-agent.md`

```markdown
# Observatory Agent

## 역할
RuView Three.js Observatory의 통합 및 하이브리드 UI 개발을 담당합니다.

## 담당 영역
- vendor/ruview-upstream (RuView 원본 코드)
- Observatory Bridge 컴포넌트
- Three.js 3D 시각화
- postMessage 기반 양방향 통신

## 사용 도구
- **Bash**: git submodule, 빌드
- **Write/Edit**: Bridge 컴포넌트, Three.js 코드

## 입력
- RuView 오픈소스 코드
- 존/디바이스 데이터
- 실시간 이벤트 스트림

## 출력
- 빌드된 Observatory 정적 파일
- Bridge 컴포넌트 (React)

## 완료 기준
- [ ] RuView Observatory가 iframe으로 임베딩됨
- [ ] postMessage로 관제 앱과 양방향 통신
- [ ] 존/디바이스/이벤트가 3D 뷰에 반영
- [ ] 테마(라이트/다크) 동기화
```

### 단계 11.5 - DevOps Agent

**도구**: `Write`

파일 경로: `D:/home/ruView/agents/devops-agent.md`

```markdown
# DevOps Agent

## 역할
인프라 설정, CI/CD, 배포, 모니터링을 담당합니다.

## 담당 영역
- infra/ 디렉토리 전체
- .github/workflows/
- Cloudflare Pages/Tunnel 설정
- Supabase 프로젝트 관리
- Docker 설정

## 사용 도구
- **Bash**: gh CLI, wrangler, cloudflared, docker-compose
- **Write/Edit**: 워크플로우, Dockerfile, 설정 파일

## 입력
- 인프라 요구사항
- 배포 환경 정보
- 시크릿/환경변수

## 출력
- CI/CD 파이프라인
- 배포된 서비스
- 인프라 설정 문서

## 완료 기준
- [ ] GitHub Actions CI 파이프라인 동작 (lint/test/build)
- [ ] Cloudflare Pages 자동 배포
- [ ] Cloudflare Tunnel 설정 완료
- [ ] Supabase 스키마 마이그레이션 적용
- [ ] Docker Compose로 로컬 환경 실행
```

### 단계 11.6 - QA Agent

**도구**: `Write`

파일 경로: `D:/home/ruView/agents/qa-agent.md`

```markdown
# QA Agent

## 역할
품질 보증, 테스트, 문서 관리를 담당합니다.

## 담당 영역
- 전체 코드베이스 품질 관리
- 테스트 작성 및 실행
- 문서 정확성 검증
- MVP 체크리스트 관리

## 사용 도구
- **Bash**: 테스트 실행, 린트 검증
- **Read**: 코드 리뷰
- **Write/Edit**: 테스트 코드, 문서

## 입력
- PR 변경 내역
- 테스트 결과
- 사용자 피드백

## 출력
- 테스트 보고서
- 코드 리뷰 코멘트
- QA 체크리스트

## 완료 기준
- [ ] 모든 PR이 CI 통과
- [ ] Python 테스트 커버리지 80% 이상
- [ ] 주요 사용자 시나리오 E2E 테스트
- [ ] 문서와 코드의 일관성 검증
- [ ] MVP 체크리스트 100% 완료
```

---

## Phase 12: 문서 작성

> **완료 기준**: 아키텍처, CI/CD, 프로토콜, 진행 상황 문서가 모두 작성됨

### 단계 12.1 - 시스템 아키텍처 개요

**도구**: `Write`

파일 경로: `D:/home/ruView/docs/architecture/system-overview.md`

```markdown
# RuView 시스템 아키텍처 개요

## 시스템 구성도

```
┌──────────────┐    Wi-Fi CSI     ┌──────────────────┐
│  ESP32-S3    │ ──────────────→  │  RuView Sensing  │
│  (COM3)      │                  │  Server (local)  │
└──────────────┘                  └────────┬─────────┘
                                           │ WebSocket
                                           ▼
                                  ┌──────────────────┐
                                  │  Signal Adapter  │
                                  │  (FastAPI:8001)  │
                                  └────────┬─────────┘
                                           │
                              ┌────────────┼────────────┐
                              │            │            │
                              ▼            ▼            ▼
                     ┌─────────────┐ ┌──────────┐ ┌──────────┐
                     │  Supabase   │ │  events  │ │  alerts  │
                     │  signal_    │ │  table   │ │  table   │
                     │  logs table │ │          │ │          │
                     └─────────────┘ └────┬─────┘ └────┬─────┘
                                          │            │
                                          ▼            ▼
                                  ┌──────────────────┐
                                  │  API Gateway     │
                                  │  (FastAPI:8000)  │
                                  └────────┬─────────┘
                                           │ REST + WebSocket
                    ┌──────────────────────┤
                    │                      │
                    ▼                      ▼
           ┌──────────────┐      ┌──────────────────┐
           │  Web Monitor │      │  Cloudflare      │
           │  (React:3000)│      │  Tunnel          │
           └──────┬───────┘      └──────────────────┘
                  │                        │
                  ▼                        ▼
           ┌──────────────┐      ┌──────────────────┐
           │  Observatory │      │  External Access │
           │  (Three.js)  │      │  api.dev.xxx.com │
           └──────────────┘      └──────────────────┘
```

## 기술 스택

| 영역 | 기술 | 용도 |
|------|------|------|
| 하드웨어 | ESP32-S3 | Wi-Fi CSI 수집 |
| 신호 처리 | Python, FastAPI, NumPy | CSI 전처리 및 이벤트 추상화 |
| API | Python, FastAPI | REST + WebSocket gateway |
| 프론트엔드 | React, Vite, Tailwind | 관제 대시보드 |
| 3D 시각화 | Three.js (RuView) | 공간 시각화 |
| 데이터베이스 | Supabase (PostgreSQL) | 이벤트, 신호, 디바이스 저장 |
| 배포 | Cloudflare Pages | 프론트엔드 배포 |
| 터널 | Cloudflare Tunnel | 로컬 API 외부 공개 |
| CI/CD | GitHub Actions | 자동 빌드/배포 |
| 컨테이너 | Docker Compose | 로컬 개발 환경 |

## 데이터 흐름

1. **CSI 수집**: ESP32-S3가 Wi-Fi CSI 데이터를 수집하여 WebSocket으로 전송
2. **신호 처리**: Signal Adapter가 CSI 데이터를 수신, 전처리, 이벤트 추출
3. **데이터 적재**: 이벤트와 신호 로그를 Supabase에 저장
4. **실시간 전달**: Supabase Realtime + WebSocket으로 프론트엔드에 전달
5. **관제 표시**: Web Monitor가 2D Floor Map과 이벤트 로그로 시각화
6. **알림 처리**: 낙상 등 위험 이벤트 시 알림 생성 및 표시
```

### 단계 12.2 - 프론트엔드 비주얼 전략

**도구**: `Write`

파일 경로: `D:/home/ruView/docs/architecture/frontend-visual-strategy.md`

```markdown
# 프론트엔드 비주얼 전략

## 하이브리드 UI 구조

RuView 관제 앱은 **2D Floor Map + 3D Observatory** 하이브리드 구조를 채택합니다.

### 2D Floor Map (React + Konva)
- **용도**: 일상적인 관제 모니터링
- **구현**: React-Konva 라이브러리 (HTML5 Canvas)
- **표시 정보**:
  - 존(방) 경계선 및 이름
  - 디바이스 위치 및 상태 (온라인/오프라인/에러)
  - 재실 상태 (색상 변화)
  - 낙상/이상 이벤트 (경고 표시)
- **장점**: 가볍고 빠른 렌더링, 직관적 인터페이스

### 3D Observatory (RuView Three.js)
- **용도**: 상세 공간 분석, 프레젠테이션
- **구현**: iframe 임베딩 + postMessage 통신
- **표시 정보**:
  - 3D 공간 모델
  - CSI 신호 파형 시각화
  - 움직임 궤적
- **장점**: 몰입감 있는 시각화, 공간 이해도 향상

### 통신 프로토콜 (postMessage)

```typescript
// Monitor → Observatory
{ type: "monitor:config", payload: ObservatoryConfig }
{ type: "monitor:zones:update", payload: Zone[] }
{ type: "monitor:devices:update", payload: Device[] }
{ type: "monitor:zone:highlight", payload: { zoneId: string } }

// Observatory → Monitor
{ type: "observatory:ready", payload: {} }
{ type: "observatory:event", payload: ObservatoryEvent }
{ type: "observatory:error", payload: { message: string } }
```

## 상태 관리 (Zustand)

- **deviceStore**: 디바이스 목록, 상태, 선택
- **eventStore**: 이벤트 목록, 알림, 구독
- **zoneStore**: 존 목록, 선택 (추후 추가)
- **uiStore**: UI 상태 (테마, 사이드바 등, 추후 추가)
```

### 단계 12.3 - Cloudflare Pages 파이프라인

**도구**: `Write`

파일 경로: `D:/home/ruView/docs/ci-cd/cloudflare-pages-pipeline.md`

```markdown
# Cloudflare Pages 배포 파이프라인

## 브랜치 전략

| 브랜치 | 환경 | URL |
|--------|------|-----|
| `main` | Production | ruview-web-monitor.pages.dev |
| `develop` | Preview | xxxxxxxx.ruview-web-monitor.pages.dev |

## 배포 흐름

1. **PR 생성** → GitHub Actions CI (lint/test/build)
2. **develop 머지** → Cloudflare Pages Preview 배포
3. **main 머지** → Cloudflare Pages Production 배포

## 환경변수

### Production
- `VITE_SUPABASE_URL`: 프로덕션 Supabase URL
- `VITE_SUPABASE_ANON_KEY`: 프로덕션 anon key
- `VITE_API_BASE_URL`: 프로덕션 API URL
- `VITE_ENVIRONMENT`: `production`

### Preview
- `VITE_SUPABASE_URL`: 개발 Supabase URL
- `VITE_SUPABASE_ANON_KEY`: 개발 anon key
- `VITE_API_BASE_URL`: 개발 API URL (Tunnel)
- `VITE_ENVIRONMENT`: `preview`

## GitHub Secrets 설정

```
CLOUDFLARE_API_TOKEN
CLOUDFLARE_ACCOUNT_ID
VITE_SUPABASE_URL
VITE_SUPABASE_ANON_KEY
PROD_API_URL
DEV_API_URL
PROD_WS_URL
DEV_WS_URL
```

## 빌드 설정

- **Framework**: None (커스텀)
- **Build command**: `pnpm --filter @ruview/web-monitor build`
- **Output directory**: `apps/web-monitor/dist`
- **Root directory**: `/`
- **Node.js version**: 18
```

### 단계 12.4 - Cloudflare Tunnel 로컬 개발

**도구**: `Write`

파일 경로: `D:/home/ruView/docs/ci-cd/cloudflare-tunnel-local-dev.md`

```markdown
# Cloudflare Tunnel 로컬 개발 가이드

## 목적

로컬에서 실행 중인 API Gateway와 관제 서버를 외부에서 접근 가능하게 만듭니다.

## 설정 방법

### 1. cloudflared 설치

```bash
# Windows (winget)
winget install Cloudflare.cloudflared

# 또는 scoop
scoop install cloudflared
```

### 2. 로그인

```bash
cloudflared tunnel login
```

### 3. 터널 생성

```bash
cloudflared tunnel create ruview-dev
```

### 4. DNS 라우팅

```bash
cloudflared tunnel route dns ruview-dev api.dev.example.com
cloudflared tunnel route dns ruview-dev sense.dev.example.com
```

### 5. 설정 파일

`~/.cloudflared/config.yml` 또는 `infra/cloudflare/tunnel-config.example.yml` 참고

### 6. 터널 실행

```bash
cloudflared tunnel run ruview-dev
```

## 라우팅 테이블

| 외부 호스트 | 로컬 서비스 | 포트 |
|------------|------------|------|
| api.dev.example.com | API Gateway | 8000 |
| sense.dev.example.com | Web Monitor | 3000 |

## 주의사항

- Tunnel 토큰과 credentials 파일은 절대로 커밋하지 마세요
- 개발용 터널은 빠른 만료 설정을 권장합니다
- WebSocket 연결 시 `connectTimeout`을 충분히 설정하세요
```

### 단계 12.5 - RuView 이벤트 매핑 프로토콜

**도구**: `Write`

파일 경로: `D:/home/ruView/docs/protocol/ruview-event-mapping.md`

```markdown
# RuView 이벤트 매핑 프로토콜

## CSI 신호 → 이벤트 변환 규칙

### 이벤트 유형

| 이벤트 | 코드 | 감지 조건 | 신뢰도 계산 |
|--------|------|-----------|------------|
| 재실 감지 | `presence_detected` | variance > 5, mean_amp > 10 | min(1.0, variance / 20) |
| 재실 해제 | `presence_lost` | variance < 2 (이전: presence) | 0.8 (고정) |
| 낙상 감지 | `fall_detected` | max_change > 50, variance > 30 | min(1.0, max_change / 100) |
| 낙상 확인 | `fall_confirmed` | fall_detected + 5초 후 정지 | 이전 confidence + 0.1 |
| 움직임 | `movement_detected` | 10 < variance < 30 | min(1.0, variance / 30) |
| 호흡 감지 | `breathing_detected` | 주기적 미세 진폭 변화 | FFT 기반 (추후) |
| 존 진입 | `zone_enter` | 디바이스 범위 내 재실 시작 | 재실 confidence |
| 존 이탈 | `zone_exit` | 디바이스 범위 내 재실 해제 | 0.8 (고정) |

### CSI 데이터 형식

```json
{
  "device_id": "d0000000-...",
  "mac": "AA:BB:CC:DD:EE:01",
  "csi": [I1, Q1, I2, Q2, ...],   // IQ 복소수 쌍
  "rssi": -45,
  "noise_floor": -95,
  "subcarrier_count": 52,
  "timestamp": "2026-03-18T10:00:00Z"
}
```

### 특징 벡터

| 특징 | 설명 | 용도 |
|------|------|------|
| mean_amplitude | 평균 진폭 | 신호 강도 기준선 |
| std_amplitude | 진폭 표준편차 | 변동성 측정 |
| variance_over_time | 시간축 분산 | 활동량 추정 |
| max_change | 최대 변화량 | 급격한 변화 감지 (낙상) |
| rssi_std | RSSI 표준편차 | 환경 변화 감지 |

### 향후 개선 계획

1. **ML 기반 분류**: 규칙 기반 → SVM/Random Forest → LSTM/Transformer
2. **적응형 임계값**: 환경별 자동 캘리브레이션
3. **다중 디바이스 퓨전**: 복수 ESP32의 CSI를 결합하여 정확도 향상
```

### 단계 12.6 - MVP 체크리스트

**도구**: `Write`

파일 경로: `D:/home/ruView/docs/progress/mvp-checklist.md`

```markdown
# RuView Q1 MVP 체크리스트

## Phase 1: 저장소 Bootstrap
- [ ] GitHub 저장소 생성
- [ ] 브랜치 전략 설정 (main, develop)
- [ ] 브랜치 보호 규칙 적용
- [ ] 라벨 생성
- [ ] 마일스톤 생성
- [ ] Issue/PR 템플릿 생성
- [ ] CODEOWNERS 설정

## Phase 2: 모노레포 구조
- [ ] 디렉토리 구조 생성
- [ ] pnpm workspace 설정
- [ ] Turbo 설정
- [ ] 공유 TypeScript 설정
- [ ] 공유 타입 패키지

## Phase 3: Bootstrap 스크립트
- [ ] bootstrap-repos.sh 작성 및 테스트

## Phase 4: Cloudflare 설정
- [ ] Pages 프로젝트 생성
- [ ] Pages 환경변수 설정
- [ ] Tunnel 생성 및 DNS 라우팅
- [ ] Tunnel 설정 파일 작성

## Phase 5: Supabase 설정
- [ ] 프로젝트 생성
- [ ] 초기 스키마 마이그레이션 실행
- [ ] RLS 정책 적용
- [ ] Realtime 활성화
- [ ] 시드 데이터 적재

## Phase 6: React 관제 앱
- [ ] Vite + React + TypeScript 초기화
- [ ] Tailwind CSS + 테마 설정
- [ ] Supabase 클라이언트 연동
- [ ] Zustand 스토어 (device, event)
- [ ] WebSocket hook
- [ ] 2D Floor Map 컴포넌트
- [ ] Observatory Bridge 컴포넌트
- [ ] Dashboard 페이지
- [ ] 빌드 성공

## Phase 7: Signal Adapter
- [ ] FastAPI 앱 구조
- [ ] RuView WebSocket 수신기
- [ ] CSI 신호 전처리 엔진
- [ ] 이벤트 감지 엔진
- [ ] Supabase 적재 어댑터
- [ ] 단위 테스트
- [ ] Docker 빌드 성공

## Phase 8: API Gateway
- [ ] FastAPI 앱 구조
- [ ] REST 엔드포인트 (devices, zones, events, alerts)
- [ ] WebSocket relay
- [ ] 인증 미들웨어
- [ ] Docker 빌드 성공

## Phase 9: Docker 통합
- [ ] docker-compose.yml 작성
- [ ] 전체 서비스 docker-compose up 성공

## Phase 10: CI/CD
- [ ] GitHub Actions CI (lint/test/build)
- [ ] Cloudflare Pages 자동 배포
- [ ] Docker 이미지 빌드 워크플로우

## Phase 11: 에이전트 문서
- [ ] Hardware Agent
- [ ] Signal Agent
- [ ] Frontend Agent
- [ ] Observatory Agent
- [ ] DevOps Agent
- [ ] QA Agent

## Phase 12: 문서
- [ ] 시스템 아키텍처 개요
- [ ] 프론트엔드 비주얼 전략
- [ ] Cloudflare Pages 파이프라인
- [ ] Cloudflare Tunnel 로컬 개발 가이드
- [ ] RuView 이벤트 매핑 프로토콜
- [ ] MVP 체크리스트 (이 문서)

---

**총 진행률**: 0 / 56 항목 (0%)

**최종 목표**: 로컬 ESP32에서 CSI 데이터 수집 → Signal Adapter에서 이벤트 감지 → Supabase 저장 → React 대시보드에서 실시간 관제 표시, Cloudflare를 통한 외부 접근 가능
```

---

## 실행 완료 후 검증

### 최종 검증 스크립트

**도구**: `Bash`

```bash
cd "D:/home/ruView"

echo "============================================"
echo "  RuView MVP 빌드 검증"
echo "============================================"

echo ""
echo "[1/5] 모노레포 구조 확인..."
ls -la apps/ services/ packages/ infra/ agents/ docs/

echo ""
echo "[2/5] Node.js 의존성 설치..."
pnpm install

echo ""
echo "[3/5] Web Monitor 빌드..."
pnpm --filter @ruview/web-monitor build 2>&1 | tail -5

echo ""
echo "[4/5] Python Signal Adapter 의존성..."
cd services/signal-adapter && pip install -e ".[dev]" 2>&1 | tail -3
cd ../..

echo ""
echo "[5/5] Python 테스트..."
cd services/signal-adapter && pytest tests/ -v 2>&1 | tail -10
cd ../..

echo ""
echo "============================================"
echo "  검증 완료"
echo "============================================"
```

### Docker 검증

**도구**: `Bash`

```bash
cd "D:/home/ruView/infra/docker"
docker-compose config  # 설정 유효성 검증
```

---

## 부록: 주요 파일 경로 요약

```
D:/home/ruView/
├── .env                              # 환경변수 (git 제외)
├── .gitignore
├── .github/
│   ├── CODEOWNERS
│   ├── pull_request_template.md
│   ├── ISSUE_TEMPLATE/
│   │   ├── feature_request.yml
│   │   └── bug_report.yml
│   └── workflows/
│       ├── ci.yml
│       ├── deploy-pages.yml
│       └── docker-build.yml
├── package.json
├── pnpm-workspace.yaml
├── turbo.json
├── CONTRIBUTING.md
├── apps/
│   ├── web-monitor/                  # React 관제 대시보드
│   │   ├── package.json
│   │   ├── vite.config.ts
│   │   ├── tailwind.config.js
│   │   ├── tsconfig.json
│   │   └── src/
│   │       ├── main.tsx
│   │       ├── App.tsx
│   │       ├── components/
│   │       │   ├── FloorMap.tsx
│   │       │   └── ObservatoryBridge.tsx
│   │       ├── hooks/
│   │       │   └── useWebSocket.ts
│   │       ├── lib/
│   │       │   └── supabase.ts
│   │       ├── pages/
│   │       │   └── DashboardPage.tsx
│   │       ├── stores/
│   │       │   ├── deviceStore.ts
│   │       │   └── eventStore.ts
│   │       └── styles/
│   │           └── globals.css
│   └── api-gateway/                  # API Gateway
│       ├── pyproject.toml
│       ├── Dockerfile
│       └── src/
│           ├── app.py
│           ├── config.py
│           ├── middleware/
│           │   └── auth.py
│           ├── routes/
│           │   ├── devices.py
│           │   ├── zones.py
│           │   └── events.py
│           └── services/
│               └── ws_manager.py
├── services/
│   └── signal-adapter/               # Signal Adapter
│       ├── pyproject.toml
│       ├── Dockerfile
│       ├── src/
│       │   ├── main.py
│       │   ├── core/
│       │   │   ├── config.py
│       │   │   └── signal_processor.py
│       │   ├── models/
│       │   │   └── events.py
│       │   ├── adapters/
│       │   │   ├── supabase_adapter.py
│       │   │   └── ruview_receiver.py
│       │   └── api/
│       │       └── app.py
│       └── tests/
│           └── test_signal_processor.py
├── packages/
│   ├── shared-types/                 # 공유 타입
│   │   ├── package.json
│   │   └── src/index.ts
│   └── tsconfig/                     # 공유 TS 설정
│       ├── package.json
│       ├── base.json
│       └── react.json
├── vendor/
│   └── ruview-upstream/              # RuView 원본 (submodule)
├── infra/
│   ├── docker/
│   │   ├── docker-compose.yml
│   │   └── Dockerfile.web-dev
│   ├── cloudflare/
│   │   ├── pages.env.example
│   │   ├── tunnel-config.example.yml
│   │   ├── setup-pages.sh
│   │   └── setup-tunnel.sh
│   ├── github/
│   │   └── bootstrap-repos.sh
│   └── supabase/
│       ├── migrations/
│       │   ├── 001_initial_schema.sql
│       │   ├── 002_rls_policies.sql
│       │   └── 003_realtime.sql
│       ├── seed/
│       │   └── 001_sample_data.sql
│       └── functions/
│           └── process-alert/
│               └── index.ts
├── agents/
│   ├── hardware-agent.md
│   ├── signal-agent.md
│   ├── frontend-agent.md
│   ├── observatory-agent.md
│   ├── devops-agent.md
│   └── qa-agent.md
└── docs/
    ├── architecture/
    │   ├── system-overview.md
    │   └── frontend-visual-strategy.md
    ├── ci-cd/
    │   ├── cloudflare-pages-pipeline.md
    │   └── cloudflare-tunnel-local-dev.md
    ├── protocol/
    │   └── ruview-event-mapping.md
    └── progress/
        └── mvp-checklist.md
```

---

> **이 프롬프트의 각 Phase를 순서대로 실행하면, RuView MVP의 전체 인프라가 구축됩니다.**
> **각 단계에서 명시된 도구(Bash, Write, Edit, Read)를 사용하여 실행하세요.**
> **환경변수와 시크릿은 반드시 .env 파일을 통해 관리하고, 코드에 하드코딩하지 마세요.**
