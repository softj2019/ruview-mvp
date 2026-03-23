/**
 * SensingBroker — Durable Object that relays WebSocket messages
 * between external browser clients (front) and the local signal-adapter (agent).
 *
 * Pattern: Raw string relay, no message parsing.
 * Front → Broker → Agent (commands, config)
 * Agent → Broker → Front (sensing data, vitals, events)
 */

export class SensingBroker {
  private frontSockets = new Set<WebSocket>();
  private agentSocket: WebSocket | null = null;
  private state: DurableObjectState;

  constructor(state: DurableObjectState) {
    this.state = state;
  }

  async fetch(request: Request): Promise<Response> {
    const url = new URL(request.url);

    if (url.pathname === '/health') {
      return Response.json({
        status: 'ok',
        frontClients: this.frontSockets.size,
        agentConnected: this.agentSocket !== null,
      });
    }

    if (url.pathname === '/ws/front') {
      return this.handleFront(request);
    }

    if (url.pathname === '/ws/agent') {
      return this.handleAgent(request);
    }

    return new Response('Not Found', { status: 404 });
  }

  private handleFront(request: Request): Response {
    const pair = new WebSocketPair();
    const [client, server] = Object.values(pair);

    server.accept();
    this.frontSockets.add(server);

    server.addEventListener('message', (event) => {
      // Front → Agent relay (commands, config changes)
      const data = typeof event.data === 'string' ? event.data : '';
      if (this.agentSocket) {
        try {
          this.agentSocket.send(data);
        } catch {
          // Agent disconnected
        }
      } else {
        server.send(JSON.stringify({
          type: 'error',
          payload: { message: 'Agent not connected. Sensing data unavailable.' },
        }));
      }
    });

    server.addEventListener('close', () => {
      this.frontSockets.delete(server);
    });

    server.addEventListener('error', () => {
      this.frontSockets.delete(server);
    });

    return new Response(null, { status: 101, webSocket: client });
  }

  private handleAgent(request: Request): Response {
    const pair = new WebSocketPair();
    const [client, server] = Object.values(pair);

    server.accept();

    // Only one agent connection at a time
    if (this.agentSocket) {
      try {
        this.agentSocket.close(1000, 'Replaced by new agent connection');
      } catch {
        // ignore
      }
    }
    this.agentSocket = server;

    // Notify front clients that agent is connected
    this.fanOut(JSON.stringify({
      type: 'system',
      payload: { message: 'Sensing server connected', agentConnected: true },
    }));

    server.addEventListener('message', (event) => {
      // Agent → Front relay (sensing data, vitals, events)
      const data = typeof event.data === 'string' ? event.data : '';
      this.fanOut(data);
    });

    server.addEventListener('close', () => {
      this.agentSocket = null;
      this.fanOut(JSON.stringify({
        type: 'system',
        payload: { message: 'Sensing server disconnected', agentConnected: false },
      }));
    });

    server.addEventListener('error', () => {
      this.agentSocket = null;
    });

    return new Response(null, { status: 101, webSocket: client });
  }

  private fanOut(data: string): void {
    for (const ws of this.frontSockets) {
      try {
        ws.send(data);
      } catch {
        this.frontSockets.delete(ws);
      }
    }
  }
}
