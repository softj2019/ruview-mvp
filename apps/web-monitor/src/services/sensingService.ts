/**
 * sensingService — CSI 센싱 데이터 수집 서비스
 * Phase 2-15 | 참조: ruvnet-RuView/ui/services/sensing.service.js
 *
 * signal-adapter WebSocket(ws://localhost:8001/ws/signal) 연결 관리.
 * 재연결 지수 백오프, RSSI 히스토리, FPS 계산, 시뮬레이션 폴백 포함.
 */

const WS_URL = 'ws://localhost:8001/ws/signal';
const RECONNECT_DELAYS_MS = [1000, 2000, 4000, 8000, 16000] as const;
const MAX_RECONNECT_ATTEMPTS = 20;
/** 이 횟수 이상 실패 후 클라이언트 시뮬레이션 시작 */
const SIM_FALLBACK_AFTER = 5;
const SIMULATION_INTERVAL_MS = 500;
const RSSI_HISTORY_MAX = 100;

// ---- 공개 타입 ---------------------------------------------------------------

export type ConnectionState =
  | 'disconnected'
  | 'connecting'
  | 'connected'
  | 'reconnecting'
  | 'simulated';

export type DataSource = 'live' | 'server-simulated' | 'reconnecting' | 'simulated';

export interface SensingFeatures {
  mean_rssi: number;
  variance: number;
  std: number;
  motion_band_power: number;
  breathing_band_power: number;
  dominant_freq_hz: number;
  change_points: number;
  spectral_power: number;
  range: number;
  iqr: number;
  skewness: number;
  kurtosis: number;
}

export interface SensingClassification {
  motion_level: 'absent' | 'present_still' | 'active';
  presence: boolean;
  confidence: number;
}

export interface SignalField {
  grid_size: [number, number, number];
  values: number[];
}

export interface SensingData {
  type: string;
  timestamp: number;
  source: string;
  _simulated?: boolean;
  nodes: Array<{
    node_id: number;
    rssi_dbm: number;
    position: [number, number, number];
    amplitude: number[];
    subcarrier_count: number;
  }>;
  features: SensingFeatures;
  classification: SensingClassification;
  signal_field?: SignalField;
}

type DataCallback = (data: SensingData) => void;
type StateCallback = (state: ConnectionState) => void;

// ---- SensingService 클래스 ---------------------------------------------------

class SensingService {
  private _ws: WebSocket | null = null;
  private _listeners = new Set<DataCallback>();
  private _stateListeners = new Set<StateCallback>();

  private _reconnectAttempt = 0;
  private _reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private _simTimer: ReturnType<typeof setInterval> | null = null;

  private _state: ConnectionState = 'disconnected';
  private _dataSource: DataSource = 'reconnecting';
  private _serverSource: string | null = null;
  private _lastMessage: SensingData | null = null;

  // RSSI 링 버퍼
  private _rssiHistory: number[] = [];

  // FPS 계산용
  private _fpsFrameTimes: number[] = [];

  // ---- Public API -----------------------------------------------------------

  start(): void {
    this._connect();
  }

  stop(): void {
    this._clearTimers();
    if (this._ws) {
      this._ws.close(1000, 'client stop');
      this._ws = null;
    }
    this._setState('disconnected');
  }

  /**
   * 센싱 데이터 콜백 등록. 마지막 수신 데이터를 즉시 전달.
   * @returns unsubscribe 함수
   */
  onData(callback: DataCallback): () => void {
    this._listeners.add(callback);
    if (this._lastMessage) callback(this._lastMessage);
    return () => this._listeners.delete(callback);
  }

  /**
   * 연결 상태 변경 콜백 등록. 현재 상태를 즉시 전달.
   * @returns unsubscribe 함수
   */
  onStateChange(callback: StateCallback): () => void {
    this._stateListeners.add(callback);
    callback(this._state);
    return () => this._stateListeners.delete(callback);
  }

  /** RSSI 히스토리 복사본 반환 (최근 100개) */
  getRssiHistory(): number[] {
    return [...this._rssiHistory];
  }

  /** 현재 FPS 계산 (최근 1초 프레임 수) */
  getFps(): number {
    const now = performance.now();
    this._fpsFrameTimes = this._fpsFrameTimes.filter((t) => t > now - 1000);
    return this._fpsFrameTimes.length;
  }

  get state(): ConnectionState {
    return this._state;
  }

  get dataSource(): DataSource {
    return this._dataSource;
  }

  get serverSource(): string | null {
    return this._serverSource;
  }

  // ---- WebSocket 연결 -------------------------------------------------------

  private _connect(): void {
    if (
      this._ws &&
      (this._ws.readyState === WebSocket.OPEN ||
        this._ws.readyState === WebSocket.CONNECTING)
    ) {
      return;
    }

    this._setState('connecting');

    try {
      this._ws = new WebSocket(WS_URL);
    } catch (err) {
      console.warn('[Sensing] WebSocket 생성 실패:', (err as Error).message);
      this._fallbackToSimulation();
      return;
    }

    this._ws.onopen = () => {
      console.info('[Sensing] 연결됨:', WS_URL);
      this._reconnectAttempt = 0;
      this._stopSimulation();
      this._setState('connected');
      void this._detectServerSource();
    };

    this._ws.onmessage = (evt: MessageEvent) => {
      try {
        const data = JSON.parse(evt.data as string) as SensingData;
        this._handleData(data);
      } catch (e) {
        console.warn('[Sensing] 잘못된 메시지:', (e as Error).message);
      }
    };

    this._ws.onerror = () => {
      // onclose에서 재연결 처리
    };

    this._ws.onclose = (evt: CloseEvent) => {
      console.info('[Sensing] 연결 종료 (code=%d)', evt.code);
      this._ws = null;
      if (evt.code !== 1000) {
        this._scheduleReconnect();
      } else {
        this._setState('disconnected');
        this._setDataSource('reconnecting');
      }
    };
  }

  private _scheduleReconnect(): void {
    if (this._reconnectAttempt >= MAX_RECONNECT_ATTEMPTS) {
      console.warn('[Sensing] 최대 재연결 횟수 도달, 시뮬레이션 전환');
      this._fallbackToSimulation();
      return;
    }

    const delay =
      RECONNECT_DELAYS_MS[
        Math.min(this._reconnectAttempt, RECONNECT_DELAYS_MS.length - 1)
      ];
    this._reconnectAttempt++;
    console.info(
      '[Sensing] %dms 후 재연결 (시도 %d/%d)',
      delay,
      this._reconnectAttempt,
      MAX_RECONNECT_ATTEMPTS,
    );

    this._setState('reconnecting');
    this._setDataSource('reconnecting');

    this._reconnectTimer = setTimeout(() => {
      this._reconnectTimer = null;
      this._connect();
    }, delay);

    // 일정 횟수 실패 후 시뮬레이션 병행
    if (
      this._reconnectAttempt >= SIM_FALLBACK_AFTER &&
      this._state !== 'simulated'
    ) {
      this._fallbackToSimulation();
    }
  }

  // ---- 시뮬레이션 폴백 -------------------------------------------------------

  private _fallbackToSimulation(): void {
    this._setState('simulated');
    this._setDataSource('simulated');
    if (this._simTimer) return;
    console.info('[Sensing] 시뮬레이션 모드 시작');

    this._simTimer = setInterval(() => {
      const data = this._generateSimulatedData();
      this._handleData(data);
    }, SIMULATION_INTERVAL_MS);
  }

  private _stopSimulation(): void {
    if (this._simTimer) {
      clearInterval(this._simTimer);
      this._simTimer = null;
    }
  }

  private _generateSimulatedData(): SensingData {
    const t = Date.now() / 1000;
    const baseRssi = -45;
    const variance = 1.5 + Math.sin(t * 0.1) * 1.0;
    const motionBand = 0.05 + Math.abs(Math.sin(t * 0.3)) * 0.15;
    const breathBand = 0.03 + Math.abs(Math.sin(t * 0.05)) * 0.08;
    const isPresent = variance > 0.8;
    const isActive = motionBand > 0.12;

    const gridSize = 20;
    const values: number[] = [];
    for (let iz = 0; iz < gridSize; iz++) {
      for (let ix = 0; ix < gridSize; ix++) {
        const cx = gridSize / 2;
        const cy = gridSize / 2;
        const dist = Math.sqrt((ix - cx) ** 2 + (iz - cy) ** 2);
        let v = Math.max(0, 1 - dist / (gridSize * 0.7)) * 0.3;
        const bx = cx + 3 * Math.sin(t * 0.2);
        const by = cy + 2 * Math.cos(t * 0.15);
        const bodyDist = Math.sqrt((ix - bx) ** 2 + (iz - by) ** 2);
        if (isPresent) {
          v += Math.exp((-bodyDist * bodyDist) / 8) * (0.3 + motionBand * 3);
        }
        values.push(Math.min(1, Math.max(0, v + Math.random() * 0.05)));
      }
    }

    return {
      type: 'sensing_update',
      timestamp: t,
      source: 'simulated',
      _simulated: true,
      nodes: [
        {
          node_id: 1,
          rssi_dbm: baseRssi + Math.sin(t * 0.5) * 3,
          position: [2, 0, 1.5],
          amplitude: [],
          subcarrier_count: 0,
        },
      ],
      features: {
        mean_rssi: baseRssi + Math.sin(t * 0.5) * 3,
        variance,
        std: Math.sqrt(variance),
        motion_band_power: motionBand,
        breathing_band_power: breathBand,
        dominant_freq_hz: 0.3 + Math.sin(t * 0.02) * 0.1,
        change_points: Math.floor(Math.random() * 3),
        spectral_power: motionBand + breathBand + Math.random() * 0.1,
        range: variance * 3,
        iqr: variance * 1.5,
        skewness: (Math.random() - 0.5) * 0.5,
        kurtosis: Math.random() * 2,
      },
      classification: {
        motion_level: isActive ? 'active' : isPresent ? 'present_still' : 'absent',
        presence: isPresent,
        confidence: isPresent ? 0.75 + Math.random() * 0.2 : 0.5 + Math.random() * 0.3,
      },
      signal_field: {
        grid_size: [gridSize, 1, gridSize],
        values,
      },
    };
  }

  // ---- 서버 소스 탐지 -------------------------------------------------------

  private async _detectServerSource(): Promise<void> {
    try {
      const resp = await fetch('/api/v1/status');
      if (resp.ok) {
        const json = (await resp.json()) as { source?: string };
        this._applyServerSource(json.source ?? null);
      } else {
        this._setDataSource('live');
      }
    } catch {
      this._setDataSource('live');
    }
  }

  private _applyServerSource(raw: string | null): void {
    this._serverSource = raw;
    if (raw === 'esp32' || raw === 'wifi' || raw === 'live') {
      this._setDataSource('live');
    } else if (raw === 'simulated' || raw === 'simulate') {
      this._setDataSource('server-simulated');
    } else {
      this._setDataSource('server-simulated');
    }
  }

  // ---- 데이터 처리 ----------------------------------------------------------

  private _handleData(data: SensingData): void {
    this._lastMessage = data;

    // FPS 추적
    this._fpsFrameTimes.push(performance.now());

    // 서버 소스 변경 감지
    if (data.source && this._state === 'connected') {
      if (data.source !== this._serverSource) {
        this._applyServerSource(data.source);
      }
    }

    // RSSI 히스토리 업데이트
    if (data.features?.mean_rssi != null) {
      this._rssiHistory.push(data.features.mean_rssi);
      if (this._rssiHistory.length > RSSI_HISTORY_MAX) {
        this._rssiHistory.shift();
      }
    }

    // 리스너 알림
    for (const cb of this._listeners) {
      try {
        cb(data);
      } catch (e) {
        console.error('[Sensing] 리스너 오류:', e);
      }
    }
  }

  // ---- 상태 관리 ------------------------------------------------------------

  private _setState(newState: ConnectionState): void {
    if (newState === this._state) return;
    this._state = newState;
    for (const cb of this._stateListeners) {
      try {
        cb(newState);
      } catch {
        // ignore
      }
    }
  }

  private _setDataSource(source: DataSource): void {
    if (source === this._dataSource) return;
    this._dataSource = source;
    // 상태 리스너 채널 재사용으로 dataSource 변경 알림
    for (const cb of this._stateListeners) {
      try {
        cb(this._state);
      } catch {
        // ignore
      }
    }
  }

  private _clearTimers(): void {
    this._stopSimulation();
    if (this._reconnectTimer) {
      clearTimeout(this._reconnectTimer);
      this._reconnectTimer = null;
    }
  }
}

// 싱글턴 인스턴스
export const sensingService = new SensingService();
