"""
Metrics collection service for RuView Signal Adapter.
Adapted from vendor/ruview-temp/v1/src/services/metrics.py
"""

import asyncio
import logging
import time
import psutil
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


@dataclass
class MetricPoint:
    """Single metric data point."""
    timestamp: datetime
    value: float
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class MetricSeries:
    """Time series of metric points (1000-point deque)."""
    name: str
    description: str
    unit: str
    points: deque = field(default_factory=lambda: deque(maxlen=1000))

    def add_point(self, value: float, labels: Optional[Dict[str, str]] = None):
        """Add a metric point."""
        point = MetricPoint(
            timestamp=datetime.utcnow(),
            value=value,
            labels=labels or {}
        )
        self.points.append(point)

    def get_latest(self) -> Optional[MetricPoint]:
        """Get the latest metric point."""
        return self.points[-1] if self.points else None

    def get_average(self, duration: timedelta) -> Optional[float]:
        """Get average value over a time duration."""
        cutoff = datetime.utcnow() - duration
        relevant_points = [p for p in self.points if p.timestamp >= cutoff]
        if not relevant_points:
            return None
        return sum(p.value for p in relevant_points) / len(relevant_points)

    def get_max(self, duration: timedelta) -> Optional[float]:
        """Get maximum value over a time duration."""
        cutoff = datetime.utcnow() - duration
        relevant_points = [p for p in self.points if p.timestamp >= cutoff]
        if not relevant_points:
            return None
        return max(p.value for p in relevant_points)


class MetricsService:
    """Service for collecting and managing application metrics."""

    def __init__(self):
        self._metrics: Dict[str, MetricSeries] = {}
        self._counters: Dict[str, float] = defaultdict(float)
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = defaultdict(list)
        self._start_time = time.time()
        self._initialized = False
        self._running = False

        # Initialize standard metrics
        self._initialize_standard_metrics()

    def _initialize_standard_metrics(self):
        """Initialize standard system and application metrics."""
        self._metrics.update({
            # System metrics
            "system_cpu_usage": MetricSeries(
                "system_cpu_usage", "System CPU usage percentage", "percent"
            ),
            "system_memory_usage": MetricSeries(
                "system_memory_usage", "System memory usage percentage", "percent"
            ),
            "system_disk_usage": MetricSeries(
                "system_disk_usage", "System disk usage percentage", "percent"
            ),
            "system_network_bytes_sent": MetricSeries(
                "system_network_bytes_sent", "Network bytes sent", "bytes"
            ),
            "system_network_bytes_recv": MetricSeries(
                "system_network_bytes_recv", "Network bytes received", "bytes"
            ),

            # Application metrics
            "app_requests_total": MetricSeries(
                "app_requests_total", "Total HTTP requests", "count"
            ),
            "app_request_duration": MetricSeries(
                "app_request_duration", "HTTP request duration", "seconds"
            ),
            "app_active_connections": MetricSeries(
                "app_active_connections", "Active WebSocket connections", "count"
            ),
            "app_csi_data_points": MetricSeries(
                "app_csi_data_points", "CSI data points processed", "count"
            ),
            "app_stream_fps": MetricSeries(
                "app_stream_fps", "Streaming frames per second", "fps"
            ),

            # CSI-specific metrics
            "csi_processed": MetricSeries(
                "csi_processed", "CSI frames processed by signal pipeline", "count"
            ),
            "motion_index": MetricSeries(
                "motion_index", "Motion index from CSI processing", "ratio"
            ),
            "inference_latency": MetricSeries(
                "inference_latency", "ML inference latency", "seconds"
            ),

            # Error metrics
            "app_errors_total": MetricSeries(
                "app_errors_total", "Total application errors", "count"
            ),
            "app_http_errors": MetricSeries(
                "app_http_errors", "HTTP errors", "count"
            ),
        })

    async def initialize(self):
        """Initialize metrics service."""
        if self._initialized:
            return
        logger.info("Initializing metrics service")
        self._initialized = True
        logger.info("Metrics service initialized")

    async def start(self):
        """Start metrics service."""
        if not self._initialized:
            await self.initialize()
        self._running = True
        logger.info("Metrics service started")

    async def shutdown(self):
        """Shutdown metrics service."""
        self._running = False
        logger.info("Metrics service shut down")

    async def collect_system_metrics(self):
        """Collect system-level metrics (CPU, memory, disk, network)."""
        try:
            cpu_percent = psutil.cpu_percent(interval=None)
            self._metrics["system_cpu_usage"].add_point(cpu_percent)

            memory = psutil.virtual_memory()
            self._metrics["system_memory_usage"].add_point(memory.percent)

            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            self._metrics["system_disk_usage"].add_point(disk_percent)

            network = psutil.net_io_counters()
            self._metrics["system_network_bytes_sent"].add_point(network.bytes_sent)
            self._metrics["system_network_bytes_recv"].add_point(network.bytes_recv)

        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")

    # ── Core recording API ────────────────────────────────────────────────────

    def record(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Record a metric value by name.

        If the metric series does not exist, it is created on-demand.
        Supports both existing named series and ad-hoc metrics.
        """
        if name not in self._metrics:
            self._metrics[name] = MetricSeries(name, name, "")
        self._metrics[name].add_point(value, labels)

    def increment_counter(self, name: str, value: float = 1.0,
                          labels: Optional[Dict[str, str]] = None):
        """Increment a counter metric."""
        self._counters[name] += value
        if name in self._metrics:
            self._metrics[name].add_point(self._counters[name], labels)

    def set_gauge(self, name: str, value: float,
                  labels: Optional[Dict[str, str]] = None):
        """Set a gauge metric value."""
        self._gauges[name] = value
        if name in self._metrics:
            self._metrics[name].add_point(value, labels)

    def record_histogram(self, name: str, value: float,
                         labels: Optional[Dict[str, str]] = None):
        """Record a histogram value (keeps last 1000 values)."""
        self._histograms[name].append(value)
        if len(self._histograms[name]) > 1000:
            self._histograms[name] = self._histograms[name][-1000:]
        if name in self._metrics:
            self._metrics[name].add_point(value, labels)

    def time_function(self, metric_name: str):
        """Decorator to time function execution and record inference latency."""
        def decorator(func):
            import functools

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = await func(*args, **kwargs)
                    return result
                finally:
                    duration = time.time() - start_time
                    self.record_histogram(metric_name, duration)

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    return result
                finally:
                    duration = time.time() - start_time
                    self.record_histogram(metric_name, duration)

            return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

        return decorator

    # ── Query API ─────────────────────────────────────────────────────────────

    def get_metric(self, name: str) -> Optional[MetricSeries]:
        """Get a metric series by name."""
        return self._metrics.get(name)

    def get_metric_value(self, name: str) -> Optional[float]:
        """Get the latest value of a metric."""
        metric = self._metrics.get(name)
        if metric:
            latest = metric.get_latest()
            return latest.value if latest else None
        return None

    def get_counter_value(self, name: str) -> float:
        """Get current counter value."""
        return self._counters.get(name, 0.0)

    def get_gauge_value(self, name: str) -> Optional[float]:
        """Get current gauge value."""
        return self._gauges.get(name)

    def get_histogram_stats(self, name: str) -> Dict[str, float]:
        """Get histogram statistics (count, sum, min, max, mean, p50/90/95/99)."""
        values = self._histograms.get(name, [])
        if not values:
            return {}
        sorted_values = sorted(values)
        count = len(sorted_values)
        return {
            "count": count,
            "sum": sum(sorted_values),
            "min": sorted_values[0],
            "max": sorted_values[-1],
            "mean": sum(sorted_values) / count,
            "p50": sorted_values[int(count * 0.5)],
            "p90": sorted_values[int(count * 0.9)],
            "p95": sorted_values[int(count * 0.95)],
            "p99": sorted_values[int(count * 0.99)],
        }

    async def get_all_metrics(self) -> Dict[str, Any]:
        """Get all current metrics in a structured dict."""
        metrics: Dict[str, Any] = {}

        for name, series in self._metrics.items():
            latest = series.get_latest()
            if latest:
                metrics[name] = {
                    "value": latest.value,
                    "timestamp": latest.timestamp.isoformat(),
                    "description": series.description,
                    "unit": series.unit,
                    "labels": latest.labels,
                }

        metrics.update({f"counter_{n}": v for n, v in self._counters.items()})
        metrics.update({f"gauge_{n}": v for n, v in self._gauges.items()})

        for name, values in self._histograms.items():
            if values:
                metrics[f"histogram_{name}"] = self.get_histogram_stats(name)

        return metrics

    async def get_system_metrics(self) -> Dict[str, Any]:
        """Get system metrics summary."""
        return {
            "cpu_usage": self.get_metric_value("system_cpu_usage"),
            "memory_usage": self.get_metric_value("system_memory_usage"),
            "disk_usage": self.get_metric_value("system_disk_usage"),
            "network_bytes_sent": self.get_metric_value("system_network_bytes_sent"),
            "network_bytes_recv": self.get_metric_value("system_network_bytes_recv"),
        }

    async def get_application_metrics(self) -> Dict[str, Any]:
        """Get application metrics summary."""
        return {
            "requests_total": self.get_counter_value("app_requests_total"),
            "active_connections": self.get_metric_value("app_active_connections"),
            "csi_data_points": self.get_counter_value("app_csi_data_points"),
            "errors_total": self.get_counter_value("app_errors_total"),
            "uptime_seconds": time.time() - self._start_time,
            "request_duration_stats": self.get_histogram_stats("app_request_duration"),
            "inference_latency_stats": self.get_histogram_stats("inference_latency"),
        }

    async def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance metrics summary over the last hour."""
        one_hour = timedelta(hours=1)
        return {
            "system": {
                "cpu_avg_1h": self._metrics["system_cpu_usage"].get_average(one_hour),
                "memory_avg_1h": self._metrics["system_memory_usage"].get_average(one_hour),
                "cpu_max_1h": self._metrics["system_cpu_usage"].get_max(one_hour),
                "memory_max_1h": self._metrics["system_memory_usage"].get_max(one_hour),
            },
            "application": {
                "avg_request_duration": self.get_histogram_stats("app_request_duration").get("mean"),
                "avg_inference_latency": self.get_histogram_stats("inference_latency").get("mean"),
                "total_requests": self.get_counter_value("app_requests_total"),
                "total_errors": self.get_counter_value("app_errors_total"),
                "error_rate": (
                    self.get_counter_value("app_errors_total") /
                    max(self.get_counter_value("app_requests_total"), 1)
                ) * 100,
            },
        }

    async def get_status(self) -> Dict[str, Any]:
        """Get metrics service status."""
        return {
            "status": "healthy" if self._running else "stopped",
            "initialized": self._initialized,
            "running": self._running,
            "metrics_count": len(self._metrics),
            "counters_count": len(self._counters),
            "gauges_count": len(self._gauges),
            "histograms_count": len(self._histograms),
            "uptime": time.time() - self._start_time,
        }

    def reset_metrics(self):
        """Reset all metric points (keeps series definitions)."""
        logger.info("Resetting all metrics")
        for series in self._metrics.values():
            series.points.clear()
        self._counters.clear()
        self._gauges.clear()
        self._histograms.clear()
        logger.info("All metrics reset")

    # ── Prometheus text format export ─────────────────────────────────────────

    def prometheus_export(self, extra_lines: Optional[List[str]] = None) -> str:
        """Export all known series in Prometheus text exposition format.

        Caller can pass additional pre-built lines (e.g. per-zone/device gauges)
        that are appended verbatim before the final newline.
        """
        lines: List[str] = []

        for name, series in self._metrics.items():
            latest = series.get_latest()
            if latest is None:
                continue
            prom_name = f"ruview_{name}"
            lines.append(f"# HELP {prom_name} {series.description}")
            lines.append(f"# TYPE {prom_name} gauge")
            label_str = ""
            if latest.labels:
                pairs = ",".join(f'{k}="{v}"' for k, v in latest.labels.items())
                label_str = f"{{{pairs}}}"
            lines.append(f"{prom_name}{label_str} {latest.value}")

        # Histograms
        for name, values in self._histograms.items():
            if not values:
                continue
            stats = self.get_histogram_stats(name)
            prom_name = f"ruview_{name}_seconds"
            lines.append(f"# HELP {prom_name} {name} histogram")
            lines.append(f"# TYPE {prom_name} summary")
            lines.append(f'{prom_name}{{quantile="0.5"}} {stats.get("p50", 0)}')
            lines.append(f'{prom_name}{{quantile="0.9"}} {stats.get("p90", 0)}')
            lines.append(f'{prom_name}{{quantile="0.99"}} {stats.get("p99", 0)}')
            lines.append(f"{prom_name}_sum {stats.get('sum', 0)}")
            lines.append(f"{prom_name}_count {stats.get('count', 0)}")

        if extra_lines:
            lines.extend(extra_lines)

        return "\n".join(lines) + "\n"
