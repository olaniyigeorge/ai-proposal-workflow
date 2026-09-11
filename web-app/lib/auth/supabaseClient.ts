import { createClient, SupabaseClient } from '@supabase/supabase-js';

// Real per-salesperson login (docs/decisions.md #21's follow-up — every
// account today used the same dev token). This client only ever calls
// Supabase Auth's own sign-in endpoints — it never touches the database
// directly, so no service-role/anon key exposure risk beyond what Supabase
// Auth itself is designed for client-side use with.
//
// Returns null (rather than throwing) when the env vars aren't configured,
// so the login page can fall back to dev-login-only in an environment that
// hasn't set these up yet, instead of crashing the whole page.
let client: SupabaseClient | null | undefined;

export function getSupabaseBrowserClient(): SupabaseClient | null {
  if (client !== undefined) return client;

  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

  if (!url || !anonKey) {
    client = null;
    return client;
  }

  client = createClient(url, anonKey);
  return client;
}
