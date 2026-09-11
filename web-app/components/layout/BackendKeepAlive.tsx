'use client';

import { useEffect } from 'react';

// Render's free tier spins the backend down after ~15 min of no inbound
// traffic, then cold-starts (~15-20s) on the next request — confirmed while
// reviewing the deployed app (docs/edge-cases.md, 2026-09-11). This pings a
// public, unauthenticated health endpoint every few minutes while anyone has
// the app open, keeping the backend warm for as long as the tool is
// actually in active use. It's a partial fix, not a full one — see the
// component's own note below.
const PING_INTERVAL_MS = 4 * 60 * 1000; // under Render's ~15 min idle window

function healthCheckUrl(): string {
  const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api/v1';
  // /health is mounted at the API root, not under /api/v1 (see
  // backend/app/main.py) — strip the versioned API path back off.
  const origin = apiBase.replace(/\/api\/v[0-9]+\/?$/, '');
  return `${origin}/health`;
}

export function BackendKeepAlive() {
  useEffect(() => {
    const ping = () => {
      fetch(healthCheckUrl(), { cache: 'no-store' }).catch(() => {
        // Best-effort only — a failed ping here shouldn't surface anywhere;
        // a real request will show its own error if the backend is
        // genuinely unreachable.
      });
    };

    ping(); // once immediately, then on an interval
    const id = setInterval(ping, PING_INTERVAL_MS);
    return () => clearInterval(id);
  }, []);

  return null;
}
