/**
 * RuView Relay Worker — Cloudflare Workers entry point.
 *
 * Routes:
 *   GET  /health                       → Worker health
 *   GET  /api/front/ws?session=ID      → External browser WebSocket
 *   GET  /api/agent/ws?session=ID      → Local signal-adapter outbound WebSocket
 *   GET  /api/broker/health?session=ID → Broker session health
 */

export { SensingBroker } from './broker';

interface Env {
  SENSING_BROKER: DurableObjectNamespace;
  AGENT_SERVICE_TOKEN?: string;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    const path = url.pathname;

    // Health check
    if (path === '/health') {
      return Response.json({ status: 'ok', service: 'ruview-relay' });
    }

    // All /api/* routes need a session ID
    const sessionId = url.searchParams.get('session') || 'default';

    if (path === '/api/front/ws') {
      // External browser connects here
      const brokerId = env.SENSING_BROKER.idFromName(sessionId);
      const broker = env.SENSING_BROKER.get(brokerId);
      return broker.fetch(new Request('http://internal/ws/front', request));
    }

    if (path === '/api/agent/ws') {
      // Local signal-adapter connects here (outbound from office)
      // Phase E: token check
      // const token = request.headers.get('Authorization')?.replace('Bearer ', '');
      // if (token !== env.AGENT_SERVICE_TOKEN) {
      //   return new Response('Unauthorized', { status: 401 });
      // }
      const brokerId = env.SENSING_BROKER.idFromName(sessionId);
      const broker = env.SENSING_BROKER.get(brokerId);
      return broker.fetch(new Request('http://internal/ws/agent', request));
    }

    if (path === '/api/broker/health') {
      const brokerId = env.SENSING_BROKER.idFromName(sessionId);
      const broker = env.SENSING_BROKER.get(brokerId);
      return broker.fetch(new Request('http://internal/health'));
    }

    return new Response('Not Found', { status: 404 });
  },
};
