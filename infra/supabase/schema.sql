-- RuView MVP - Supabase Schema
-- Run this in Supabase SQL Editor

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Devices table
CREATE TABLE IF NOT EXISTS devices (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    mac TEXT UNIQUE NOT NULL,
    status TEXT DEFAULT 'offline' CHECK (status IN ('online', 'offline', 'error')),
    x FLOAT DEFAULT 0,
    y FLOAT DEFAULT 0,
    signal_strength FLOAT,
    firmware_version TEXT DEFAULT '0.5.0',
    last_seen TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Zones table
CREATE TABLE IF NOT EXISTS zones (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    polygon JSONB NOT NULL DEFAULT '[]',
    status TEXT DEFAULT 'inactive' CHECK (status IN ('active', 'inactive', 'alert')),
    presence_count INT DEFAULT 0,
    last_activity TIMESTAMPTZ,
    floor_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Events table
CREATE TABLE IF NOT EXISTS events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    type TEXT NOT NULL CHECK (type IN (
        'presence_detected', 'motion_active', 'stationary_detected',
        'fall_suspected', 'fall_confirmed', 'zone_intrusion',
        'device_offline', 'signal_weak'
    )),
    severity TEXT NOT NULL CHECK (severity IN ('info', 'warning', 'critical')),
    zone TEXT,
    device_id TEXT NOT NULL,
    confidence FLOAT DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Signal logs table (time-series)
CREATE TABLE IF NOT EXISTS signal_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    device_id TEXT NOT NULL,
    rssi FLOAT,
    snr FLOAT,
    csi_amplitude FLOAT,
    motion_index FLOAT,
    breathing_rate FLOAT,
    heart_rate FLOAT,
    channel INT,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

-- Alerts table
CREATE TABLE IF NOT EXISTS alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_id UUID REFERENCES events(id),
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'acknowledged', 'resolved')),
    acknowledged_by TEXT,
    acknowledged_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_events_type ON events(type);
CREATE INDEX IF NOT EXISTS idx_events_device ON events(device_id);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_events_severity ON events(severity);
CREATE INDEX IF NOT EXISTS idx_signal_logs_device ON signal_logs(device_id);
CREATE INDEX IF NOT EXISTS idx_signal_logs_timestamp ON signal_logs(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_devices_status ON devices(status);
CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status);

-- Enable Realtime for key tables
ALTER PUBLICATION supabase_realtime ADD TABLE devices;
ALTER PUBLICATION supabase_realtime ADD TABLE events;
ALTER PUBLICATION supabase_realtime ADD TABLE zones;
ALTER PUBLICATION supabase_realtime ADD TABLE alerts;

-- RLS Policies (permissive for MVP)
ALTER TABLE devices ENABLE ROW LEVEL SECURITY;
ALTER TABLE zones ENABLE ROW LEVEL SECURITY;
ALTER TABLE events ENABLE ROW LEVEL SECURITY;
ALTER TABLE signal_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE alerts ENABLE ROW LEVEL SECURITY;

-- Allow anon read/write for MVP (tighten in production)
CREATE POLICY "Allow all for anon" ON devices FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all for anon" ON zones FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all for anon" ON events FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all for anon" ON signal_logs FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all for anon" ON alerts FOR ALL USING (true) WITH CHECK (true);

-- Seed data: demo devices
INSERT INTO devices (name, mac, status, x, y, signal_strength, firmware_version)
VALUES
    ('Node #1', '0C:B8:15:F5:6F:14', 'online', 200, 200, -45.0, '0.5.0'),
    ('Node #2', '0C:B8:15:F5:6F:15', 'online', 500, 400, -52.0, '0.5.0')
ON CONFLICT (mac) DO NOTHING;

-- Seed data: demo zones
INSERT INTO zones (name, polygon, status, presence_count)
VALUES
    ('Living Room', '[{"x":50,"y":50},{"x":400,"y":50},{"x":400,"y":350},{"x":50,"y":350}]', 'active', 1),
    ('Bedroom', '[{"x":420,"y":50},{"x":750,"y":50},{"x":750,"y":350},{"x":420,"y":350}]', 'inactive', 0),
    ('Hallway', '[{"x":50,"y":370},{"x":750,"y":370},{"x":750,"y":450},{"x":50,"y":450}]', 'inactive', 0);
