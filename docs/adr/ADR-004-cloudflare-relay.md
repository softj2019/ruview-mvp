# ADR-004: Cloudflare Worker Relay for External Access

## Status
Accepted

## Date
2025-07-10

## Context
The monitoring server runs inside an office network behind a restrictive firewall.
Caregivers and family members need real-time access to the dashboard from external
networks. Opening inbound firewall ports is not permitted by IT policy. Traditional
VPN adds friction for non-technical users.

## Decision
Use a Cloudflare-based outbound relay architecture:

1. **Office-side bridge** (`services/cf-bridge/`): Maintains a persistent outbound
   WebSocket connection to a Cloudflare Worker. Pushes state updates (presence, vitals,
   alerts) every 1 second.
2. **Cloudflare Worker + Durable Object** (`infra/cloudflare/worker/`): Receives
   updates from the bridge and holds current state in a Durable Object. Serves REST
   and WebSocket APIs to external clients.
3. **Cloudflare Pages** (`apps/ruview-dashboard/`): Static SPA dashboard deployed to
   Pages, connects to the Worker for real-time data.
4. **Authentication:** Cloudflare Access (Zero Trust) gates the Pages app. Authorized
   users authenticate via email OTP.

Data flow: `signal-adapter -> cf-bridge --outbound--> Worker DO ---> Pages SPA`

## Consequences
- **Positive:** Zero inbound firewall changes required; all connections are outbound.
- **Positive:** Cloudflare edge caching provides low-latency access globally.
- **Positive:** Zero Trust authentication without managing a VPN.
- **Negative:** Dependency on Cloudflare availability (mitigated by their 99.99% SLA).
- **Negative:** Durable Object adds ~50ms latency vs direct connection.
- **Cost:** Worker free tier supports up to 100K requests/day, sufficient for current
  scale. Durable Object billed per 1M requests (~$0.15/M).
