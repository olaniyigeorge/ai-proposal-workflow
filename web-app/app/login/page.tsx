'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { setClientAuthToken } from '@/lib/auth/session';
import { getSupabaseBrowserClient } from '@/lib/auth/supabaseClient';

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<'signin' | 'signup'>('signin');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  const supabase = getSupabaseBrowserClient();

  const handleSignIn = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!supabase) return;
    setLoading(true);
    setError(null);
    setInfo(null);
    try {
      const { data, error: signInError } = await supabase.auth.signInWithPassword({
        email,
        password,
      });
      if (signInError || !data.session) {
        setError(signInError?.message || 'Sign in failed.');
        return;
      }
      setClientAuthToken(data.session.access_token);
      router.push('/proposals');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sign in failed.');
    } finally {
      setLoading(false);
    }
  };

  // Self-serve account creation — no Supabase dashboard step needed per
  // salesperson. Calls Supabase Auth's own signUp() directly from the
  // browser; every real account still lands on the single `salesperson`
  // role (decisions #21 — there is no other role to assign), so this is
  // safe from a privilege-escalation standpoint. It is NOT gated by
  // company-email-domain or an invite — anyone with this URL can create an
  // account and see client PII once signed in. Acceptable for now given the
  // single-tenant/single-role model, but worth restricting (e.g. an
  // allowed-domain check, or disabling public signup in the Supabase
  // dashboard once the team is fully onboarded) before this is handed to
  // people outside the org.
  const handleSignUp = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!supabase) return;
    setLoading(true);
    setError(null);
    setInfo(null);
    try {
      const { data, error: signUpError } = await supabase.auth.signUp({
        email,
        password,
      });
      if (signUpError) {
        setError(signUpError.message);
        return;
      }
      if (data.session) {
        // Email confirmation is off for this project — signed in immediately.
        setClientAuthToken(data.session.access_token);
        router.push('/proposals');
        return;
      }
      // Email confirmation is on — no session until the link is clicked.
      setInfo('Account created — check your email to confirm it, then sign in.');
      setMode('signin');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sign up failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#f5f6f5] flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-white border border-[#d8dbd9] rounded-2xl p-8 shadow-[0_8px_24px_-8px_rgba(31,36,41,0.12)]">
        <div className="text-center mb-8">
          <div className="w-12 h-12 rounded-xl bg-[#1f2429] flex items-center justify-center font-bold text-white text-xl mx-auto mb-4">
            K
          </div>
          <h1 className="text-xl font-bold text-[#1f2429] tracking-tight">
            Proposal Workflow
          </h1>
          <p className="text-xs text-[#5c646c] mt-1.5">
            Internal Salesperson Review Dashboard
          </p>
        </div>

        <div className="space-y-4">
          {supabase ? (
            <form onSubmit={mode === 'signin' ? handleSignIn : handleSignUp} className="space-y-3">
              <div>
                <label className="text-[11px] text-[#5c646c] font-medium mb-1 block">
                  Email
                </label>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full px-3 py-2.5 rounded-lg bg-white border border-[#d8dbd9] text-sm text-[#1f2429] placeholder:text-[#9aa0a6] focus:outline-none focus:border-[#2563eb]/60"
                  placeholder="you@company.com"
                />
              </div>
              <div>
                <label className="text-[11px] text-[#5c646c] font-medium mb-1 block">
                  Password
                </label>
                <div className="relative">
                  <input
                    type={showPassword ? 'text' : 'password'}
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full px-3 py-2.5 pr-10 rounded-lg bg-white border border-[#d8dbd9] text-sm text-[#1f2429] placeholder:text-[#9aa0a6] focus:outline-none focus:border-[#2563eb]/60"
                    placeholder="••••••••"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    tabIndex={-1}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[#8a8f8c] hover:text-[#1f2429] cursor-pointer"
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                  >
                    {showPassword ? (
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3.98 8.223A10.477 10.477 0 001.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.45 10.45 0 0112 4.5c4.756 0 8.773 3.162 10.065 7.498a10.523 10.523 0 01-4.293 5.774M6.228 6.228L3 3m3.228 3.228l3.65 3.65m7.894 7.894L21 21m-3.228-3.228l-3.65-3.65m0 0a3 3 0 10-4.243-4.243m4.243 4.243L9.88 9.88" />
                      </svg>
                    ) : (
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z" />
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                      </svg>
                    )}
                  </button>
                </div>
              </div>
              {error && <p className="text-xs text-rose-600">{error}</p>}
              {info && <p className="text-xs text-emerald-600">{info}</p>}
              <button
                type="submit"
                disabled={loading}
                className="w-full py-3 px-4 rounded-xl bg-[#1f2429] hover:bg-[#111417] active:bg-black text-white font-medium text-sm transition-all duration-150 flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
              >
                {loading ? (
                  <>
                    <div className="w-4 h-4 rounded-full border-2 border-white border-t-transparent animate-spin" />
                    <span>{mode === 'signin' ? 'Signing in...' : 'Creating account...'}</span>
                  </>
                ) : (
                  <span>{mode === 'signin' ? 'Sign In' : 'Create Account'}</span>
                )}
              </button>
              <button
                type="button"
                onClick={() => {
                  setMode(mode === 'signin' ? 'signup' : 'signin');
                  setError(null);
                  setInfo(null);
                }}
                className="w-full text-center text-[11px] text-[#5c646c] hover:text-[#1f2429] cursor-pointer"
              >
                {mode === 'signin'
                  ? "New salesperson? Create an account"
                  : 'Already have an account? Sign in'}
              </button>
            </form>
          ) : (
            <div className="bg-[#f5f6f5] border border-amber-300/60 rounded-xl p-4 text-xs space-y-1">
              <p className="text-amber-700 font-medium">Supabase Auth not configured</p>
              <p className="text-[#5c646c]">
                Set <code className="text-[#1f2429]">NEXT_PUBLIC_SUPABASE_URL</code> and{' '}
                <code className="text-[#1f2429]">NEXT_PUBLIC_SUPABASE_ANON_KEY</code> to enable
                real per-salesperson sign-in.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
