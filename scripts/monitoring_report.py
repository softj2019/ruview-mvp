#!/usr/bin/env python3
"""
ruView 2시간 주기 모니터링 리포트
- signal-adapter 노드 상태/정확도 수집
- camera-service 포즈 신뢰도 수집
- aimix gateway에 태스크로 보고
- GitHub 이슈 자동 등록 (심각 문제 감지 시)
"""
import json, subprocess, urllib.request, urllib.error, datetime, os

SIGNAL_URL = "http://localhost:8001"
CAMERA_URL = "http://localhost:8002"
AIMIX_URL  = "http://localhost:3001"
AIMIX_PID  = os.environ.get("AIMIX_PROJECT_ID", "xRcaQ3pt593HZ2mDhie0p")
AIMIX_SID  = os.environ.get("AIMIX_SESSION_ID",  "e49IJHAU3be4I-quUv-_U")
GH_REPO    = "softj2019/ruview-mvp"
KST        = datetime.timezone(datetime.timedelta(hours=9))


def fetch(url, timeout=5):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}


def post_json(url, payload, timeout=10):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}


def gh_open_issues(limit=10):
    """Return list of open issues as '#N title' strings."""
    try:
        r = subprocess.run(
            ["gh", "issue", "list", "--repo", GH_REPO,
             "--state", "open", "--limit", str(limit),
             "--json", "number,title"],
            capture_output=True, timeout=20
        )
        items = json.loads(r.stdout.decode("utf-8", errors="replace") or "[]")
        return [f"#{i['number']} {i['title']}" for i in items]
    except Exception:
        return []


def gh_issue_exists(title):
    try:
        r = subprocess.run(
            ["gh", "issue", "list", "--repo", GH_REPO,
             "--search", title, "--json", "title"],
            capture_output=True, timeout=20
        )
        items = json.loads(r.stdout.decode("utf-8", errors="replace") or "[]")
        return any(i.get("title", "") == title for i in items)
    except Exception:
        return False


def gh_issue(title, body, labels="monitoring,auto-detected"):
    if gh_issue_exists(title):
        return "(이미 등록된 이슈)"
    try:
        r = subprocess.run(
            ["gh", "issue", "create", "--repo", GH_REPO,
             "--title", title, "--body", body, "--label", labels],
            capture_output=True, timeout=30
        )
        out = r.stdout.decode("utf-8", errors="replace").strip()
        err = r.stderr.decode("utf-8", errors="replace").strip()
        return out or err
    except Exception as e:
        return f"gh error: {e}"


def analyze():
    now = datetime.datetime.now(KST)
    ts  = now.strftime("%Y-%m-%d %H:%M KST")

    # ── 1. signal-adapter 수집 ──────────────────────────────────────
    health  = fetch(f"{SIGNAL_URL}/health")
    devices = fetch(f"{SIGNAL_URL}/api/devices")
    lreport = fetch(f"{SIGNAL_URL}/api/learning-report")
    fstats  = fetch(f"{SIGNAL_URL}/api/fall/stats")
    devs    = devices.get("data", []) if isinstance(devices, dict) else []

    # ── 2. camera-service 수집 ──────────────────────────────────────
    cam_health = fetch(f"{CAMERA_URL}/cam/health")
    cam_ok     = "error" not in cam_health and cam_health.get("status") == "ok"

    # ── 3. 분석 ────────────────────────────────────────────────────
    online  = [d for d in devs if d.get("status") == "online"]
    offline = [d for d in devs if d.get("status") != "online"]

    issues_found = []
    node_rows = []

    for d in devs:
        did  = d.get("id", "?")
        st   = d.get("status", "?")
        ps   = float(d.get("presence_score") or 0)
        me   = float(d.get("motion_energy") or 0)
        np_  = int(d.get("csi_estimated_persons") or 0)
        cpc  = float(d.get("csi_pose_confidence") or 0)
        # GitHub #11: csi 필드 우선 (Welford 가드 적용된 값)
        br   = float(d.get("csi_breathing_bpm") or d.get("breathing_bpm") or 0)
        hr   = float(d.get("csi_heart_rate") or d.get("heart_rate") or 0)
        zone = d.get("zone_id", "?")

        # 이상 감지
        # node-6: 전원 OFF 상태 (의도적) — 오프라인 알림 제외
        KNOWN_OFFLINE = {"node-6"}
        if st == "offline" and did not in KNOWN_OFFLINE:
            issues_found.append(f"[OFFLINE] {did} 오프라인 — 물리 점검 필요")
        if st == "online" and ps < 0.15:
            issues_found.append(f"[LOW_PRESENCE] {did} presence_score={ps:.3f} (노이즈 수준)")
        # presence < 0.15 → 노이즈 구간이므로 vitals 경보 억제
        vitals_reliable = ps >= 0.15
        if vitals_reliable and br > 30:
            issues_found.append(f"[HIGH_BR] {did} 호흡={br:.1f}bpm 상한 초과")
        if vitals_reliable and hr > 110:
            issues_found.append(f"[HIGH_HR] {did} 심박={hr:.1f}bpm 빈맥 경보")
        if vitals_reliable and hr > 0 and hr < 40:
            issues_found.append(f"[LOW_HR] {did} 심박={hr:.1f}bpm 서맥 경보")

        icon = "✅" if st == "online" else "❌"
        node_rows.append(
            f"| {did} | {icon} {st} | {zone} | {ps:.3f} | {np_} | "
            f"{cpc:.2f} | {br:.1f} | {hr:.1f} |"
        )

    # 전체 정확도 추정
    valid_nodes = [d for d in devs
                   if d.get("status") == "online"
                   and float(d.get("presence_score") or 0) >= 0.15]
    presence_acc = f"{len(valid_nodes)}/{len(online)} 노드 신뢰 (presence≥0.15)"

    # ── 4. GitHub 오픈 이슈 ─────────────────────────────────────────
    open_issues = gh_open_issues()

    # ── 5. 동적 권장 조치 생성 ──────────────────────────────────────
    nl = "\n"
    actions = []
    offline_ids = [d.get("id") for d in devs if d.get("status") != "online"]
    low_presence_nodes = [d.get("id") for d in devs
                          if d.get("status") == "online"
                          and float(d.get("presence_score") or 0) < 0.15]

    if offline_ids:
        for oid in offline_ids:
            actions.append(f"**즉시**: {oid} 전원/WiFi 확인 및 재부팅")

    fall_samples = int(fstats.get("total_samples", 0))
    if fall_samples < 150:
        remaining = 150 - fall_samples
        actions.append(
            f"**금일 중**: 낙상 시뮬레이션 데이터 수집 {remaining}건 (POST /api/fall/record)"
        )

    if len(low_presence_nodes) >= 3:
        actions.append("**주말 중**: AP 채널 고정, 노드 높이 1.2~1.5m 재조정 — "
                       f"저신뢰 노드 {len(low_presence_nodes)}개")

    if not lreport.get("calibration_complete") or len(low_presence_nodes) >= 4:
        actions.append("**재캘리브레이션**: 노드 정리 후 `POST /api/calibration/empty-room`")

    if not actions:
        actions.append("이상 없음 — 추가 조치 불필요 ✅")

    actions_text = nl.join(f"{i+1}. {a}" for i, a in enumerate(actions))

    # ── 6. 보고서 생성 ─────────────────────────────────────────────
    report = f"""# ruView 정기 모니터링 리포트
**시각**: {ts}
**서비스**: signal-adapter={health.get('mode','?')} | camera={'✅' if cam_ok else '❌'} | 노드={len(online)}/6 온라인

---

## 노드별 센싱 상태

| 노드 | 상태 | 존 | presence | n_persons | pose_conf | 호흡(bpm) | 심박(bpm) |
|------|------|----|---------:|----------:|----------:|----------:|----------:|
{nl.join(node_rows)}

**재실 감지 신뢰도**: {presence_acc}

---

## 캘리브레이션 / 학습 상태

- Welford 캘리브레이션: {'✅ 완료' if lreport.get('calibration_complete') else '⚠️ 미완료'}
- 리포트: {lreport.get('report', 'N/A')}
- 낙상 모델 로드: {'✅' if fstats.get('model_loaded') else '❌ 미학습'}
- 학습 샘플: **{fstats.get('total_samples', 0)}건** / 목표 150건
  - 낙상 {fstats.get('falls', 0)}건 | 정상 {fstats.get('non_falls', 0)}건

---

## 감지된 문제 ({len(issues_found)}건)

{nl.join('- ' + i for i in issues_found) if issues_found else '- 이상 없음 ✅'}

---

## 미해결 개선 이슈 (GitHub)

{nl.join('- ' + i for i in open_issues) if open_issues else '- (이슈 없음 또는 gh 미인증)'}

---

## 권장 조치

{actions_text}
"""
    return report, issues_found, ts


def main():
    report, issues, ts = analyze()

    # ── aimix 보고 ─────────────────────────────────────────────────
    result = post_json(f"{AIMIX_URL}/api/tasks", {
        "projectId": AIMIX_PID,
        "sessionId": AIMIX_SID,
        "title":     f"[ruView 모니터링] {ts}",
        "prompt":    report,
        "agents":    ["claude"]
    })
    print(f"[{ts}] aimix 보고: task_id={result.get('id', 'ERR: ' + str(result))}")

    # ── 심각 문제 → GitHub 이슈 자동 등록 ─────────────────────────
    critical_keywords = ["[OFFLINE]", "[HIGH_HR]", "[LOW_HR]"]
    for msg in issues:
        if any(k in msg for k in critical_keywords):
            url = gh_issue(
                title=f"[자동감지] {msg[:80]}",
                body=(
                    f"## 자동 모니터링 감지\n"
                    f"**시각**: {ts}\n\n"
                    f"**내용**: {msg}\n\n"
                    f"---\n"
                    f"*monitoring_report.py 자동 생성*"
                )
            )
            print(f"  GitHub 이슈: {url}")

    # 콘솔 출력 (로그용)
    print(report)


if __name__ == "__main__":
    import sys
    if sys.stdout.encoding and sys.stdout.encoding.lower() in ("cp949", "cp1252", "ascii"):
        sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)
    main()
