import { useRef, useCallback, useEffect, useState } from 'react';

interface UseReconnectableWsOptions {
  maxRetries?: number;
  baseDelay?: number;
  maxDelay?: number;
  onMessage?: (data: unknown) => void;
  onOpen?: () => void;
  onClose?: () => void;
  onError?: () => void;
}

interface UseReconnectableWsReturn {
  wsRef: React.MutableRefObject<WebSocket | null>;
  isConnecting: boolean;
  isReconnecting: boolean;
  reconnectCount: number;
  connect: (url: string, authPayload?: Record<string, unknown>) => void;
  disconnect: () => void;
}

export function useReconnectableWs(options: UseReconnectableWsOptions = {}): UseReconnectableWsReturn {
  const wsRef = useRef<WebSocket | null>(null);
  const [isConnecting, setIsConnecting] = useState(false);
  const [isReconnecting, setIsReconnecting] = useState(false);
  const [reconnectCount, setReconnectCount] = useState(0);

  const retryCountRef = useRef(0);
  const urlRef = useRef('');
  const authPayloadRef = useRef<Record<string, unknown> | undefined>(undefined);
  const shouldReconnectRef = useRef(true);
  const reconnectTimerRef = useRef<NodeJS.Timeout | null>(null);
  const onMessageRef = useRef(options.onMessage);
  const onOpenRef = useRef(options.onOpen);
  const onCloseRef = useRef(options.onClose);
  const onErrorRef = useRef(options.onError);
  const setupListenersRef = useRef<(ws: WebSocket) => void>(() => {});

  // Keep refs updated via effect
  useEffect(() => {
    onMessageRef.current = options.onMessage;
    onOpenRef.current = options.onOpen;
    onCloseRef.current = options.onClose;
    onErrorRef.current = options.onError;
  });

  const maxRetries = options.maxRetries ?? 5;
  const baseDelay = options.baseDelay ?? 1000;
  const maxDelay = options.maxDelay ?? 30000;

  const clearReconnectTimer = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
  }, []);

  const setupListeners = useCallback((ws: WebSocket) => {
    ws.onopen = () => {
      retryCountRef.current = 0;
      setIsConnecting(false);
      setIsReconnecting(false);
      setReconnectCount(0);
      onOpenRef.current?.();
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onMessageRef.current?.(data);
      } catch {
        onMessageRef.current?.(event.data);
      }
    };

    ws.onclose = (event) => {
      wsRef.current = null;
      setIsConnecting(false);
      onCloseRef.current?.();

      // Reconexão automática
      if (shouldReconnectRef.current && retryCountRef.current < maxRetries && !event.wasClean) {
        const delay = Math.min(baseDelay * Math.pow(2, retryCountRef.current), maxDelay);
        retryCountRef.current += 1;
        setReconnectCount(retryCountRef.current);
        setIsReconnecting(true);

        clearReconnectTimer();
        reconnectTimerRef.current = setTimeout(() => {
          if (shouldReconnectRef.current && urlRef.current) {
            const newWs = new WebSocket(urlRef.current);
            wsRef.current = newWs;
            // Reenviar auth após reconexão
            if (authPayloadRef.current) {
              newWs.addEventListener('open', () => {
                newWs.send(JSON.stringify(authPayloadRef.current));
              }, { once: true });
            }
            setupListenersRef.current(newWs);
          }
        }, delay);
      }
    };

    ws.onerror = () => {
      onErrorRef.current?.();
    };
  }, [maxRetries, baseDelay, maxDelay, clearReconnectTimer]);

  // Update the ref after setupListeners is defined
  useEffect(() => {
    setupListenersRef.current = setupListeners;
  }, [setupListeners]);

  const connect = useCallback((url: string, authPayload?: Record<string, unknown>) => {
    if (wsRef.current) {
      wsRef.current.close();
    }

    shouldReconnectRef.current = true;
    urlRef.current = url;
    authPayloadRef.current = authPayload;
    retryCountRef.current = 0;

    setIsConnecting(true);
    setIsReconnecting(false);
    setReconnectCount(0);

    const ws = new WebSocket(url);
    wsRef.current = ws;

    if (authPayload) {
      ws.addEventListener('open', () => {
        ws.send(JSON.stringify(authPayload));
      }, { once: true });
    }

    setupListeners(ws);
  }, [setupListeners]);

  const disconnect = useCallback(() => {
    shouldReconnectRef.current = false;
    clearReconnectTimer();
    if (wsRef.current) {
      wsRef.current.close(1000, 'manual');
      wsRef.current = null;
    }
    setIsConnecting(false);
    setIsReconnecting(false);
    setReconnectCount(0);
  }, [clearReconnectTimer]);

  useEffect(() => {
    return () => {
      shouldReconnectRef.current = false;
      clearReconnectTimer();
      if (wsRef.current) {
        wsRef.current.close(1000, 'unmount');
      }
    };
  }, [clearReconnectTimer]);

  return { wsRef, isConnecting, isReconnecting, reconnectCount, connect, disconnect };
}
