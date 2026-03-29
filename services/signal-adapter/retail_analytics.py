"""
Retail Analytics — 존 전이 기반 고객 동선 및 체류 시간 분석.

기능:
  - 존 간 전이(transition) 추적 → Sankey 다이어그램 데이터
  - 존별 체류 시간 히스토그램
  - 인파 밀도 계산
  - 대기열 감지 (한 존에 3명 이상 동시 감지)
"""

from datetime import datetime, timezone
from typing import Optional

import numpy as np


class RetailAnalytics:
    """존 전이 기반 고객 동선 및 체류 시간 분석 클래스.

    웹 대시보드의 Sankey 다이어그램, 히트맵, 대기열 알림에
    필요한 데이터를 실시간으로 집계합니다.
    """

    QUEUE_THRESHOLD = 3  # 한 존에 이 인원 이상 시 대기열로 판정

    def __init__(self) -> None:
        # 전이 매트릭스: {from_zone: {to_zone: count}}
        self._transitions: dict[str, dict[str, int]] = {}
        # 존별 체류 시간 목록 (분 단위)
        self._dwell_times: dict[str, list[float]] = {}
        # 현재 존별 인원
        self._current_presence: dict[str, int] = {}
        # 존별 체류 시작 시각 (ISO 문자열)
        self._zone_entry_time: dict[str, str] = {}
        # 전체 업데이트 이력 (총 방문객 수 추산)
        self._total_updates: int = 0

    # ------------------------------------------------------------------
    # 내부 헬퍼
    # ------------------------------------------------------------------

    def _parse_iso(self, ts: str) -> Optional[datetime]:
        try:
            return datetime.fromisoformat(ts)
        except Exception:
            return None

    def _elapsed_minutes(self, start_iso: str, end_iso: str) -> float:
        """두 ISO 타임스탬프 간 경과 시간(분)을 반환합니다."""
        try:
            start_dt = self._parse_iso(start_iso)
            end_dt = self._parse_iso(end_iso)
            if start_dt and end_dt:
                return max((end_dt - start_dt).total_seconds() / 60.0, 0.0)
        except Exception:
            pass
        return 0.0

    # ------------------------------------------------------------------
    # 공개 API
    # ------------------------------------------------------------------

    def update_presence(self, zone_id: str, count: int, timestamp: str) -> dict:
        """존의 현재 인원을 업데이트합니다.

        인원이 0 → 양수로 바뀌면 체류 시작 기록,
        양수 → 0으로 바뀌면 체류 시간을 집계합니다.

        Args:
            zone_id: 존 식별자.
            count: 현재 감지된 인원 수.
            timestamp: ISO8601 타임스탬프.

        Returns:
            업데이트된 존 상태 dict.
        """
        try:
            prev_count = self._current_presence.get(zone_id, 0)
            self._current_presence[zone_id] = max(count, 0)
            self._total_updates += 1

            # 체류 시간 집계
            if prev_count == 0 and count > 0:
                # 입장: 체류 시작 기록
                self._zone_entry_time[zone_id] = timestamp
            elif prev_count > 0 and count == 0:
                # 퇴장: 체류 시간 기록
                entry_ts = self._zone_entry_time.pop(zone_id, None)
                if entry_ts:
                    dwell = self._elapsed_minutes(entry_ts, timestamp)
                    if zone_id not in self._dwell_times:
                        self._dwell_times[zone_id] = []
                    self._dwell_times[zone_id].append(round(dwell, 3))

            queue_active = count >= self.QUEUE_THRESHOLD

            return {
                "zone_id": zone_id,
                "count": count,
                "queue_active": queue_active,
                "timestamp": timestamp,
            }

        except Exception as exc:
            return {"zone_id": zone_id, "error": str(exc)}

    def record_transition(self, from_zone: str, to_zone: str, timestamp: str) -> dict:
        """존 이동을 기록합니다.

        Args:
            from_zone: 출발 존 식별자.
            to_zone: 도착 존 식별자.
            timestamp: ISO8601 타임스탬프.

        Returns:
            기록된 전이 정보 dict.
        """
        try:
            if from_zone not in self._transitions:
                self._transitions[from_zone] = {}
            self._transitions[from_zone][to_zone] = (
                self._transitions[from_zone].get(to_zone, 0) + 1
            )
            return {
                "from_zone": from_zone,
                "to_zone": to_zone,
                "count": self._transitions[from_zone][to_zone],
                "timestamp": timestamp,
            }

        except Exception as exc:
            return {"from_zone": from_zone, "to_zone": to_zone, "error": str(exc)}

    def get_paths(self) -> dict:
        """전이 매트릭스를 Sankey 다이어그램 형식으로 반환합니다.

        Returns:
            {
              "matrix": {from_zone: {to_zone: count}},
              "links": [{"source": ..., "target": ..., "value": ...}],
              "total_transitions": int,
            }
        """
        try:
            links = []
            total = 0
            for from_zone, targets in self._transitions.items():
                for to_zone, count in targets.items():
                    links.append({
                        "source": from_zone,
                        "target": to_zone,
                        "value": count,
                    })
                    total += count

            return {
                "matrix": {
                    fz: dict(targets)
                    for fz, targets in self._transitions.items()
                },
                "links": links,
                "total_transitions": total,
            }

        except Exception as exc:
            return {"error": str(exc), "matrix": {}, "links": [], "total_transitions": 0}

    def get_heatmap(self) -> list[dict]:
        """존별 평균 체류 시간 히트맵 데이터를 반환합니다.

        Returns:
            [{"zone_id": ..., "mean_dwell_min": ..., "visit_count": ..., "histogram": [...]}]
        """
        try:
            result = []
            all_zones = set(self._current_presence) | set(self._dwell_times)
            for zone_id in sorted(all_zones):
                times = self._dwell_times.get(zone_id, [])
                if times:
                    arr = np.array(times, dtype=np.float64)
                    mean_dwell = round(float(np.mean(arr)), 3)
                    # 히스토그램: 0-5분, 5-15분, 15-30분, 30분+
                    bins = [0.0, 5.0, 15.0, 30.0, float("inf")]
                    labels = ["0-5min", "5-15min", "15-30min", "30min+"]
                    histogram = []
                    for i in range(len(labels)):
                        cnt = int(np.sum((arr >= bins[i]) & (arr < bins[i + 1])))
                        histogram.append({"range": labels[i], "count": cnt})
                else:
                    mean_dwell = 0.0
                    histogram = []

                result.append({
                    "zone_id": zone_id,
                    "mean_dwell_min": mean_dwell,
                    "visit_count": len(times),
                    "current_count": self._current_presence.get(zone_id, 0),
                    "histogram": histogram,
                })

            return result

        except Exception as exc:
            return [{"error": str(exc)}]

    def get_queue_status(self) -> dict:
        """대기열 감지 결과를 반환합니다.

        Returns:
            {
              "queues": [{"zone_id": ..., "count": ..., "queue_active": bool}],
              "total_queue_zones": int,
              "total_people": int,
            }
        """
        try:
            queues = []
            for zone_id, count in self._current_presence.items():
                if count > 0:
                    queues.append({
                        "zone_id": zone_id,
                        "count": count,
                        "queue_active": count >= self.QUEUE_THRESHOLD,
                    })
            # 인원 내림차순 정렬
            queues.sort(key=lambda x: x["count"], reverse=True)
            queue_zones = [q for q in queues if q["queue_active"]]

            return {
                "queues": queues,
                "total_queue_zones": len(queue_zones),
                "total_people": sum(q["count"] for q in queues),
                "queue_zone_ids": [q["zone_id"] for q in queue_zones],
            }

        except Exception as exc:
            return {"error": str(exc), "queues": [], "total_queue_zones": 0, "total_people": 0}

    def get_density(self) -> dict:
        """인파 밀도 현황을 반환합니다.

        Returns:
            {zones: [{zone_id, count, density_level}], total_people: int}
        """
        try:
            zones = []
            for zone_id, count in self._current_presence.items():
                if count <= 1:
                    density_level = "low"
                elif count <= 3:
                    density_level = "medium"
                else:
                    density_level = "high"
                zones.append({
                    "zone_id": zone_id,
                    "count": count,
                    "density_level": density_level,
                })
            zones.sort(key=lambda x: x["count"], reverse=True)
            return {
                "zones": zones,
                "total_people": sum(z["count"] for z in zones),
            }

        except Exception as exc:
            return {"error": str(exc), "zones": [], "total_people": 0}


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    from datetime import datetime, timezone, timedelta

    analytics = RetailAnalytics()

    print("=== RetailAnalytics 동작 테스트 ===")

    base = datetime(2026, 3, 29, 10, 0, 0, tzinfo=timezone.utc)

    def ts(offset_min: float) -> str:
        return (base + timedelta(minutes=offset_min)).isoformat()

    # 입장 시뮬레이션
    analytics.update_presence("entrance", 2, ts(0))
    analytics.update_presence("zone_A", 1, ts(1))
    analytics.update_presence("zone_B", 3, ts(2))
    analytics.update_presence("zone_B", 4, ts(3))  # 대기열 발생

    # 동선 기록
    analytics.record_transition("entrance", "zone_A", ts(1))
    analytics.record_transition("entrance", "zone_B", ts(2))
    analytics.record_transition("zone_A", "zone_B", ts(4))
    analytics.record_transition("zone_B", "exit", ts(10))

    # 퇴장 (체류 시간 집계)
    analytics.update_presence("zone_A", 0, ts(15))
    analytics.update_presence("zone_B", 0, ts(20))

    print("\n[Paths / Sankey]")
    paths = analytics.get_paths()
    print(f"  total_transitions: {paths['total_transitions']}")
    for link in paths["links"]:
        print(f"    {link['source']} → {link['target']} : {link['value']}")

    print("\n[Heatmap]")
    for zone in analytics.get_heatmap():
        print(f"  {zone['zone_id']}: mean_dwell={zone['mean_dwell_min']}min, visits={zone['visit_count']}")

    print("\n[Queue Status]")
    qs = analytics.get_queue_status()
    print(f"  total_people={qs['total_people']}, queue_zones={qs['total_queue_zones']}")
    for q in qs["queues"]:
        print(f"    {q['zone_id']}: count={q['count']}, queue={q['queue_active']}")

    print("\n[Density]")
    density = analytics.get_density()
    for z in density["zones"]:
        print(f"  {z['zone_id']}: {z['count']}명 ({z['density_level']})")
