"""
Health check service for RuView signal-adapter
Adapted from vendor/ruview-temp/v1/src/services/health_check.py
"""

import asyncio
import logging
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status enumeration."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheck:
    """Health check result."""
    name: str
    status: HealthStatus
    message: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    duration_ms: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ServiceHealth:
    """Service health information."""
    name: str
    status: HealthStatus
    last_check: Optional[datetime] = None
    checks: List[HealthCheck] = field(default_factory=list)
    uptime: float = 0.0
    error_count: int = 0
    last_error: Optional[str] = None


class HealthCheckService:
    """Service for monitoring signal-adapter component health."""

    def __init__(self):
        self._services: Dict[str, ServiceHealth] = {}
        self._start_time = time.time()
        self._initialized = False
        self._running = False

    async def initialize(self):
        """Initialize health check service."""
        if self._initialized:
            return

        logger.info("Initializing health check service")

        # Initialize component health tracking (signal-adapter specific)
        self._services = {
            "api": ServiceHealth("api", HealthStatus.UNKNOWN),
            "udp_listener": ServiceHealth("udp_listener", HealthStatus.UNKNOWN),
            "csi_processor": ServiceHealth("csi_processor", HealthStatus.UNKNOWN),
            "event_engine": ServiceHealth("event_engine", HealthStatus.UNKNOWN),
            "fall_detector": ServiceHealth("fall_detector", HealthStatus.UNKNOWN),
            "websocket_manager": ServiceHealth("websocket_manager", HealthStatus.UNKNOWN),
        }

        self._initialized = True
        logger.info("Health check service initialized")

    async def start(self):
        """Start health check service."""
        if not self._initialized:
            await self.initialize()

        self._running = True
        logger.info("Health check service started")

    async def shutdown(self):
        """Shutdown health check service."""
        self._running = False
        logger.info("Health check service shut down")

    async def perform_health_checks(self) -> Dict[str, HealthCheck]:
        """Perform all health checks."""
        if not self._running:
            return {}

        logger.debug("Performing health checks")
        results = {}

        checks = [
            self._check_api_health(),
            self._check_udp_listener_health(),
            self._check_csi_processor_health(),
            self._check_event_engine_health(),
            self._check_fall_detector_health(),
            self._check_websocket_manager_health(),
        ]

        check_names = [
            "api", "udp_listener", "csi_processor",
            "event_engine", "fall_detector", "websocket_manager",
        ]

        check_results = await asyncio.gather(*checks, return_exceptions=True)

        for i, result in enumerate(check_results):
            check_name = check_names[i]

            if isinstance(result, Exception):
                health_check = HealthCheck(
                    name=check_name,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Health check failed: {result}",
                )
            else:
                health_check = result

            results[check_name] = health_check
            self._update_service_health(check_name, health_check)

        logger.debug(f"Completed {len(results)} health checks")
        return results

    async def _check_api_health(self) -> HealthCheck:
        """Check API health."""
        start_time = time.time()

        try:
            uptime = time.time() - self._start_time
            status = HealthStatus.HEALTHY
            message = "API is running normally"
            details = {
                "uptime_seconds": uptime,
                "uptime_formatted": str(timedelta(seconds=int(uptime))),
            }
        except Exception as e:
            status = HealthStatus.UNHEALTHY
            message = f"API health check failed: {e}"
            details = {"error": str(e)}

        duration_ms = (time.time() - start_time) * 1000
        return HealthCheck(
            name="api",
            status=status,
            message=message,
            duration_ms=duration_ms,
            details=details,
        )

    async def _check_udp_listener_health(self) -> HealthCheck:
        """Check UDP listener health."""
        start_time = time.time()

        try:
            # Import at runtime to avoid circular imports
            import main as _main  # noqa: PLC0415
            transport = getattr(_main.runtime, "transport", None)

            if transport is None:
                status = HealthStatus.UNKNOWN
                message = "UDP transport not yet started"
                details = {"transport": None}
            elif transport.is_closing():
                status = HealthStatus.UNHEALTHY
                message = "UDP transport is closing"
                details = {"transport": "closing"}
            else:
                status = HealthStatus.HEALTHY
                message = "UDP listener is active"
                details = {"transport": "active"}
        except Exception as e:
            status = HealthStatus.UNHEALTHY
            message = f"UDP listener check failed: {e}"
            details = {"error": str(e)}

        duration_ms = (time.time() - start_time) * 1000
        return HealthCheck(
            name="udp_listener",
            status=status,
            message=message,
            duration_ms=duration_ms,
            details=details,
        )

    async def _check_csi_processor_health(self) -> HealthCheck:
        """Check CSI processor health."""
        start_time = time.time()

        try:
            import main as _main  # noqa: PLC0415
            processor = getattr(_main.runtime, "csi_processor", None)

            if processor is None:
                status = HealthStatus.UNHEALTHY
                message = "CSI processor not initialized"
                details = {}
            else:
                status = HealthStatus.HEALTHY
                message = "CSI processor is operational"
                details = {"type": type(processor).__name__}
        except Exception as e:
            status = HealthStatus.UNHEALTHY
            message = f"CSI processor check failed: {e}"
            details = {"error": str(e)}

        duration_ms = (time.time() - start_time) * 1000
        return HealthCheck(
            name="csi_processor",
            status=status,
            message=message,
            duration_ms=duration_ms,
            details=details,
        )

    async def _check_event_engine_health(self) -> HealthCheck:
        """Check event engine health."""
        start_time = time.time()

        try:
            import main as _main  # noqa: PLC0415
            engine = getattr(_main.runtime, "event_engine", None)

            if engine is None:
                status = HealthStatus.UNHEALTHY
                message = "Event engine not initialized"
                details = {}
            else:
                status = HealthStatus.HEALTHY
                message = "Event engine is operational"
                details = {"type": type(engine).__name__}
        except Exception as e:
            status = HealthStatus.UNHEALTHY
            message = f"Event engine check failed: {e}"
            details = {"error": str(e)}

        duration_ms = (time.time() - start_time) * 1000
        return HealthCheck(
            name="event_engine",
            status=status,
            message=message,
            duration_ms=duration_ms,
            details=details,
        )

    async def _check_fall_detector_health(self) -> HealthCheck:
        """Check fall detector health."""
        start_time = time.time()

        try:
            import main as _main  # noqa: PLC0415
            detector = getattr(_main.runtime, "fall_detector", None)

            if detector is None:
                status = HealthStatus.UNHEALTHY
                message = "Fall detector not initialized"
                details = {}
            else:
                status = HealthStatus.HEALTHY
                message = "Fall detector is operational"
                details = {"type": type(detector).__name__}
        except Exception as e:
            status = HealthStatus.UNHEALTHY
            message = f"Fall detector check failed: {e}"
            details = {"error": str(e)}

        duration_ms = (time.time() - start_time) * 1000
        return HealthCheck(
            name="fall_detector",
            status=status,
            message=message,
            duration_ms=duration_ms,
            details=details,
        )

    async def _check_websocket_manager_health(self) -> HealthCheck:
        """Check WebSocket connection manager health."""
        start_time = time.time()

        try:
            import main as _main  # noqa: PLC0415
            manager = getattr(_main.runtime, "manager", None)

            if manager is None:
                status = HealthStatus.UNHEALTHY
                message = "WebSocket manager not initialized"
                details = {}
            else:
                connection_count = len(getattr(manager, "active_connections", []))
                status = HealthStatus.HEALTHY
                message = "WebSocket manager is operational"
                details = {"active_connections": connection_count}
        except Exception as e:
            status = HealthStatus.UNHEALTHY
            message = f"WebSocket manager check failed: {e}"
            details = {"error": str(e)}

        duration_ms = (time.time() - start_time) * 1000
        return HealthCheck(
            name="websocket_manager",
            status=status,
            message=message,
            duration_ms=duration_ms,
            details=details,
        )

    def _update_service_health(self, service_name: str, health_check: HealthCheck):
        """Update service health information."""
        if service_name not in self._services:
            self._services[service_name] = ServiceHealth(service_name, HealthStatus.UNKNOWN)

        service_health = self._services[service_name]
        service_health.status = health_check.status
        service_health.last_check = health_check.timestamp
        service_health.uptime = time.time() - self._start_time

        # Keep last 10 checks
        service_health.checks.append(health_check)
        if len(service_health.checks) > 10:
            service_health.checks.pop(0)

        # Update error tracking
        if health_check.status == HealthStatus.UNHEALTHY:
            service_health.error_count += 1
            service_health.last_error = health_check.message

    async def get_overall_health(self) -> Dict[str, Any]:
        """Get overall system health."""
        if not self._services:
            return {
                "status": HealthStatus.UNKNOWN.value,
                "message": "Health checks not initialized",
            }

        statuses = [service.status for service in self._services.values()]

        if all(s == HealthStatus.HEALTHY for s in statuses):
            overall_status = HealthStatus.HEALTHY
            message = "All components are healthy"
        elif any(s == HealthStatus.UNHEALTHY for s in statuses):
            overall_status = HealthStatus.UNHEALTHY
            unhealthy = [
                name for name, svc in self._services.items()
                if svc.status == HealthStatus.UNHEALTHY
            ]
            message = f"Unhealthy components: {', '.join(unhealthy)}"
        elif any(s == HealthStatus.DEGRADED for s in statuses):
            overall_status = HealthStatus.DEGRADED
            degraded = [
                name for name, svc in self._services.items()
                if svc.status == HealthStatus.DEGRADED
            ]
            message = f"Degraded components: {', '.join(degraded)}"
        else:
            overall_status = HealthStatus.UNKNOWN
            message = "System health status unknown"

        return {
            "status": overall_status.value,
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
            "uptime": time.time() - self._start_time,
            "components": {
                name: {
                    "status": svc.status.value,
                    "last_check": svc.last_check.isoformat() if svc.last_check else None,
                    "error_count": svc.error_count,
                    "last_error": svc.last_error,
                }
                for name, svc in self._services.items()
            },
        }

    async def get_service_health(self, service_name: str) -> Optional[Dict[str, Any]]:
        """Get health information for a specific component."""
        svc = self._services.get(service_name)
        if not svc:
            return None

        return {
            "name": svc.name,
            "status": svc.status.value,
            "last_check": svc.last_check.isoformat() if svc.last_check else None,
            "uptime": svc.uptime,
            "error_count": svc.error_count,
            "last_error": svc.last_error,
            "recent_checks": [
                {
                    "timestamp": chk.timestamp.isoformat(),
                    "status": chk.status.value,
                    "message": chk.message,
                    "duration_ms": chk.duration_ms,
                    "details": chk.details,
                }
                for chk in svc.checks[-5:]
            ],
        }

    def get_status(self) -> Dict[str, Any]:
        """Get health check service status (synchronous, safe for /health endpoint)."""
        statuses = {
            name: svc.status.value
            for name, svc in self._services.items()
        }
        all_healthy = all(s == HealthStatus.HEALTHY for s in self._services.values() if s)
        degraded = [
            name for name, svc in self._services.items()
            if svc.status in (HealthStatus.UNHEALTHY, HealthStatus.DEGRADED)
        ]
        return {
            "initialized": self._initialized,
            "running": self._running,
            "components_monitored": len(self._services),
            "uptime": time.time() - self._start_time,
            "component_statuses": statuses,
            "degraded_components": degraded,
        }
