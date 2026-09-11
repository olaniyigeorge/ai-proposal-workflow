import { cookies } from 'next/headers';
import { AUTH_COOKIE_NAME, DEV_TOKEN } from './session';

/**
 * Server Component / Route Handler only — reads the auth cookie via
 * next/headers (document.cookie doesn't exist on the server, which is
 * exactly why the old code silently sent DEV_TOKEN instead: client.ts's
 * request() guarded on `typeof window === 'undefined'` and fell back to a
 * hardcoded dev token whenever it couldn't read a real cookie, which is
 * every server-rendered page load, in every environment including
 * production — see docs/edge-cases.md, 2026-09-11, "Not enough segments").
 *
 * Every Server Component that fetches from the backend (app/proposals/page.tsx,
 * app/proposals/[id]/page.tsx) must call this and pass the result explicitly
 * as the `token` argument — never rely on the API client's own fallback for
 * a server-rendered request.
 */
export async function getServerAuthToken(): Promise<string | undefined> {
  const cookieStore = await cookies();
  const token = cookieStore.get(AUTH_COOKIE_NAME)?.value;
  if (token) return token;
  // Only in local dev, matching the backend's own dev-token gate
  // (app/core/security.py checks settings.ENVIRONMENT) — never in a
  // production build, where sending a fake token gets a confusing
  // "invalid token" 401 instead of the clear "authentication required" one.
  return process.env.NODE_ENV !== 'production' ? DEV_TOKEN : undefined;
}
