'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  approveProposal,
  rejectProposal,
  requestChanges,
  submitForApproval,
} from '@/lib/api/client';
import { ApiError } from '@/lib/api/types';
import type { ProposalDetailResponse } from '@/lib/api/types';
import { pendingSectionCount } from '@/lib/proposal-status';

interface ApprovalPanelProps {
  proposal: ProposalDetailResponse;
}

type Action = 'submit' | 'approve' | 'request-changes' | 'reject';

export function ApprovalPanel({ proposal }: ApprovalPanelProps) {
  const router = useRouter();
  const [pending, setPending] = useState<Action | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reasonPanel, setReasonPanel] = useState<'request-changes' | 'reject' | null>(null);
  const [reason, setReason] = useState('');

  const status = proposal.status;
  const remainingPending = pendingSectionCount(proposal);
  const totalSections = proposal.sections?.length || 0;

  const run = async (action: Action, fn: () => Promise<unknown>) => {
    setPending(action);
    setError(null);
    try {
      await fn();
      setReasonPanel(null);
      setReason('');
      router.refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : `Failed to ${action.replace('-', ' ')}.`);
    } finally {
      setPending(null);
    }
  };

  if (status === 'IN_REVIEW') {
    return (
      <div className="space-y-2">
        {error && <p className="text-xs text-rose-400">{error}</p>}
        <button
          onClick={() => run('submit', () => submitForApproval(proposal.id))}
          disabled={pending !== null}
          className="w-full py-2.5 px-4 rounded-lg bg-sky-950/40 border border-sky-800/40 hover:bg-sky-900/40 text-sky-300 font-medium text-xs flex items-center justify-between disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
        >
          <span>{pending === 'submit' ? 'Submitting…' : 'Submit for Approval'}</span>
          <span className="text-[10px] text-sky-400/70">→ Pending Approval</span>
        </button>
        <button
          onClick={() => run('approve', () => approveProposal(proposal.id))}
          disabled={pending !== null}
          className="w-full py-2.5 px-4 rounded-lg bg-emerald-950/40 border border-emerald-800/40 hover:bg-emerald-900/40 text-emerald-300 font-medium text-xs flex items-center justify-between disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
        >
          <span>{pending === 'approve' ? 'Approving…' : 'Approve Proposal'}</span>
          {remainingPending > 0 && (
            <span className="text-[10px] text-emerald-400/70">
              will approve {remainingPending} remaining
            </span>
          )}
        </button>
      </div>
    );
  }

  if (status === 'PENDING_APPROVAL') {
    return (
      <div className="space-y-2">
        {error && <p className="text-xs text-rose-400">{error}</p>}
        <button
          onClick={() => run('approve', () => approveProposal(proposal.id))}
          disabled={pending !== null}
          className="w-full py-2.5 px-4 rounded-lg bg-emerald-950/40 border border-emerald-800/40 hover:bg-emerald-900/40 text-emerald-300 font-medium text-xs flex items-center justify-between disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
        >
          <span>{pending === 'approve' ? 'Approving…' : 'Approve Proposal'}</span>
          {remainingPending > 0 && (
            <span className="text-[10px] text-emerald-400/70">
              will approve {remainingPending} remaining
            </span>
          )}
        </button>

        {reasonPanel === null ? (
          <div className="flex items-center gap-2">
            <button
              onClick={() => setReasonPanel('request-changes')}
              disabled={pending !== null}
              className="flex-1 py-2 px-3 rounded-lg bg-amber-950/30 border border-amber-800/40 hover:bg-amber-900/30 text-amber-300 font-medium text-xs disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
            >
              Request Changes
            </button>
            <button
              onClick={() => setReasonPanel('reject')}
              disabled={pending !== null}
              className="flex-1 py-2 px-3 rounded-lg bg-rose-950/30 border border-rose-800/40 hover:bg-rose-900/30 text-rose-300 font-medium text-xs disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
            >
              Reject
            </button>
          </div>
        ) : (
          <div className="space-y-2 p-3 rounded-lg border border-zinc-700/60 bg-zinc-900/40">
            <label className="block text-[11px] font-medium text-zinc-400">
              {reasonPanel === 'reject' ? 'Reason for rejecting (optional)' : 'What needs to change (optional)'}
            </label>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              disabled={pending !== null}
              rows={2}
              className="w-full text-sm text-zinc-100 bg-[#090a0f] p-2.5 rounded-lg border border-zinc-700 focus:border-zinc-500 focus:outline-none disabled:opacity-60"
            />
            <div className="flex items-center gap-2">
              <button
                onClick={() =>
                  run(reasonPanel, () =>
                    reasonPanel === 'reject'
                      ? rejectProposal(proposal.id, reason.trim() || undefined)
                      : requestChanges(proposal.id, reason.trim() || undefined)
                  )
                }
                disabled={pending !== null}
                className="px-3 py-1.5 rounded bg-zinc-700 hover:bg-zinc-600 text-white text-[11px] font-semibold disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
              >
                {pending !== null ? 'Sending…' : `Confirm ${reasonPanel === 'reject' ? 'Reject' : 'Request Changes'}`}
              </button>
              <button
                onClick={() => {
                  setReasonPanel(null);
                  setReason('');
                }}
                disabled={pending !== null}
                className="px-3 py-1.5 rounded bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 text-zinc-300 text-[11px] font-medium disabled:opacity-60 transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>
    );
  }

  if (status === 'APPROVED') {
    return (
      <div className="p-3 rounded-lg bg-emerald-950/30 border border-emerald-800/40 text-xs text-emerald-300">
        Approved — all {totalSections} sections signed off. Document generation (Phase 6) is next.
      </div>
    );
  }

  return null;
}
