export const DEV_TOKEN = 'dev-salesperson-token';

// Single source of truth for the cookie name — get/set/clear all used to
// disagree on this (AUTH_COOKIE_NAME vs. a separate local COOKIE_NAME
// constant), which meant a real login could never actually take effect:
// setClientAuthToken() wrote to 'auth_token' while getClientAuthToken() only
// ever looked for 'proposal_auth_token', so it silently fell through to
// DEV_TOKEN every time regardless of what was set. One constant, used by all
// three functions, fixes that.
const COOKIE_NAME = 'proposal_auth_token';

/**
 * Get the current auth token.
 * In development (or if nothing is set yet), defaults to DEV_TOKEN.
 */
export function getClientAuthToken(): string | null {
  if (typeof window === 'undefined') {
    return DEV_TOKEN;
  }
  const cookies = document.cookie.split(';');
  for (const cookie of cookies) {
    const [name, value] = cookie.trim().split('=');
    if (name === COOKIE_NAME && value) {
      return decodeURIComponent(value);
    }
  }
  // Default to dev token in dev environment
  return DEV_TOKEN;
}

export function setClientAuthToken(token: string): void {
  if (typeof window !== 'undefined') {
    // Set 7-day expiration
    const expires = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toUTCString();
    const secureFlag = window.location.protocol === 'https:' ? '; Secure' : '';

    document.cookie = `${COOKIE_NAME}=${encodeURIComponent(token)}; path=/; expires=${expires}; SameSite=Lax${secureFlag}`;
  }
}

export function clearClientAuthToken(): void {
  if (typeof window !== 'undefined') {
    const secureFlag = window.location.protocol === 'https:' ? '; Secure' : '';

    // Set expiration in the past and Max-Age=0 to immediately invalidate
    document.cookie = `${COOKIE_NAME}=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT; Max-Age=0; SameSite=Lax${secureFlag}`;
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
