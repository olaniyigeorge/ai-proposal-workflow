export const DEV_TOKEN = 'dev-salesperson-token';

// Single source of truth for the cookie name — get/set/clear all used to
// disagree on this (AUTH_COOKIE_NAME vs. a separate local COOKIE_NAME
// constant), which meant a real login could never actually take effect:
// setClientAuthToken() wrote to 'auth_token' while getClientAuthToken() only
// ever looked for 'proposal_auth_token', so it silently fell through to
// DEV_TOKEN every time regardless of what was set. One constant, used by all
// three functions (and exported so lib/auth/serverSession.ts — which reads
// the same cookie via next/headers for Server Components — can never drift
// from this either).
export const AUTH_COOKIE_NAME = 'proposal_auth_token';

/**
 * Get the current auth token, browser-side only (uses document.cookie,
 * which doesn't exist on the server). Never call this from a Server
 * Component — see lib/auth/serverSession.ts::getServerAuthToken() for that
 * case; the two used to be conflated (this function returning DEV_TOKEN
 * whenever `window` was undefined), which is exactly what caused real
 * logins to send a fake token on every server-rendered page and get
 * rejected in production with "Invalid or expired token: Not enough
 * segments" (docs/edge-cases.md, 2026-09-11).
 */
export function getClientAuthToken(): string | null {
  if (typeof window === 'undefined') {
    return null;
  }
  const cookies = document.cookie.split(';');
  for (const cookie of cookies) {
    const [name, value] = cookie.trim().split('=');
    if (name === AUTH_COOKIE_NAME && value) {
      return decodeURIComponent(value);
    }
  }
  return null;
}

export function setClientAuthToken(token: string): void {
  if (typeof window !== 'undefined') {
    // Set 7-day expiration
    const expires = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toUTCString();
    const secureFlag = window.location.protocol === 'https:' ? '; Secure' : '';

    document.cookie = `${AUTH_COOKIE_NAME}=${encodeURIComponent(token)}; path=/; expires=${expires}; SameSite=Lax${secureFlag}`;
  }
}

export function clearClientAuthToken(): void {
  if (typeof window !== 'undefined') {
    const secureFlag = window.location.protocol === 'https:' ? '; Secure' : '';

    // Set expiration in the past and Max-Age=0 to immediately invalidate
    document.cookie = `${AUTH_COOKIE_NAME}=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT; Max-Age=0; SameSite=Lax${secureFlag}`;
  }
}

/**
 * Best-effort read of the current session's identity for display only (e.g.
 * the sidebar footer) — decodes the JWT payload client-side without
 * verifying the signature. Never use this for anything security-relevant;
 * the backend is the authority and verifies the token itself on every
 * request (app/core/security.py).
 */
export function getClientSessionInfo(): { email: string | null; isDevToken: boolean } {
  const token = getClientAuthToken();
  if (!token) return { email: null, isDevToken: false };
  if (token === DEV_TOKEN) return { email: 'salesperson@example.com', isDevToken: true };

  try {
    const payloadSegment = token.split('.')[1];
    if (!payloadSegment) return { email: null, isDevToken: false };
    const json = atob(payloadSegment.replace(/-/g, '+').replace(/_/g, '/'));
    const payload = JSON.parse(json);
    return { email: payload.email ?? null, isDevToken: false };
  } catch {
    return { email: null, isDevToken: false };
  }
}
