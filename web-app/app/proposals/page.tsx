import React from 'react';
import { listProposals } from '@/lib/api/client';
import { ProposalSummaryResponse } from '@/lib/api/types';
import { ProposalList } from '@/components/proposals/ProposalList';

export const dynamic = 'force-dynamic';

export default async function ProposalsPage() {
  let proposals: ProposalSummaryResponse[] = [];
  let errorNotice: string | null = null;

  try {
    proposals = await listProposals(0, 50);
  } catch (err: any) {
    errorNotice = err?.message || 'Failed to load proposals from backend';
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-[#1e2436]">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">
            Proposals
          </h1>
          <p className="text-xs text-zinc-400 mt-1">
            Review and track proposals generated from client intake submissions.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-[#121520] border border-[#1e2436] text-zinc-300">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            Backend Sync Active
          </span>
        </div>
      </div>

      {/* Backend connection warning if offline */}
      {errorNotice && (
        <div className="p-4 rounded-xl bg-amber-950/40 border border-amber-800/50 text-amber-200 text-xs flex items-start gap-3">
          <svg className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <div className="space-y-1">
            <div className="font-semibold text-amber-300">Backend Connection Notice</div>
            <div>{errorNotice}</div>
            <div className="text-[11px] text-amber-400/80">
              Ensure the FastAPI backend is running: <code className="px-1.5 py-0.5 rounded bg-black/40 font-mono">cd backend && uvicorn main:app --reload</code>
            </div>
          </div>
        </div>
      )}

      {/* Proposal Table / Cards */}
      <ProposalList initialProposals={proposals} />
    </div>
  );
}
