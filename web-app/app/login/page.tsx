'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { DEV_TOKEN, setClientAuthToken } from '@/lib/auth/session';

export default function LoginPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  const handleDevLogin = () => {
    setLoading(true);
    setClientAuthToken(DEV_TOKEN);
    setTimeout(() => {
      router.push('/proposals');
    }, 200);
  };

  return (
    <div className="min-h-screen bg-[#090a0f] flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-[#121520] border border-[#1e2436] rounded-2xl p-8 shadow-2xl shadow-black/50">
        <div className="text-center mb-8">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-indigo-500 to-indigo-700 flex items-center justify-center font-bold text-white text-xl shadow-lg shadow-indigo-500/25 mx-auto mb-4">
            P
          </div>
          <h1 className="text-xl font-bold text-white tracking-tight">
            Proposal Workflow
          </h1>
          <p className="text-xs text-zinc-400 mt-1.5">
            Internal Salesperson Review Dashboard
          </p>
        </div>

        <div className="space-y-4">
          <div className="bg-[#0b0d14] border border-[#1e2436] rounded-xl p-4 text-xs space-y-2">
            <div className="flex items-center justify-between text-zinc-300 font-medium">
              <span>Environment:</span>
              <span className="text-emerald-400">Local Development</span>
            </div>
            <div className="flex items-center justify-between text-zinc-400">
              <span>Auth Strategy:</span>
              <span className="font-mono text-[11px] text-zinc-300">Bearer Token Stub</span>
            </div>
            <div className="flex items-center justify-between text-zinc-400">
              <span>Assigned Role:</span>
              <span className="text-indigo-300 font-medium">salesperson</span>
            </div>
          </div>

          <button
            onClick={handleDevLogin}
            disabled={loading}
            className="w-full py-3 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 text-white font-medium text-sm transition-all duration-150 shadow-lg shadow-indigo-600/25 flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
          >
            {loading ? (
              <>
                <div className="w-4 h-4 rounded-full border-2 border-white border-t-transparent animate-spin" />
                <span>Entering Workspace...</span>
              </>
            ) : (
              <>
                <span>Continue as Dev Salesperson</span>
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
                </svg>
              </>
            )}
          </button>

          <p className="text-[11px] text-zinc-500 text-center leading-relaxed pt-2">
            In production, authentication connects to Supabase Auth with standard salesperson credentials.
          </p>
        </div>
      </div>
    </div>
  );
}
