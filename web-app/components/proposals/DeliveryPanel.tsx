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
      <div className="space-y-2 pt-2 border-t border-teal-200 min-w-0">
        <p className="text-[11px] text-[#5c646c] font-medium">Delivery attempts</p>
        {records.map((r) => (
          <div key={r.id} className="text-[11px] min-w-0 space-y-0.5">
            <div className="flex items-center gap-2 flex-wrap">
              <span
                className={
                  r.status === 'sent'
                    ? 'text-emerald-700'
                    : r.status === 'bounced'
                      ? 'text-amber-700'
                      : 'text-rose-700'
                }
              >
                {r.status}
              </span>
              <span className="text-[#5c646c] break-all">to {r.recipient_email}</span>
              <span className="text-[#9aa0a6] shrink-0">
                {new Date(r.created_at).toLocaleString()}
              </span>
            </div>
            {r.error_message && (
              <p className="text-rose-700/80 break-words">{r.error_message}</p>
            )}
          </div>
        ))}
      </div>
    );
  };

  if (isDelivered) {
    return (
      <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-xs space-y-2">
        <div className="text-emerald-800 font-medium">Delivered to client</div>
        {renderHistory()}
      </div>
    );
  }

  if (inProgress || isPolling) {
    return (
      <div className="w-full py-2.5 px-4 rounded-lg bg-[#2563eb]/10 border border-[#2563eb]/20 text-[#2563eb] font-medium text-xs flex items-center justify-center gap-2">
        <span className="w-3 h-3 rounded-full border-2 border-[#2563eb]/40 border-t-[#2563eb] animate-spin" />
        Sending email…
      </div>
    );
  }

  if (!canDeliver) {
    return (
      <button
        disabled
        className="w-full py-2.5 px-4 rounded-lg bg-[#f5f6f5] border border-[#d8dbd9] text-[#9aa0a6] font-medium text-xs flex items-center justify-between cursor-not-allowed"
      >
        <span>Send PDF to Client</span>
        <span className="text-[10px] px-1.5 py-0.5 rounded bg-white text-[#9aa0a6] border border-[#d8dbd9]">
          Requires Document
        </span>
      </button>
    );
  }

  return (
    <div className="space-y-2 min-w-0">
      {draftError && <p className="text-xs text-rose-600 break-words">{draftError}</p>}
      {draft && (
        <div className="p-3 rounded-lg bg-[#f5f6f5] border border-[#d8dbd9] text-xs space-y-2 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <span className="text-[#5c646c] shrink-0">To</span>
            <span className="text-[#374151] font-mono break-all text-right">{draft.recipient_email}</span>
          </div>
          <div className="flex items-start justify-between gap-2">
            <span className="text-[#5c646c] shrink-0">Subject</span>
            <span className="text-[#374151] break-words text-right">{draft.subject}</span>
          </div>
          <button
            onClick={() => setShowFullBody((v) => !v)}
            className="text-[#2563eb] hover:text-[#1d4ed8] text-[11px] font-medium"
          >
            {showFullBody ? 'Hide email body' : 'Preview email body'}
          </button>
          {showFullBody && (
            <pre className="whitespace-pre-wrap break-words text-[#374151] bg-white p-2 rounded border border-[#d8dbd9] max-h-64 overflow-y-auto overflow-x-hidden text-[11px]">
              {draft.body}
            </pre>
          )}
        </div>
      )}
      {sendError && <p className="text-xs text-rose-600 break-words">{sendError}</p>}
      <button
        onClick={send}
        disabled={isSending || !draft}
        className="w-full py-2.5 px-4 rounded-lg bg-[#1f2429] hover:bg-[#111417] border border-[#1f2429] text-white font-medium text-xs flex items-center justify-center disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
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
