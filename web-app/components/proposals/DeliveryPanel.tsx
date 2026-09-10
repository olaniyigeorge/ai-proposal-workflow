'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { deliverProposal, getDeliveryDraft, getDeliveryRecords, getProposal } from '@/lib/api/client';
import { ApiError } from '@/lib/api/types';
import type { DeliveryDraftResponse, DeliveryRecordResponse } from '@/lib/api/types';

const POLL_INTERVAL_MS = 2500;
const POLL_TIMEOUT_MS = 30000;

interface DeliveryPanelProps {
  proposalId: string;
  status: string;
  canDeliver: boolean;
  inProgress: boolean;
  isDelivered: boolean;
}

export function DeliveryPanel({
  proposalId,
  status,
  canDeliver,
  inProgress,
  isDelivered,
}: DeliveryPanelProps) {
  const router = useRouter();
  const [draft, setDraft] = useState<DeliveryDraftResponse | null>(null);
  const [records, setRecords] = useState<DeliveryRecordResponse[]>([]);
  const [draftError, setDraftError] = useState<string | null>(null);
  const [isSending, setIsSending] = useState(false);
  const [isPolling, setIsPolling] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);
  const [showFullBody, setShowFullBody] = useState(false);

  useEffect(() => {
    let cancelled = false;
    if (canDeliver) {
      getDeliveryDraft(proposalId)
        .then((data) => {
          if (!cancelled) setDraft(data);
        })
        .catch((err) => {
          if (!cancelled) {
            setDraftError(err instanceof ApiError ? err.message : 'Failed to load draft.');
          }
        });
    }
    getDeliveryRecords(proposalId)
      .then((data) => {
        if (!cancelled) setRecords(data);
      })
      .catch(() => {
        // history is a nice-to-have — a failed fetch here shouldn't block sending
      });
    return () => {
      cancelled = true;
    };
  }, [proposalId, canDeliver]);

  const pollUntilDone = (startedAt: number) => {
    setTimeout(async () => {
      try {
        const latest = await getProposal(proposalId);
        if (latest.status !== 'DELIVERING') {
          setIsPolling(false);
          router.refresh();
          return;
        }
      } catch {
        // transient poll failure — keep trying until timeout
      }
      if (Date.now() - startedAt >= POLL_TIMEOUT_MS) {
        setIsPolling(false);
        setSendError('Sending is taking longer than expected. It may still complete — refresh to check.');
        return;
      }
      pollUntilDone(startedAt);
    }, POLL_INTERVAL_MS);
  };

  const send = async () => {
    setIsSending(true);
    setSendError(null);
    try {
      await deliverProposal(proposalId);
      setIsPolling(true);
      router.refresh();
      pollUntilDone(Date.now());
    } catch (err) {
      setSendError(err instanceof ApiError ? err.message : 'Failed to send.');
    } finally {
      setIsSending(false);
    }
  };

  const renderHistory = () => {
    if (records.length === 0) return null;
    return (
      <div className="space-y-2 pt-2 border-t border-teal-900/40 min-w-0">
        <p className="text-[11px] text-zinc-500 font-medium">Delivery attempts</p>
        {records.map((r) => (
          <div key={r.id} className="text-[11px] min-w-0 space-y-0.5">
            <div className="flex items-center gap-2 flex-wrap">
              <span
                className={
                  r.status === 'sent'
                    ? 'text-emerald-400'
                    : r.status === 'bounced'
                      ? 'text-amber-400'
                      : 'text-rose-400'
                }
              >
                {r.status}
              </span>
              <span className="text-zinc-500 break-all">to {r.recipient_email}</span>
              <span className="text-zinc-600 shrink-0">
                {new Date(r.created_at).toLocaleString()}
              </span>
            </div>
            {r.error_message && (
              <p className="text-rose-400/80 break-words">{r.error_message}</p>
            )}
          </div>
        ))}
      </div>
    );
  };

  if (isDelivered) {
    return (
      <div className="p-3 rounded-lg bg-emerald-950/20 border border-emerald-800/40 text-xs space-y-2">
        <div className="text-emerald-300 font-medium">Delivered to client</div>
        {renderHistory()}
      </div>
    );
  }

  if (inProgress || isPolling) {
    return (
      <div className="w-full py-2.5 px-4 rounded-lg bg-indigo-950/40 border border-indigo-800/40 text-indigo-300 font-medium text-xs flex items-center justify-center gap-2">
        <span className="w-3 h-3 rounded-full border-2 border-indigo-300/40 border-t-indigo-300 animate-spin" />
        Sending email…
      </div>
    );
  }

  if (!canDeliver) {
    return (
      <button
        disabled
        className="w-full py-2.5 px-4 rounded-lg bg-zinc-800/40 border border-zinc-700/40 text-zinc-500 font-medium text-xs flex items-center justify-between cursor-not-allowed"
      >
        <span>Send PDF to Client</span>
        <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400">
          Requires Document
        </span>
      </button>
    );
  }

  return (
    <div className="space-y-2 min-w-0">
      {draftError && <p className="text-xs text-rose-400 break-words">{draftError}</p>}
      {draft && (
        <div className="p-3 rounded-lg bg-[#090a0f] border border-[#1e2436] text-xs space-y-2 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <span className="text-zinc-500 shrink-0">To</span>
            <span className="text-zinc-300 font-mono break-all text-right">{draft.recipient_email}</span>
          </div>
          <div className="flex items-start justify-between gap-2">
            <span className="text-zinc-500 shrink-0">Subject</span>
            <span className="text-zinc-300 break-words text-right">{draft.subject}</span>
          </div>
          <button
            onClick={() => setShowFullBody((v) => !v)}
            className="text-indigo-400 hover:text-indigo-300 text-[11px] font-medium"
          >
            {showFullBody ? 'Hide email body' : 'Preview email body'}
          </button>
          {showFullBody && (
            <pre className="whitespace-pre-wrap break-words text-zinc-400 bg-[#050609] p-2 rounded border border-[#1e2436] max-h-64 overflow-y-auto overflow-x-hidden text-[11px]">
              {draft.body}
            </pre>
          )}
        </div>
      )}
      {sendError && <p className="text-xs text-rose-400 break-words">{sendError}</p>}
      <button
        onClick={send}
        disabled={isSending || !draft}
        className="w-full py-2.5 px-4 rounded-lg bg-indigo-600 hover:bg-indigo-500 border border-indigo-500/60 text-white font-medium text-xs flex items-center justify-center disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
      >
        {isSending
          ? 'Starting…'
          : status === 'DELIVERY_FAILED'
            ? 'Retry Send to Client'
            : 'Send PDF to Client'}
      </button>
      {renderHistory()}
    </div>
  );
}
