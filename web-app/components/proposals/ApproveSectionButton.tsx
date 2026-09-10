'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { approveSection } from '@/lib/api/client';
import { ApiError } from '@/lib/api/types';

interface ApproveSectionButtonProps {
  proposalId: string;
  sectionKey: string;
  approvalStatus: string;
  editable: boolean;
}

export function ApproveSectionButton({
  proposalId,
  sectionKey,
  approvalStatus,
  editable,
}: ApproveSectionButtonProps) {
  const router = useRouter();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const alreadyApproved = approvalStatus === 'approved';

  const approve = async () => {
    setIsSubmitting(true);
    setError(null);
    try {
      await approveSection(proposalId, sectionKey);
      router.refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to approve section.');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (alreadyApproved) {
    return null;
  }

  return (
    <div className="flex items-center gap-2">
      <button
        onClick={approve}
        disabled={!editable || isSubmitting}
        title={editable ? undefined : 'Sections can only be approved while In Review'}
        className="px-2.5 py-1 rounded bg-emerald-950/60 border border-emerald-800/50 text-emerald-300 text-[11px] font-medium hover:bg-emerald-900/60 disabled:bg-zinc-800/50 disabled:border-zinc-700/50 disabled:text-zinc-500 disabled:cursor-not-allowed transition-colors"
      >
        {isSubmitting ? 'Approving…' : 'Approve Section'}
      </button>
      {error && <span className="text-[11px] text-rose-400">{error}</span>}
    </div>
  );
}
