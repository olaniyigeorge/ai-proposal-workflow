'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { updateSectionContent } from '@/lib/api/client';
import { ApiError } from '@/lib/api/types';
import type { ProposalSectionResponse } from '@/lib/api/types';

interface SectionEditorProps {
  proposalId: string;
  section: ProposalSectionResponse;
  editable: boolean;
  invalidatesApproval: boolean;
}

export function SectionEditor({
  proposalId,
  section,
  editable,
  invalidatesApproval,
}: SectionEditorProps) {
  const router = useRouter();
  const [isEditing, setIsEditing] = useState(false);
  const [draft, setDraft] = useState(section.content);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const startEditing = () => {
    setDraft(section.content);
    setError(null);
    setIsEditing(true);
  };

  const cancelEditing = () => {
    setDraft(section.content);
    setError(null);
    setIsEditing(false);
  };

  const save = async () => {
    if (!draft.trim()) {
      setError('Content cannot be empty.');
      return;
    }
    setIsSaving(true);
    setError(null);
    try {
      await updateSectionContent(proposalId, section.section_key, draft);
      setIsEditing(false);
      router.refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to save section.');
    } finally {
      setIsSaving(false);
    }
  };

  if (isEditing) {
    return (
      <div className="space-y-3">
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          disabled={isSaving}
          rows={6}
          autoFocus
          className="w-full text-sm text-zinc-100 leading-relaxed bg-[#090a0f] p-4 rounded-lg border border-indigo-700/60 focus:border-indigo-500 focus:outline-none whitespace-pre-wrap disabled:opacity-60"
        />
        {error && <p className="text-xs text-rose-400">{error}</p>}
        <div className="flex items-center gap-2">
          <button
            onClick={save}
            disabled={isSaving}
            className="px-3 py-1.5 rounded bg-indigo-600 hover:bg-indigo-500 text-white text-[11px] font-semibold disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
          >
            {isSaving ? 'Saving…' : 'Save'}
          </button>
          <button
            onClick={cancelEditing}
            disabled={isSaving}
            className="px-3 py-1.5 rounded bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 text-zinc-300 text-[11px] font-medium disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
          >
            Cancel
          </button>
          {invalidatesApproval && (
            <span className="text-[11px] text-amber-400/90">
              Saving will move this proposal back to In Review.
            </span>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="text-sm text-zinc-300 leading-relaxed bg-[#090a0f] p-4 rounded-lg border border-[#1e2436] font-normal min-h-[5rem] whitespace-pre-wrap">
        {section.content || (
          <span className="text-zinc-600 italic">
            No content generated yet. Will populate after Claude synthesis.
          </span>
        )}
      </div>
      <button
        onClick={startEditing}
        disabled={!editable}
        title={editable ? undefined : 'Not editable in this proposal status'}
        className="px-2.5 py-1 rounded bg-indigo-950/60 border border-indigo-800/50 text-indigo-300 text-[11px] font-medium hover:bg-indigo-900/60 disabled:bg-zinc-800/50 disabled:border-zinc-700/50 disabled:text-zinc-500 disabled:cursor-not-allowed transition-colors"
      >
        Edit Content
      </button>
    </div>
  );
}
