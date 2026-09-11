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
        {error && <p className="text-xs text-rose-600">{error}</p>}
        <button
          onClick={() => run('submit', () => submitForApproval(proposal.id))}
          disabled={pending !== null}
          className="w-full py-2.5 px-4 rounded-lg bg-sky-50 border border-sky-200 hover:bg-sky-100 text-sky-800 font-medium text-xs flex items-center justify-between disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
        >
          <span>{pending === 'submit' ? 'Submitting…' : 'Submit for Approval'}</span>
          <span className="text-[10px] text-sky-700/70">→ Pending Approval</span>
        </button>
        <button
          onClick={() => run('approve', () => approveProposal(proposal.id))}
          disabled={pending !== null}
          className="w-full py-2.5 px-4 rounded-lg bg-emerald-50 border border-emerald-200 hover:bg-emerald-100 text-emerald-800 font-medium text-xs flex items-center justify-between disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
        >
          <span>{pending === 'approve' ? 'Approving…' : 'Approve Proposal'}</span>
          {remainingPending > 0 && (
            <span className="text-[10px] text-emerald-700/70">
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
        {error && <p className="text-xs text-rose-600">{error}</p>}
        <button
          onClick={() => run('approve', () => approveProposal(proposal.id))}
          disabled={pending !== null}
          className="w-full py-2.5 px-4 rounded-lg bg-emerald-50 border border-emerald-200 hover:bg-emerald-100 text-emerald-800 font-medium text-xs flex items-center justify-between disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
        >
          <span>{pending === 'approve' ? 'Approving…' : 'Approve Proposal'}</span>
          {remainingPending > 0 && (
            <span className="text-[10px] text-emerald-700/70">
              will approve {remainingPending} remaining
            </span>
          )}
        </button>

        {reasonPanel === null ? (
          <div className="flex items-center gap-2">
            <button
              onClick={() => setReasonPanel('request-changes')}
              disabled={pending !== null}
              className="flex-1 py-2 px-3 rounded-lg bg-amber-50 border border-amber-200 hover:bg-amber-100 text-amber-800 font-medium text-xs disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
            >
              Request Changes
            </button>
            <button
              onClick={() => setReasonPanel('reject')}
              disabled={pending !== null}
              className="flex-1 py-2 px-3 rounded-lg bg-rose-50 border border-rose-200 hover:bg-rose-100 text-rose-700 font-medium text-xs disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
            >
              Reject
            </button>
          </div>
        ) : (
          <div className="space-y-2 p-3 rounded-lg border border-[#d8dbd9] bg-[#f5f6f5]">
            <label className="block text-[11px] font-medium text-[#5c646c]">
              {reasonPanel === 'reject' ? 'Reason for rejecting (optional)' : 'What needs to change (optional)'}
            </label>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              disabled={pending !== null}
              rows={2}
              className="w-full text-sm text-[#1f2429] bg-white p-2.5 rounded-lg border border-[#d8dbd9] focus:border-[#9aa0a6] focus:outline-none disabled:opacity-60"
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
                className="px-3 py-1.5 rounded bg-[#1f2429] hover:bg-[#111417] text-white text-[11px] font-semibold disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
              >
                {pending !== null ? 'Sending…' : `Confirm ${reasonPanel === 'reject' ? 'Reject' : 'Request Changes'}`}
              </button>
              <button
                onClick={() => {
                  setReasonPanel(null);
                  setReason('');
                }}
                disabled={pending !== null}
                className="px-3 py-1.5 rounded bg-white hover:bg-[#f5f6f5] border border-[#d8dbd9] text-[#1f2429] text-[11px] font-medium disabled:opacity-60 transition-colors"
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
      <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-xs text-emerald-800">
        Approved — all {totalSections} sections signed off. Document generation (Phase 6) is next.
      </div>
    );
  }

  return null;
}
