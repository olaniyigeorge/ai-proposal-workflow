'use client';

import React, { useState } from 'react';
import { getClaudeCalls } from '@/lib/api/client';
import { ApiError } from '@/lib/api/types';
import type { ClaudeCallLogResponse } from '@/lib/api/types';

interface ClaudeCallLogPanelProps {
  proposalId: string;
}

function formatTokens(log: ClaudeCallLogResponse): string {
  if (log.input_tokens == null || log.output_tokens == null) return '—';
  return `${log.input_tokens} in / ${log.output_tokens} out`;
}

export function ClaudeCallLogPanel({ proposalId }: ClaudeCallLogPanelProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [calls, setCalls] = useState<ClaudeCallLogResponse[] | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const load = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await getClaudeCalls(proposalId);
      setCalls(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load Claude call log.');
    } finally {
      setIsLoading(false);
    }
  };

  const toggle = () => {
    const next = !isOpen;
    setIsOpen(next);
    if (next && calls === null) {
      load();
    }
  };

  return (
    <div className="rounded-xl border border-[#1e2436] bg-[#121520] shadow-lg shadow-black/20 overflow-hidden">
      <button
        onClick={toggle}
        className="w-full flex items-center justify-between px-5 py-4 text-sm font-semibold text-white hover:bg-[#161a26] transition-colors"
      >
        <span className="flex items-center gap-2">
          <svg className="w-4 h-4 text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 17v-2a4 4 0 014-4h4m0 0l-3-3m3 3l-3 3M4 7h16M4 12h4m-4 5h10" />
          </svg>
          Claude Call Log
          {calls !== null && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400 font-normal">
              {calls.length}
            </span>
          )}
        </span>
        <svg
          className={`w-4 h-4 text-zinc-500 transition-transform ${isOpen ? 'rotate-180' : ''}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isOpen && (
        <div className="px-5 pb-5 space-y-3 border-t border-[#1e2436] pt-4">
          {isLoading && <p className="text-xs text-zinc-500">Loading…</p>}
          {error && <p className="text-xs text-rose-400">{error}</p>}
          {calls !== null && calls.length === 0 && (
            <p className="text-xs text-zinc-500">No Claude calls made for this proposal yet.</p>
          )}
          {calls?.map((log) => {
            const expanded = expandedId === log.id;
            return (
              <div
                key={log.id}
                className="rounded-lg border border-[#1e2436] bg-[#090a0f] p-3 text-xs space-y-2"
              >
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-mono text-zinc-300">{log.section_key}</span>
                    <span
                      className={`px-1.5 py-0.5 rounded text-[10px] uppercase font-medium ${
                        log.call_type === 'regeneration'
                          ? 'bg-violet-950/60 text-violet-300'
                          : 'bg-indigo-950/60 text-indigo-300'
                      }`}
                    >
                      {log.call_type.replace('_', ' ')}
                    </span>
                    <span
                      className={`px-1.5 py-0.5 rounded text-[10px] uppercase font-medium ${
                        log.status === 'succeeded'
                          ? 'bg-emerald-950/60 text-emerald-300'
                          : 'bg-rose-950/60 text-rose-300'
                      }`}
                    >
                      {log.status}
                    </span>
                  </div>
                  <span className="text-zinc-500 font-mono text-[10px]">
                    {new Date(log.created_at).toLocaleString()}
                  </span>
                </div>

                <div className="flex items-center gap-4 text-zinc-500 flex-wrap">
                  <span>Model: {log.model || '—'}</span>
                  <span>Tokens: {formatTokens(log)}</span>
                  <span>Latency: {log.duration_ms != null ? `${log.duration_ms}ms` : '—'}</span>
                </div>

                {log.instruction && (
                  <div className="text-zinc-400">
                    Instruction: <span className="text-zinc-300">&quot;{log.instruction}&quot;</span>
                  </div>
                )}

                {log.error_message && (
                  <div className="text-rose-400">Error: {log.error_message}</div>
                )}

                <button
                  onClick={() => setExpandedId(expanded ? null : log.id)}
                  className="text-indigo-400 hover:text-indigo-300 text-[11px] font-medium"
                >
                  {expanded ? 'Hide prompt/response' : 'Show prompt/response'}
                </button>

                {expanded && (
                  <div className="space-y-2 pt-2 border-t border-[#1e2436]">
                    <div>
                      <p className="text-zinc-500 mb-1">System prompt</p>
                      <pre className="whitespace-pre-wrap text-zinc-400 bg-[#050609] p-2 rounded border border-[#1e2436] max-h-40 overflow-y-auto">
                        {log.system_prompt}
                      </pre>
                    </div>
                    <div>
                      <p className="text-zinc-500 mb-1">User prompt</p>
                      <pre className="whitespace-pre-wrap text-zinc-400 bg-[#050609] p-2 rounded border border-[#1e2436] max-h-40 overflow-y-auto">
                        {log.user_prompt}
                      </pre>
                    </div>
                    {log.response_text && (
                      <div>
                        <p className="text-zinc-500 mb-1">Response</p>
                        <pre className="whitespace-pre-wrap text-zinc-300 bg-[#050609] p-2 rounded border border-[#1e2436] max-h-40 overflow-y-auto">
                          {log.response_text}
                        </pre>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
