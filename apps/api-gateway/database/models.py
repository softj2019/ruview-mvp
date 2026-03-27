"""
SQLAlchemy 2.0 ORM models for RuView API Gateway.

Tables:
  - devices          — ESP32 노드 (6대)
  - detection_events — 낙상/재실/모션 감지 이벤트
  - csi_records      — CSI 원시 데이터 (호흡/심박 포함)
  - zones            — 4존 평면도 구역
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy.types import JSON, TypeDecorator

from database import Base


# ── Portable UUID helper ─────────────────────────────────────────────────────

class UUIDType(TypeDecorator):
    """UUID stored as TEXT in SQLite, native UUID in PostgreSQL."""

    impl = String(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(String(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        return str(value)


def new_uuid() -> str:
    return str(uuid.uuid4())


# ── Timestamp mixin ──────────────────────────────────────────────────────────

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# ── Device ───────────────────────────────────────────────────────────────────

class Device(TimestampMixin, Base):
    """ESP32 노드 장치 테이블."""

    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(
        UUIDType, primary_key=True, default=new_uuid, nullable=False
    )
    node_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="offline", nullable=False
    )
    zone_id: Mapped[str | None] = mapped_column(
        UUIDType, ForeignKey("zones.id", ondelete="SET NULL"), nullable=True
    )
    last_seen: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    firmware_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    hardware_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    mac_address: Mapped[str | None] = mapped_column(String(17), nullable=True)
    # 평면도 좌표
    pos_x: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    pos_y: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    # 최신 CSI 지표 (캐시)
    signal_strength: Mapped[float | None] = mapped_column(Float, nullable=True)
    motion_energy: Mapped[float | None] = mapped_column(Float, nullable=True)
    breathing_bpm: Mapped[float | None] = mapped_column(Float, nullable=True)
    heart_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    events: Mapped[list["DetectionEvent"]] = relationship(
        "DetectionEvent", back_populates="device", cascade="all, delete-orphan"
    )
    csi_records: Mapped[list["CSIRecord"]] = relationship(
        "CSIRecord", back_populates="device", cascade="all, delete-orphan"
    )
    zone: Mapped["Zone | None"] = relationship("Zone", back_populates="devices")

    __table_args__ = (
        Index("idx_device_node_id", "node_id"),
        Index("idx_device_status", "status"),
        Index("idx_device_zone_id", "zone_id"),
        CheckConstraint(
            "status IN ('online','offline','maintenance','error')",
            name="ck_device_status",
        ),
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "node_id": self.node_id,
            "ip": self.ip,
            "name": self.name,
            "status": self.status,
            "zone_id": self.zone_id,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "firmware_version": self.firmware_version,
            "hardware_version": self.hardware_version,
            "mac_address": self.mac_address,
            "pos_x": self.pos_x,
            "pos_y": self.pos_y,
            "signal_strength": self.signal_strength,
            "motion_energy": self.motion_energy,
            "breathing_bpm": self.breathing_bpm,
            "heart_rate": self.heart_rate,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# ── DetectionEvent ────────────────────────────────────────────────────────────

class DetectionEvent(TimestampMixin, Base):
    """감지 이벤트 (낙상, 재실, 모션 등)."""

    __tablename__ = "detection_events"

    id: Mapped[str] = mapped_column(
        UUIDType, primary_key=True, default=new_uuid, nullable=False
    )
    device_id: Mapped[str | None] = mapped_column(
        UUIDType, ForeignKey("devices.id", ondelete="SET NULL"), nullable=True
    )
    zone_id: Mapped[str | None] = mapped_column(
        UUIDType, ForeignKey("zones.id", ondelete="SET NULL"), nullable=True
    )
    # 이벤트 분류
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(
        String(16), default="info", nullable=False
    )
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    # 낙상 상태 필드
    is_fall: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # 추가 메타데이터 (JSON)
    metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Relationships
    device: Mapped["Device | None"] = relationship("Device", back_populates="events")
    zone: Mapped["Zone | None"] = relationship("Zone", back_populates="events")

    __table_args__ = (
        Index("idx_event_device_id", "device_id"),
        Index("idx_event_zone_id", "zone_id"),
        Index("idx_event_type", "type"),
        Index("idx_event_severity", "severity"),
        Index("idx_event_created_at", "created_at"),
        CheckConstraint(
            "severity IN ('info','warning','critical')",
            name="ck_event_severity",
        ),
        CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="ck_event_confidence",
        ),
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "device_id": self.device_id,
            "zone_id": self.zone_id,
            "type": self.type,
            "severity": self.severity,
            "confidence": self.confidence,
            "is_fall": self.is_fall,
            "acknowledged": self.acknowledged,
            "acknowledged_at": (
                self.acknowledged_at.isoformat() if self.acknowledged_at else None
            ),
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# ── CSIRecord ────────────────────────────────────────────────────────────────

class CSIRecord(TimestampMixin, Base):
    """CSI 원시 데이터 레코드 (amplitude/phase + 생체지표)."""

    __tablename__ = "csi_records"

    id: Mapped[str] = mapped_column(
        UUIDType, primary_key=True, default=new_uuid, nullable=False
    )
    device_id: Mapped[str] = mapped_column(
        UUIDType, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False
    )
    # 타임스탬프 (ESP32 기준)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    # CSI 데이터 (JSON 배열로 저장)
    amplitude_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    phase_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # 처리된 생체 지표
    breathing_bpm: Mapped[float | None] = mapped_column(Float, nullable=True)
    heart_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    motion_energy: Mapped[float | None] = mapped_column(Float, nullable=True)
    rssi: Mapped[float | None] = mapped_column(Float, nullable=True)
    snr: Mapped[float | None] = mapped_column(Float, nullable=True)
    num_subcarriers: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 처리 상태
    processing_status: Mapped[str] = mapped_column(
        String(16), default="raw", nullable=False
    )
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Relationship
    device: Mapped["Device"] = relationship("Device", back_populates="csi_records")

    __table_args__ = (
        Index("idx_csi_device_id", "device_id"),
        Index("idx_csi_captured_at", "captured_at"),
        Index("idx_csi_processing_status", "processing_status"),
        CheckConstraint(
            "processing_status IN ('raw','processed','failed')",
            name="ck_csi_processing_status",
        ),
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "device_id": self.device_id,
            "captured_at": self.captured_at.isoformat() if self.captured_at else None,
            "amplitude_json": self.amplitude_json,
            "phase_json": self.phase_json,
            "breathing_bpm": self.breathing_bpm,
            "heart_rate": self.heart_rate,
            "motion_energy": self.motion_energy,
            "rssi": self.rssi,
            "snr": self.snr,
            "num_subcarriers": self.num_subcarriers,
            "processing_status": self.processing_status,
            "is_valid": self.is_valid,
            "quality_score": self.quality_score,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ── Zone ────────────────────────────────────────────────────────────────────

class Zone(TimestampMixin, Base):
    """4존 평면도 구역."""

    __tablename__ = "zones"

    id: Mapped[str] = mapped_column(
        UUIDType, primary_key=True, default=new_uuid, nullable=False
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    # 폴리곤 꼭짓점 [{x, y}, ...]
    polygon_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # 층 정보 (멀티플로어 지원)
    floor: Mapped[str] = mapped_column(String(16), default="1F", nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), default="active", nullable=False
    )
    presence_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_activity: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    devices: Mapped[list["Device"]] = relationship("Device", back_populates="zone")
    events: Mapped[list["DetectionEvent"]] = relationship(
        "DetectionEvent", back_populates="zone"
    )

    __table_args__ = (
        Index("idx_zone_floor", "floor"),
        Index("idx_zone_status", "status"),
        CheckConstraint(
            "status IN ('active','inactive','alert')", name="ck_zone_status"
        ),
        CheckConstraint(
            "presence_count >= 0", name="ck_zone_presence_count"
        ),
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "polygon_json": self.polygon_json,
            "floor": self.floor,
            "status": self.status,
            "presence_count": self.presence_count,
            "last_activity": (
                self.last_activity.isoformat() if self.last_activity else None
            ),
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


__all__ = ["Device", "DetectionEvent", "CSIRecord", "Zone", "Base"]
