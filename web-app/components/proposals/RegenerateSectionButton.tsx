'use client';

import React, { useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { getProposal, regenerateSection } from '@/lib/api/client';
import { ApiError } from '@/lib/api/types';
import type { ProposalSectionResponse } from '@/lib/api/types';
import { MAX_REGENERATION_ATTEMPTS } from '@/lib/proposal-status';

const POLL_INTERVAL_MS = 2500;
const POLL_TIMEOUT_MS = 45000;
const HUMAN_TOUCHED_ORIGINS = new Set(['human_edited', 'human_edited_after_generation']);

interface RegenerateSectionButtonProps {
  proposalId: string;
  section: ProposalSectionResponse;
  editable: boolean;
}

export function RegenerateSectionButton({
  proposalId,
  section,
  editable,
}: RegenerateSectionButtonProps) {
  const router = useRouter();
  const [isOpen, setIsOpen] = useState(false);
  const [instruction, setInstruction] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isRegenerating, setIsRegenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const attemptsUsed = section.regeneration_count;
  const capReached = attemptsUsed >= MAX_REGENERATION_ATTEMPTS;
  const hasHumanEdits = HUMAN_TOUCHED_ORIGINS.has(section.content_origin);
  const triggerDisabled = !editable || capReached || isSubmitting || isRegenerating;

  const openPanel = () => {
    setInstruction('');
    setError(null);
    setIsOpen(true);
  };

  const closePanel = () => {
    setIsOpen(false);
    setInstruction('');
    setError(null);
  };

  const pollForCompletion = (startingVersion: number, startedAt: number) => {
    pollTimeoutRef.current = setTimeout(async () => {
      try {
        const latest = await getProposal(proposalId);
        const latestSection = latest.sections.find((s) => s.id === section.id);
        if (latestSection && latestSection.version !== startingVersion) {
          setIsRegenerating(false);
          router.refresh();
          return;
        }
      } catch {
        // Transient poll failure — keep trying until the timeout below.
      }
      if (Date.now() - startedAt >= POLL_TIMEOUT_MS) {
        setIsRegenerating(false);
        setError(
          'Regeneration is taking longer than expected. It may still complete — refresh to check.'
        );
        return;
      }
      pollForCompletion(startingVersion, startedAt);
    }, POLL_INTERVAL_MS);
  };

  const submit = async () => {
    if (!instruction.trim()) {
      setError('An instruction is required to regenerate this section.');
      return;
    }
    if (hasHumanEdits) {
      const confirmed = window.confirm(
        'This section has manual edits. Regenerating will replace them with new AI-generated content — this cannot be undone. Continue?'
      );
      if (!confirmed) return;
    }

    setIsSubmitting(true);
    setError(null);
    try {
      await regenerateSection(proposalId, section.section_key, instruction.trim());
      setIsOpen(false);
      setIsRegenerating(true);
      router.refresh();
      pollForCompletion(section.version, Date.now());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to start regeneration.');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isOpen) {
    return (
      <div className="space-y-2 p-3 rounded-lg border border-violet-800/50 bg-violet-950/10">
        <label className="block text-[11px] font-medium text-zinc-400">
          Regeneration instruction (required) — attempt {attemptsUsed + 1} of{' '}
          {MAX_REGENERATION_ATTEMPTS}
        </label>
        <textarea
          value={instruction}
          onChange={(e) => setInstruction(e.target.value)}
          disabled={isSubmitting}
          rows={2}
          autoFocus
          placeholder='e.g. "make this more formal" or "shorten, keep pricing facts"'
          className="w-full text-sm text-zinc-100 bg-[#090a0f] p-2.5 rounded-lg border border-violet-700/60 focus:border-violet-500 focus:outline-none disabled:opacity-60"
        />
        {error && <p className="text-xs text-rose-400">{error}</p>}
        <div className="flex items-center gap-2">
          <button
            onClick={submit}
            disabled={isSubmitting}
            className="px-3 py-1.5 rounded bg-violet-600 hover:bg-violet-500 text-white text-[11px] font-semibold disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
          >
            {isSubmitting ? 'Starting…' : 'Regenerate'}
          </button>
          <button
            onClick={closePanel}
            disabled={isSubmitting}
            className="px-3 py-1.5 rounded bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 text-zinc-300 text-[11px] font-medium disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
          >
            Cancel
          </button>
        </div>
        {section.regeneration_log.length > 0 && (
          <div className="pt-2 border-t border-zinc-800/60 space-y-1">
            <p className="text-[11px] text-zinc-500 font-medium">Previous attempts</p>
            {section.regeneration_log.map((entry, i) => (
              <p key={i} className="text-[11px] text-zinc-500 leading-relaxed">
                <span
                  className={
                    entry.outcome === 'succeeded' ? 'text-emerald-400/80' : 'text-rose-400/80'
                  }
                >
                  {i + 1}. {entry.outcome}
                </span>
                {' — "'}
                {entry.instruction}
                {'"'}
              </p>
            ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <button
      onClick={openPanel}
      disabled={triggerDisabled}
      title={
        capReached
          ? 'Maximum of 3 regeneration attempts reached'
          : !editable
            ? 'Not editable in this proposal status'
            : undefined
      }
      className="px-2.5 py-1 rounded bg-violet-950/60 border border-violet-800/50 text-violet-300 text-[11px] font-medium hover:bg-violet-900/60 disabled:bg-zinc-800/50 disabled:border-zinc-700/50 disabled:text-zinc-500 disabled:cursor-not-allowed transition-colors"
    >
      {isRegenerating ? 'Regenerating…' : 'Regenerate'}
    </button>
  );
}
