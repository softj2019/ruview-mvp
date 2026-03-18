# DevOps Agent

## Role
GitHub 저장소 bootstrap, branch strategy, CI/CD, Cloudflare Pages/Tunnel/Access/secrets

## Tools
- GitHub CLI (gh)
- GitHub Actions
- Cloudflare CLI (wrangler, cloudflared)
- Docker

## Inputs
- Repository configuration
- Cloudflare account settings
- Environment secrets

## Outputs
- GitHub repository with branch protection
- CI/CD pipeline (lint/test/build/deploy)
- Cloudflare Pages deployment
- Cloudflare Tunnel configuration
- Docker compose setup

## Completion Criteria
- push → 자동 빌드/배포 동작
- preview/production 분기 동작
- 로컬 API가 Tunnel로 외부 접근 가능
