'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { generateDocument, getProposal } from '@/lib/api/client';
import { ApiError } from '@/lib/api/types';

const POLL_INTERVAL_MS = 2500;
const POLL_TIMEOUT_MS = 60000;

interface GenerateDocumentButtonProps {
  proposalId: string;
  status: string;
}

export function GenerateDocumentButton({ proposalId, status }: GenerateDocumentButtonProps) {
  const router = useRouter();
  const [isStarting, setIsStarting] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const label =
    status === 'DOCUMENT_GENERATION_FAILED' ? 'Retry PDF Generation' : 'Generate PDF Document';

  const pollUntilDone = (startedAt: number) => {
    setTimeout(async () => {
      try {
        const latest = await getProposal(proposalId);
        if (latest.status !== 'DOCUMENT_GENERATING') {
          setIsGenerating(false);
          router.refresh();
          return;
        }
      } catch {
        // transient poll failure — keep trying until timeout
      }
      if (Date.now() - startedAt >= POLL_TIMEOUT_MS) {
        setIsGenerating(false);
        setError('Document generation is taking longer than expected. It may still complete — refresh to check.');
        return;
      }
      pollUntilDone(startedAt);
    }, POLL_INTERVAL_MS);
  };

  const start = async () => {
    setIsStarting(true);
    setError(null);
    try {
      await generateDocument(proposalId);
      setIsGenerating(true);
      router.refresh();
      pollUntilDone(Date.now());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to start document generation.');
    } finally {
      setIsStarting(false);
    }
  };

  return (
    <div className="space-y-2">
      <button
        onClick={start}
        disabled={isStarting || isGenerating}
        className="w-full py-2.5 px-4 rounded-lg bg-teal-950/40 border border-teal-800/40 hover:bg-teal-900/40 text-teal-300 font-medium text-xs flex items-center justify-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
      >
        {isGenerating || isStarting ? (
          <>
            <span className="w-3 h-3 rounded-full border-2 border-teal-300/40 border-t-teal-300 animate-spin" />
            Rendering PDF…
          </>
        ) : (
          label
        )}
      </button>
      {error && <p className="text-xs text-rose-400">{error}</p>}
    </div>
  );
}
