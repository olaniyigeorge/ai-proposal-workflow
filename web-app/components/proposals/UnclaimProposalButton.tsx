'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { unclaimProposal } from '@/lib/api/client';
import { ApiError } from '@/lib/api/types';
import { ConfirmDialog } from '@/components/shared/ConfirmDialog';

interface UnclaimProposalButtonProps {
  proposalId: string;
}

/** Owner-only release of a claimed proposal back to unassigned (ownership
 * enforcement, resolved 2026-09-11 — see
 * docs/design-system-redesign-and-ownership-concerns.md §1). Only ever
 * rendered when the current salesperson is the proposal's owner (see
 * app/proposals/[id]/page.tsx) — the backend enforces this too, so this is
 * a UX affordance, not the actual access control. */
export function UnclaimProposalButton({ proposalId }: UnclaimProposalButtonProps) {
  const router = useRouter();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [isBusy, setIsBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const unclaim = async () => {
    setIsBusy(true);
    setError(null);
    try {
      await unclaimProposal(proposalId);
      setConfirmOpen(false);
      router.refresh();
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : 'Failed to unclaim this proposal.'
      );
    } finally {
      setIsBusy(false);
    }
  };

  return (
    <div className="space-y-1">
      <button
        onClick={() => setConfirmOpen(true)}
        className="px-2.5 py-1 rounded bg-white border border-[#d8dbd9] text-[#5c646c] text-[11px] font-medium hover:bg-[#f5f6f5] cursor-pointer"
      >
        Unclaim
      </button>
      {error && <p className="text-[11px] text-rose-600">{error}</p>}

      <ConfirmDialog
        open={confirmOpen}
        title="Unclaim this proposal?"
        message="This releases the proposal back to unassigned. Any other salesperson will be able to claim and act on it."
        confirmLabel="Unclaim It"
        tone="danger"
        isBusy={isBusy}
        onConfirm={unclaim}
        onCancel={() => setConfirmOpen(false)}
      />
    </div>
  );
}
