#!/usr/bin/env python3
"""
ruView 주말 카메라-CSI 연속 학습기
- 카메라(YOLO) ground truth vs CSI 피처 매 30초 수집
- 거짓양성/거짓음성 레이블링 → presence_dataset.csv 누적
- 매 300샘플마다 Welford threshold 자동 재조정
- 매 실행 시 학습 현황 aimix 보고
"""
import json, time, csv, os, datetime, urllib.request, urllib.error, pathlib, statistics

SIGNAL_URL = "http://localhost:8001"
CAMERA_URL = "http://localhost:8002"
AIMIX_URL  = "http://localhost:3001"
AIMIX_PID  = os.environ.get("AIMIX_PROJECT_ID", "xRcaQ3pt593HZ2mDhie0p")
AIMIX_SID  = os.environ.get("AIMIX_SESSION_ID",  "e49IJHAU3be4I-quUv-_U")
KST        = datetime.timezone(datetime.timedelta(hours=9))

DATASET_PATH = pathlib.Path(__file__).parent.parent / "services/signal-adapter/fall_data/presence_dataset.csv"
INTERVAL_SEC = 30      # 수집 주기
RETRAIN_EVERY = 300    # N 샘플마다 threshold 재조정
REPORT_EVERY  = 240    # N 샘플마다 aimix 보고 (~2시간)

FIELDNAMES = [
    "timestamp", "device_id", "zone_id",
    "presence_score", "motion_energy", "max_velocity",
    "csi_estimated_persons", "csi_breathing_bpm", "csi_heart_rate",
    "n_persons", "_presence_z", "_presence_threshold",
    "camera_person_count", "label"   # label: 0=empty, 1=occupied
]


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


def get_camera_count():
    d = fetch(f"{CAMERA_URL}/cam/health")
    if "error" in d:
        return -1  # 카메라 불가
    return int(d.get("person_count", 0))


def collect_sample(camera_count):
    """현재 모든 노드에서 피처 수집 → row list 반환"""
    devs_resp = fetch(f"{SIGNAL_URL}/api/devices")
    zones_resp = fetch(f"{SIGNAL_URL}/api/zones")

    devs  = devs_resp.get("data", []) if isinstance(devs_resp, dict) else []
    zones = zones_resp if isinstance(zones_resp, list) else zones_resp.get("data", zones_resp.get("zones", []))
    zone_cam = {z["id"]: z.get("camera_person_count", 0) for z in zones}

    ts = datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
    rows = []
    for dev in devs:
        if dev.get("status") != "online":
            continue
        did  = dev["id"]
        zone = dev.get("zone_id", "?")
        # camera ground truth: zone-level camera, or global camera_count
        cam_zone = zone_cam.get(zone, 0)
        cam_gt   = camera_count if camera_count >= 0 else cam_zone
        label    = 1 if cam_gt > 0 else 0

        row = {
            "timestamp":             ts,
            "device_id":             did,
            "zone_id":               zone,
            "presence_score":        round(float(dev.get("presence_score") or 0), 6),
            "motion_energy":         round(float(dev.get("motion_energy") or 0), 6),
            "max_velocity":          round(float(dev.get("max_velocity") or 0), 4),
            "csi_estimated_persons": int(dev.get("csi_estimated_persons") or 0),
            "csi_breathing_bpm":     round(float(dev.get("csi_breathing_bpm") or 0), 2),
            "csi_heart_rate":        round(float(dev.get("csi_heart_rate") or 0), 2),
            "n_persons":             int(dev.get("n_persons") or 0),
            "_presence_z":           round(float(dev.get("_presence_z") or 0), 4),
            "_presence_threshold":   round(float(dev.get("_presence_threshold") or 0), 6),
            "camera_person_count":   cam_gt,
            "label":                 label,
        }
        rows.append(row)
    return rows


def append_to_dataset(rows):
    new_file = not DATASET_PATH.exists()
    with open(DATASET_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if new_file:
            writer.writeheader()
        writer.writerows(rows)


def load_dataset():
    if not DATASET_PATH.exists():
        return []
    rows = []
    with open(DATASET_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)
    return rows


def analyze_false_positives(rows):
    """label=0(빈방)인데 presence_score 높은 샘플 분석"""
    empty_rows = [r for r in rows if r["label"] == "0"]
    occ_rows   = [r for r in rows if r["label"] == "1"]

    stats = {}
    for did in set(r["device_id"] for r in rows):
        empty_ps = [float(r["presence_score"]) for r in empty_rows if r["device_id"] == did]
        occ_ps   = [float(r["presence_score"]) for r in occ_rows  if r["device_id"] == did]
        if not empty_ps:
            continue
        mean_e = statistics.mean(empty_ps)
        std_e  = statistics.stdev(empty_ps) if len(empty_ps) > 1 else 0.0
        p99_e  = sorted(empty_ps)[int(len(empty_ps) * 0.99)]
        mean_o = statistics.mean(occ_ps) if occ_ps else None
        # 권장 threshold: empty 99th percentile + 20% margin
        suggested_thr = p99_e * 1.2 if p99_e > 0 else mean_e + 3 * std_e + 0.05
        stats[did] = {
            "n_empty": len(empty_ps),
            "n_occ": len(occ_ps),
            "empty_mean": round(mean_e, 5),
            "empty_std": round(std_e, 5),
            "empty_p99": round(p99_e, 5),
            "occ_mean": round(mean_o, 5) if mean_o else None,
            "suggested_threshold": round(suggested_thr, 5),
        }
    return stats


def apply_suggested_thresholds(stats):
    """빈방 학습 기반 권장 threshold를 signal-adapter에 직접 반영.

    /api/calibration/thresholds 로 노드별 임계값만 패치 (Welford reset 없음).
    """
    thresholds = {did: s["suggested_threshold"] for did, s in stats.items()}
    result = post_json(f"{SIGNAL_URL}/api/calibration/thresholds", {"thresholds": thresholds})
    return result


def make_report(stats, total_rows, fp_count, fn_count):
    ts = datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")
    lines = [
        f"# ruView 주말 학습 리포트",
        f"**시각**: {ts}",
        f"**총 수집 샘플**: {total_rows}행 ({total_rows//6}회 스냅샷)",
        f"**거짓양성(빈방→감지)**: {fp_count}건 | **거짓음성(재실→미감지)**: {fn_count}건",
        "",
        "## 노드별 빈방 분석 및 권장 threshold",
        "",
        "| 노드 | 빈방N | 재실N | 빈방mean | 빈방p99 | 현재thr→권장thr |",
        "|------|------:|------:|--------:|-------:|----------------|",
    ]
    for did, s in sorted(stats.items()):
        lines.append(
            f"| {did} | {s['n_empty']} | {s['n_occ']} | "
            f"{s['empty_mean']:.4f} | {s['empty_p99']:.4f} | "
            f"→ **{s['suggested_threshold']:.4f}** |"
        )
    lines += [
        "",
        "## 오탐 패턴 요약",
        f"- 데이터 기반 threshold 권장값 계산 완료",
        f"- 다음 빈방 캘리브레이션 시 자동 반영 예정",
        "",
        "*weekend_learner.py 자동 생성*",
    ]
    return "\n".join(lines)


def main():
    import sys
    print(f"[weekend_learner] start interval={INTERVAL_SEC}s dataset={DATASET_PATH}")

    sample_count = 0
    fp_count = 0
    fn_count = 0

    while True:
        try:
            cam_count = get_camera_count()
            rows = collect_sample(cam_count)
            append_to_dataset(rows)
            sample_count += len(rows)

            # 거짓양성/음성 카운트
            for r in rows:
                pz = float(r["_presence_z"] or 0)
                lbl = int(r["label"])
                if pz > 0 and lbl == 0:
                    fp_count += 1
                if pz == 0 and lbl == 1:
                    fn_count += 1

            ts = datetime.datetime.now(KST).strftime("%H:%M:%S")
            print(f"[{ts}] 수집 {sample_count}행 | cam={cam_count} | fp={fp_count} fn={fn_count}")

            # 300샘플마다 분석 및 threshold 재조정
            if sample_count % RETRAIN_EVERY < len(rows):
                all_rows = load_dataset()
                stats = analyze_false_positives(all_rows)
                print(f"  [재조정] {len(all_rows)}행 분석 — 빈방 캘리브레이션 재실행")
                apply_suggested_thresholds(stats)

            # REPORT_EVERY샘플마다 aimix 보고
            if sample_count % REPORT_EVERY < len(rows):
                all_rows = load_dataset()
                stats = analyze_false_positives(all_rows)
                report = make_report(stats, len(all_rows), fp_count, fn_count)
                result = post_json(f"{AIMIX_URL}/api/tasks", {
                    "projectId": AIMIX_PID,
                    "sessionId": AIMIX_SID,
                    "title":     f"[주말학습] presence 오탐 분석 {ts}",
                    "prompt":    report,
                    "agents":    ["claude"],
                })
                print(f"  [aimix] task_id={result.get('id', 'ERR')}")

        except KeyboardInterrupt:
            print("\n[weekend_learner] 중단")
            break
        except Exception as e:
            print(f"[ERROR] {e}")

        time.sleep(INTERVAL_SEC)


if __name__ == "__main__":
    main()
