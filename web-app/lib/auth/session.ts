export const DEV_TOKEN = 'dev-salesperson-token';
export const AUTH_COOKIE_NAME = 'proposal_auth_token';

/**
 * Get the current auth token.
 * In development, defaults to DEV_TOKEN if not explicitly set or overridden.
 */
export function getClientAuthToken(): string | null {
  if (typeof window === 'undefined') {
    return DEV_TOKEN;
  }
  const cookies = document.cookie.split(';');
  for (const cookie of cookies) {
    const [name, value] = cookie.trim().split('=');
    if (name === AUTH_COOKIE_NAME && value) {
      return decodeURIComponent(value);
    }
  }
  // Default to dev token in dev environment
  return DEV_TOKEN;
}

const COOKIE_NAME = 'auth_token'; // Or your preferred cookie key name

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