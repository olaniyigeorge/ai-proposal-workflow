'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { generateProposal, getProposal } from '@/lib/api/client';
import { ApiError } from '@/lib/api/types';

const POLL_INTERVAL_MS = 2500;
const POLL_TIMEOUT_MS = 60000;

interface GenerateProposalButtonProps {
  proposalId: string;
  status: string;
}

export function GenerateProposalButton({ proposalId, status }: GenerateProposalButtonProps) {
  const router = useRouter();
  const [isStarting, setIsStarting] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const label = status === 'GENERATION_FAILED' ? 'Retry Generation' : 'Generate Proposal';

  const pollUntilDone = (startedAt: number) => {
    setTimeout(async () => {
      try {
        const latest = await getProposal(proposalId);
        if (latest.status !== 'GENERATING') {
          setIsGenerating(false);
          router.refresh();
          return;
        }
      } catch {
        // transient poll failure — keep trying until timeout
      }
      if (Date.now() - startedAt >= POLL_TIMEOUT_MS) {
        setIsGenerating(false);
        setError('Generation is taking longer than expected. It may still complete — refresh to check.');
        return;
      }
      pollUntilDone(startedAt);
    }, POLL_INTERVAL_MS);
  };

  const start = async () => {
    setIsStarting(true);
    setError(null);
    try {
      await generateProposal(proposalId);
      setIsGenerating(true);
      router.refresh();
      pollUntilDone(Date.now());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to start generation.');
    } finally {
      setIsStarting(false);
    }
  };

  return (
    <div className="space-y-2">
      <button
        onClick={start}
        disabled={isStarting || isGenerating}
        className="w-full py-2.5 px-4 rounded-lg bg-[#1f2429] hover:bg-[#111417] border border-[#1f2429] text-white font-medium text-xs flex items-center justify-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
      >
        {isGenerating || isStarting ? (
          <>
            <span className="w-3 h-3 rounded-full border-2 border-white/40 border-t-white animate-spin" />
            Generating with Claude…
          </>
        ) : (
          label
        )}
      </button>
      {error && <p className="text-xs text-rose-600">{error}</p>}
    </div>
  );
}
