-- ============================================================
-- RuView API Gateway — Initial Schema (001_initial.sql)
-- SQLite 및 PostgreSQL 호환
-- ============================================================

-- 존 테이블 (Device 보다 먼저 생성 — FK 참조)
CREATE TABLE IF NOT EXISTS zones (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    polygon_json    TEXT,                        -- JSON array of {x, y}
    floor           TEXT NOT NULL DEFAULT '1F',
    status          TEXT NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active','inactive','alert')),
    presence_count  INTEGER NOT NULL DEFAULT 0
                        CHECK (presence_count >= 0),
    last_activity   DATETIME,
    description     TEXT,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_zone_floor   ON zones (floor);
CREATE INDEX IF NOT EXISTS idx_zone_status  ON zones (status);

-- 디바이스 테이블 (ESP32 노드)
CREATE TABLE IF NOT EXISTS devices (
    id               TEXT PRIMARY KEY,
    node_id          TEXT NOT NULL UNIQUE,
    ip               TEXT,
    name             TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'offline'
                         CHECK (status IN ('online','offline','maintenance','error')),
    zone_id          TEXT REFERENCES zones(id) ON DELETE SET NULL,
    last_seen        DATETIME,
    firmware_version TEXT,
    hardware_version TEXT,
    mac_address      TEXT,
    pos_x            REAL NOT NULL DEFAULT 0.0,
    pos_y            REAL NOT NULL DEFAULT 0.0,
    signal_strength  REAL,
    motion_energy    REAL,
    breathing_bpm    REAL,
    heart_rate       REAL,
    description      TEXT,
    created_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_device_node_id ON devices (node_id);
CREATE INDEX IF NOT EXISTS idx_device_status  ON devices (status);
CREATE INDEX IF NOT EXISTS idx_device_zone_id ON devices (zone_id);

-- 감지 이벤트 테이블
CREATE TABLE IF NOT EXISTS detection_events (
    id               TEXT PRIMARY KEY,
    device_id        TEXT REFERENCES devices(id) ON DELETE SET NULL,
    zone_id          TEXT REFERENCES zones(id) ON DELETE SET NULL,
    type             TEXT NOT NULL,
    severity         TEXT NOT NULL DEFAULT 'info'
                         CHECK (severity IN ('info','warning','critical')),
    confidence       REAL NOT NULL DEFAULT 0.0
                         CHECK (confidence >= 0.0 AND confidence <= 1.0),
    is_fall          INTEGER NOT NULL DEFAULT 0,  -- 0=false, 1=true
    acknowledged     INTEGER NOT NULL DEFAULT 0,
    acknowledged_at  DATETIME,
    metadata         TEXT,                        -- JSON object
    created_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_event_device_id  ON detection_events (device_id);
CREATE INDEX IF NOT EXISTS idx_event_zone_id    ON detection_events (zone_id);
CREATE INDEX IF NOT EXISTS idx_event_type       ON detection_events (type);
CREATE INDEX IF NOT EXISTS idx_event_severity   ON detection_events (severity);
CREATE INDEX IF NOT EXISTS idx_event_created_at ON detection_events (created_at);

-- CSI 레코드 테이블
CREATE TABLE IF NOT EXISTS csi_records (
    id                 TEXT PRIMARY KEY,
    device_id          TEXT NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    captured_at        DATETIME NOT NULL,
    amplitude_json     TEXT,   -- JSON float array
    phase_json         TEXT,   -- JSON float array
    breathing_bpm      REAL,
    heart_rate         REAL,
    motion_energy      REAL,
    rssi               REAL,
    snr                REAL,
    num_subcarriers    INTEGER,
    processing_status  TEXT NOT NULL DEFAULT 'raw'
                           CHECK (processing_status IN ('raw','processed','failed')),
    is_valid           INTEGER NOT NULL DEFAULT 1,
    quality_score      REAL,
    created_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_csi_device_id         ON csi_records (device_id);
CREATE INDEX IF NOT EXISTS idx_csi_captured_at       ON csi_records (captured_at);
CREATE INDEX IF NOT EXISTS idx_csi_processing_status ON csi_records (processing_status);

-- ============================================================
-- Seed data: 기본 4존 (1F 기준)
-- ============================================================
INSERT OR IGNORE INTO zones (id, name, polygon_json, floor, status, presence_count)
VALUES
    ('zone-1001', 'Room 1001',
     '[{"x":20,"y":20},{"x":210,"y":20},{"x":210,"y":380},{"x":20,"y":380}]',
     '1F', 'active', 0),
    ('zone-1002', 'Room 1002',
     '[{"x":210,"y":20},{"x":400,"y":20},{"x":400,"y":380},{"x":210,"y":380}]',
     '1F', 'active', 0),
    ('zone-1003', 'Room 1003',
     '[{"x":400,"y":20},{"x":590,"y":20},{"x":590,"y":380},{"x":400,"y":380}]',
     '1F', 'active', 0),
    ('zone-1004', 'Room 1004',
     '[{"x":590,"y":20},{"x":780,"y":20},{"x":780,"y":380},{"x":590,"y":380}]',
     '1F', 'active', 0);
