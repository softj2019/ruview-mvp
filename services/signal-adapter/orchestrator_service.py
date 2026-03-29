"""
Service orchestrator for RuView signal-adapter
Adapted from vendor/ruview-temp/v1/src/services/orchestrator.py
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from contextlib import asynccontextmanager

from health_check_service import HealthCheckService

logger = logging.getLogger(__name__)


class OrchestratorService:
    """Orchestrator that manages signal-adapter service lifecycle."""

    def __init__(self):
        self._services: Dict[str, Any] = {}
        self._background_tasks: List[asyncio.Task] = []
        self._initialized = False
        self._started = False

        # Health check is embedded; the runtime creates a shared instance
        # but the orchestrator also holds its own reference for lifecycle calls
        self.health_service = HealthCheckService()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self):
        """Initialize orchestrator and core services."""
        if self._initialized:
            logger.warning("OrchestratorService already initialized")
            return

        logger.info("Initializing OrchestratorService...")

        try:
            await self.health_service.initialize()

            self._services = {
                "health": self.health_service,
            }

            self._initialized = True
            logger.info("OrchestratorService initialized")

        except Exception as e:
            logger.error(f"Failed to initialize OrchestratorService: {e}")
            await self.shutdown()
            raise

    async def start(self):
        """Start the orchestrator and launch background tasks."""
        if not self._initialized:
            await self.initialize()

        if self._started:
            logger.warning("OrchestratorService already started")
            return

        logger.info("Starting OrchestratorService...")

        try:
            await self.health_service.start()
            await self._start_background_tasks()
            self._started = True
            logger.info("OrchestratorService started")

        except Exception as e:
            logger.error(f"Failed to start OrchestratorService: {e}")
            await self.shutdown()
            raise

    async def _start_background_tasks(self):
        """Start periodic background tasks."""
        task = asyncio.create_task(self._health_check_loop())
        self._background_tasks.append(task)
        logger.info(f"Started {len(self._background_tasks)} background task(s)")

    async def _health_check_loop(self):
        """Periodic health check loop (runs every 30 s)."""
        logger.info("Health check loop started")
        while True:
            try:
                await self.health_service.perform_health_checks()
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                logger.info("Health check loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in health check loop: {e}")
                await asyncio.sleep(30)

    async def shutdown(self):
        """Cancel background tasks and shut down services."""
        logger.info("Shutting down OrchestratorService...")

        try:
            for task in self._background_tasks:
                if not task.done():
                    task.cancel()

            if self._background_tasks:
                await asyncio.gather(*self._background_tasks, return_exceptions=True)
                self._background_tasks.clear()

            await self.health_service.shutdown()

            self._started = False
            self._initialized = False
            logger.info("OrchestratorService shut down")

        except Exception as e:
            logger.error(f"Error during OrchestratorService shutdown: {e}")

    # ------------------------------------------------------------------
    # Service registry helpers
    # ------------------------------------------------------------------

    async def restart_service(self, service_name: str):
        """Restart a named service."""
        logger.info(f"Restarting service: {service_name}")
        service = self._services.get(service_name)
        if not service:
            raise ValueError(f"Service not found: {service_name}")

        try:
            if hasattr(service, "stop"):
                await service.stop()
            elif hasattr(service, "shutdown"):
                await service.shutdown()

            if hasattr(service, "initialize"):
                await service.initialize()

            if hasattr(service, "start"):
                await service.start()

            logger.info(f"Service restarted: {service_name}")
        except Exception as e:
            logger.error(f"Failed to restart {service_name}: {e}")
            raise

    async def get_service_status(self) -> Dict[str, Any]:
        """Return status dict for every registered service."""
        status: Dict[str, Any] = {}
        for name, svc in self._services.items():
            try:
                if hasattr(svc, "get_status"):
                    result = svc.get_status()
                    # Support both sync and async get_status
                    if asyncio.iscoroutine(result):
                        status[name] = await result
                    else:
                        status[name] = result
                else:
                    status[name] = {"status": "unknown"}
            except Exception as e:
                status[name] = {"status": "error", "error": str(e)}
        return status

    async def get_service_info(self) -> Dict[str, Any]:
        """Return metadata about all registered services."""
        return {
            "total_services": len(self._services),
            "initialized": self._initialized,
            "started": self._started,
            "background_tasks": len(self._background_tasks),
            "services": {
                name: {"type": type(svc).__name__, "module": type(svc).__module__}
                for name, svc in self._services.items()
            },
        }

    def get_service(self, name: str) -> Optional[Any]:
        """Retrieve a service by name."""
        return self._services.get(name)

    @property
    def is_healthy(self) -> bool:
        """True when fully initialized and started."""
        return self._initialized and self._started

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    @asynccontextmanager
    async def service_context(self):
        """Async context manager for orchestrator lifecycle."""
        try:
            await self.initialize()
            await self.start()
            yield self
        finally:
            await self.shutdown()
