'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { transferProposal } from '@/lib/api/client';
import { ApiError, SalespersonAccountResponse } from '@/lib/api/types';
import { ConfirmDialog } from '@/components/shared/ConfirmDialog';

interface TransferProposalButtonProps {
  proposalId: string;
  candidates: SalespersonAccountResponse[];
}

/** Owner-only hand-off of a claimed proposal to a named colleague
 * (ownership enforcement, resolved 2026-09-11 — see
 * docs/design-system-redesign-and-ownership-concerns.md §1). `candidates`
 * is pre-filtered by the caller to approved accounts with a display_name
 * set, excluding the current owner — the same precondition the backend
 * enforces on the transfer target. */
export function TransferProposalButton({ proposalId, candidates }: TransferProposalButtonProps) {
  const router = useRouter();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [targetId, setTargetId] = useState(candidates[0]?.id ?? '');
  const [isBusy, setIsBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (candidates.length === 0) {
    return null;
  }

  const targetName = candidates.find((c) => c.id === targetId)?.display_name ?? 'this colleague';

  const transfer = async () => {
    if (!targetId) return;
    setIsBusy(true);
    setError(null);
    try {
      await transferProposal(proposalId, targetId);
      setConfirmOpen(false);
      router.refresh();
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : 'Failed to transfer this proposal.'
      );
    } finally {
      setIsBusy(false);
    }
  };

  return (
    <div className="flex items-center gap-1.5">
      <select
        value={targetId}
        onChange={(e) => setTargetId(e.target.value)}
        className="px-2 py-1 rounded bg-white border border-[#d8dbd9] text-[#1f2429] text-[11px] cursor-pointer"
      >
        {candidates.map((c) => (
          <option key={c.id} value={c.id}>
            {c.display_name}
          </option>
        ))}
      </select>
      <button
        onClick={() => setConfirmOpen(true)}
        className="px-2.5 py-1 rounded bg-white border border-[#d8dbd9] text-[#5c646c] text-[11px] font-medium hover:bg-[#f5f6f5] cursor-pointer"
      >
        Transfer
      </button>
      {error && <p className="text-[11px] text-rose-600">{error}</p>}

      <ConfirmDialog
        open={confirmOpen}
        title="Transfer this proposal?"
        message={`This hands ownership directly to ${targetName}. You will no longer be able to edit, approve, or deliver it.`}
        confirmLabel="Transfer It"
        tone="danger"
        isBusy={isBusy}
        onConfirm={transfer}
        onCancel={() => setConfirmOpen(false)}
      />
    </div>
  );
}
