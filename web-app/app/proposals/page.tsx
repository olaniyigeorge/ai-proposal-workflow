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
    <div className="space-y-6 animate-fade-in-up">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-[#d8dbd9]">
        <div>
          <h1 className="text-2xl font-bold text-[#1f2429] tracking-tight">
            Proposals
          </h1>
          <p className="text-xs text-[#5c646c] mt-1">
            Review and track proposals generated from client intake submissions.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-white border border-[#d8dbd9] text-[#5c646c]">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            Backend Sync Active
          </span>
        </div>
      </div>

      {/* Backend connection warning if offline */}
      {errorNotice && (
        <div className="p-4 rounded-xl bg-amber-50 border border-amber-200 text-amber-800 text-xs flex items-start gap-3">
          <svg className="w-5 h-5 text-amber-500 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <div className="space-y-1">
            <div className="font-semibold text-amber-900">Backend Connection Notice</div>
            <div>{errorNotice}</div>
            <div className="text-[11px] text-amber-700">
              Ensure the FastAPI backend is running: <code className="px-1.5 py-0.5 rounded bg-amber-100 font-mono">cd backend && uvicorn main:app --reload</code>
            </div>
          </div>
        </div>
      )}

      {/* Proposal Table / Cards */}
      <ProposalList initialProposals={proposals} />
    </div>
  );
}
