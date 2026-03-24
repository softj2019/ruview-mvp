import { useEffect, useRef, useCallback } from 'react';

interface UseWebSocketOptions {
  url: string;
  onMessage: (data: unknown) => void;
  onOpen?: () => void;
  onClose?: () => void;
  onError?: (error: Event) => void;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
  heartbeatInterval?: number;
}

export function useWebSocket({
  url,
  onMessage,
  onOpen,
  onClose,
  onError,
  reconnectInterval = 3000,
  maxReconnectAttempts = 10,
  heartbeatInterval = 30000,
}: UseWebSocketOptions) {
  const wsRef = useRef<WebSocket | null>(null);
  const attemptsRef = useRef(0);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const heartbeatRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const callbacksRef = useRef({ onMessage, onOpen, onClose, onError });

  callbacksRef.current = { onMessage, onOpen, onClose, onError };

  const stopHeartbeat = useCallback(() => {
    if (heartbeatRef.current !== null) {
      clearInterval(heartbeatRef.current);
      heartbeatRef.current = null;
    }
  }, []);

  const startHeartbeat = useCallback(() => {
    stopHeartbeat();
    heartbeatRef.current = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'ping' }));
      }
    }, heartbeatInterval);
  }, [heartbeatInterval, stopHeartbeat]);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;
    if (wsRef.current?.readyState === WebSocket.CONNECTING) return;

    try {
      const ws = new WebSocket(url);

      ws.onopen = () => {
        attemptsRef.current = 0;
        startHeartbeat();
        callbacksRef.current.onOpen?.();
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          callbacksRef.current.onMessage(data);
        } catch {
          callbacksRef.current.onMessage(event.data);
        }
      };

      ws.onclose = () => {
        stopHeartbeat();
        callbacksRef.current.onClose?.();
        if (attemptsRef.current < maxReconnectAttempts) {
          const delay = reconnectInterval * Math.pow(2, attemptsRef.current);
          timerRef.current = setTimeout(() => {
            attemptsRef.current++;
            connect();
          }, Math.min(delay, 30000));
        }
      };

      ws.onerror = (error) => {
        callbacksRef.current.onError?.(error);
      };

      wsRef.current = ws;
    } catch {
      console.warn('[WS] Failed to create WebSocket connection');
    }
  }, [url, reconnectInterval, maxReconnectAttempts, startHeartbeat, stopHeartbeat]);

  useEffect(() => {
    connect();
    return () => {
      stopHeartbeat();
      if (timerRef.current !== null) {
        clearTimeout(timerRef.current);
      }
      wsRef.current?.close();
    };
  }, [connect, stopHeartbeat]);

  const send = useCallback((data: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(typeof data === 'string' ? data : JSON.stringify(data));
    }
  }, []);

  return { send };
}
