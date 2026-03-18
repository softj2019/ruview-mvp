import { useEffect, useRef, useCallback } from 'react';

interface UseWebSocketOptions {
  url: string;
  onMessage: (data: unknown) => void;
  onOpen?: () => void;
  onClose?: () => void;
  onError?: (error: Event) => void;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
}

export function useWebSocket({
  url,
  onMessage,
  onOpen,
  onClose,
  onError,
  reconnectInterval = 3000,
  maxReconnectAttempts = 10,
}: UseWebSocketOptions) {
  const wsRef = useRef<WebSocket | null>(null);
  const attemptsRef = useRef(0);
  const timerRef = useRef<ReturnType<typeof setTimeout>>();
  const callbacksRef = useRef({ onMessage, onOpen, onClose, onError });

  // Update callbacks ref without triggering reconnect
  callbacksRef.current = { onMessage, onOpen, onClose, onError };

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    try {
      const ws = new WebSocket(url);

      ws.onopen = () => {
        attemptsRef.current = 0;
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
      // WebSocket construction can fail (e.g., invalid URL)
      console.warn('[WS] Failed to create WebSocket connection');
    }
  }, [url, reconnectInterval, maxReconnectAttempts]);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(timerRef.current);
      wsRef.current?.close();
    };
  }, [connect]);

  const send = useCallback((data: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(typeof data === 'string' ? data : JSON.stringify(data));
    }
  }, []);

  return { send };
}
