import React from 'react';
import { getMe, listAccounts } from '@/lib/api/client';
import { ApiError } from '@/lib/api/types';
import { SalespersonAccountResponse, SalespersonProfileResponse } from '@/lib/api/types';
import { TeamList } from '@/components/team/TeamList';
import { getServerAuthToken } from '@/lib/auth/serverSession';

export const dynamic = 'force-dynamic';

export default async function TeamPage() {
  let accounts: SalespersonAccountResponse[] = [];
  let me: SalespersonProfileResponse | null = null;
  let errorNotice: string | null = null;
  let isConnectionFailure = false;

  try {
    const token = await getServerAuthToken();
    [me, accounts] = await Promise.all([getMe(token), listAccounts(token)]);
  } catch (err: any) {
    errorNotice = err?.message || 'Failed to load team data';
    isConnectionFailure = err instanceof ApiError && err.status === 0;
  }

  return (
    <div className="space-y-6 animate-fade-in-up">
      <div className="pb-6 border-b border-[#d8dbd9]">
        <h1 className="text-2xl font-bold text-[#1f2429] tracking-tight">Team</h1>
        <p className="text-xs text-[#5c646c] mt-1">
          Set your display name and approve new salespeople — any approved salesperson can approve the next one, no separate approver role.
        </p>
      </div>

      {errorNotice && (
        <div className="p-4 rounded-xl bg-amber-50 border border-amber-200 text-amber-800 text-xs flex items-start gap-3">
          <svg className="w-5 h-5 text-amber-500 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <div className="space-y-1">
            <div className="font-semibold text-amber-900">
              {isConnectionFailure ? 'Backend Connection Notice' : 'Couldn’t Load Team'}
            </div>
            <div>{errorNotice}</div>
            {isConnectionFailure && (
              <div className="text-[11px] text-amber-700">
                Ensure the FastAPI backend is running: <code className="px-1.5 py-0.5 rounded bg-amber-100 font-mono">cd backend && uvicorn main:app --reload</code>
              </div>
            )}
          </div>
        </div>
      )}

      {me && <TeamList me={me} initialAccounts={accounts} />}
    </div>
  );
}
