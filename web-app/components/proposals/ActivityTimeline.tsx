'use client';

import React, { useState } from 'react';
import { getActivityLog } from '@/lib/api/client';
import { ApiError } from '@/lib/api/types';
import type { ActivityLogEntryResponse } from '@/lib/api/types';

interface ActivityTimelineProps {
  proposalId: string;
}

const FAILURE_EVENT_TYPES = new Set([
  'generation_failed',
  'regeneration_failed',
  'document_generation_failed',
  'delivery_failed',
  'rejected',
]);

function eventLabel(eventType: string): string {
  return eventType.replace(/_/g, ' ');
}

export function ActivityTimeline({ proposalId }: ActivityTimelineProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [entries, setEntries] = useState<ActivityLogEntryResponse[] | null>(null);

  const load = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await getActivityLog(proposalId);
      setEntries(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load activity log.');
    } finally {
      setIsLoading(false);
    }
  };

  const toggle = () => {
    const next = !isOpen;
    setIsOpen(next);
    if (next && entries === null) {
      load();
    }
  };

  return (
    <div className="rounded-xl border border-[#d8dbd9] bg-white shadow-[0_8px_24px_-8px_rgba(31,36,41,0.1)] overflow-hidden">
      <button
        onClick={toggle}
        className="w-full flex items-center justify-between px-5 py-4 text-sm font-semibold text-[#1f2429] hover:bg-[#f5f6f5] transition-colors"
      >
        <span className="flex items-center gap-2">
          <svg className="w-4 h-4 text-[#2563eb]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          Activity Log
          {entries !== null && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#f5f6f5] text-[#5c646c] font-normal">
              {entries.length}
            </span>
          )}
        </span>
        <svg
          className={`w-4 h-4 text-[#8a8f8c] transition-transform ${isOpen ? 'rotate-180' : ''}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isOpen && (
        <div className="px-5 pb-5 space-y-3 border-t border-[#d8dbd9] pt-4">
          {isLoading && <p className="text-xs text-[#8a8f8c]">Loading…</p>}
          {error && <p className="text-xs text-rose-600">{error}</p>}
          {entries !== null && entries.length === 0 && (
            <p className="text-xs text-[#8a8f8c]">No activity recorded for this proposal yet.</p>
          )}
          {entries && entries.length > 0 && (
            <ol className="space-y-3 border-l border-[#d8dbd9] pl-4">
              {entries.map((entry) => {
                const isFailure = FAILURE_EVENT_TYPES.has(entry.event_type);
                return (
                  <li key={entry.id} className="relative text-xs">
                    <span
                      className={`absolute -left-[21px] top-1 w-2.5 h-2.5 rounded-full border-2 border-white ${
                        isFailure ? 'bg-rose-500' : 'bg-[#2563eb]'
                      }`}
                    />
                    <div className="flex items-center justify-between gap-2 flex-wrap">
                      <span
                        className={`px-1.5 py-0.5 rounded text-[10px] uppercase font-medium ${
                          isFailure
                            ? 'bg-rose-50 text-rose-700'
                            : 'bg-[#2563eb]/10 text-[#2563eb]'
                        }`}
                      >
                        {eventLabel(entry.event_type)}
                      </span>
                      <span className="text-[#8a8f8c] font-mono text-[10px]">
                        {new Date(entry.created_at).toLocaleString()}
                      </span>
                    </div>
                    <p className="text-[#374151] mt-1 break-words">{entry.description}</p>
                    <p className="text-[#9aa0a6] mt-0.5">
                      {entry.actor ? `by ${entry.actor}` : 'system'}
                    </p>
                  </li>
                );
              })}
            </ol>
          )}
        </div>
      )}
    </div>
  );
}
