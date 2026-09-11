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
          className="w-full text-sm text-[#1f2429] leading-relaxed bg-[#f5f6f5] p-4 rounded-lg border border-[#2563eb]/40 focus:border-[#2563eb] focus:outline-none whitespace-pre-wrap disabled:opacity-60"
        />
        {error && <p className="text-xs text-rose-600">{error}</p>}
        <div className="flex items-center gap-2">
          <button
            onClick={save}
            disabled={isSaving}
            className="px-3 py-1.5 rounded bg-[#1f2429] hover:bg-[#111417] text-white text-[11px] font-semibold disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
          >
            {isSaving ? 'Saving…' : 'Save'}
          </button>
          <button
            onClick={cancelEditing}
            disabled={isSaving}
            className="px-3 py-1.5 rounded bg-[#f5f6f5] hover:bg-[#eef0ee] border border-[#d8dbd9] text-[#1f2429] text-[11px] font-medium disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
          >
            Cancel
          </button>
          {invalidatesApproval && (
            <span className="text-[11px] text-amber-700">
              Saving will move this proposal back to In Review.
            </span>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="text-sm text-[#374151] leading-relaxed bg-[#f5f6f5] p-4 rounded-lg border border-[#d8dbd9] font-normal min-h-[5rem] whitespace-pre-wrap">
        {section.content || (
          <span className="text-[#9aa0a6] italic">
            No content generated yet. Will populate after Claude synthesis.
          </span>
        )}
      </div>
      <button
        onClick={startEditing}
        disabled={!editable}
        title={editable ? undefined : 'Not editable in this proposal status'}
        className="px-2.5 py-1 rounded bg-[#2563eb]/10 border border-[#2563eb]/20 text-[#2563eb] text-[11px] font-medium hover:bg-[#2563eb]/15 disabled:bg-[#f5f6f5] disabled:border-[#d8dbd9] disabled:text-[#9aa0a6] disabled:cursor-not-allowed transition-colors"
      >
        Edit Content
      </button>
    </div>
  );
}
