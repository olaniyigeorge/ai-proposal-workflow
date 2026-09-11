'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { claimProposal } from '@/lib/api/client';
import { ApiError } from '@/lib/api/types';
import { ConfirmDialog } from '@/components/shared/ConfirmDialog';

interface ClaimProposalButtonProps {
  proposalId: string;
}

/** Manual self-claim only (decisions #20) — never an automatic string
 * match. Only ever rendered when salesperson_name is genuinely null (see
 * app/proposals/[id]/page.tsx), so there's nothing to reassign here. */
export function ClaimProposalButton({ proposalId }: ClaimProposalButtonProps) {
  const router = useRouter();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [isClaiming, setIsClaiming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const claim = async () => {
    setIsClaiming(true);
    setError(null);
    try {
      await claimProposal(proposalId);
      setConfirmOpen(false);
      router.refresh();
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : 'Failed to claim this proposal.'
      );
    } finally {
      setIsClaiming(false);
    }
  };

  return (
    <div className="space-y-1">
      <button
        onClick={() => setConfirmOpen(true)}
        className="px-2.5 py-1 rounded bg-[#2563eb]/10 border border-[#2563eb]/20 text-[#2563eb] text-[11px] font-medium hover:bg-[#2563eb]/15 cursor-pointer"
      >
        Claim for yourself
      </button>
      {error && <p className="text-[11px] text-rose-600">{error}</p>}

      <ConfirmDialog
        open={confirmOpen}
        title="Claim this proposal?"
        message="This proposal has no salesperson assigned yet. Claiming it will set you as the owner using your display name (set in Team) — this can't be undone from here."
        confirmLabel="Claim It"
        isBusy={isClaiming}
        onConfirm={claim}
        onCancel={() => setConfirmOpen(false)}
      />
    </div>
  );
}
