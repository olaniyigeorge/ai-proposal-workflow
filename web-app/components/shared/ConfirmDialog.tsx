'use client';

import React from 'react';

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  message: string;
  confirmLabel: string;
  cancelLabel?: string;
  tone?: 'default' | 'danger';
  isBusy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

/** A real modal, not window.confirm() — used anywhere a clear, specific
 * message matters more than a generic browser confirm box (e.g. "Approve
 * this account? They will get full access to every client proposal."). */
export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel,
  cancelLabel = 'Cancel',
  tone = 'default',
  isBusy = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      role="dialog"
      aria-modal="true"
      onClick={onCancel}
    >
      <div
        className="w-full max-w-sm bg-white border border-[#d8dbd9] rounded-2xl p-6 shadow-[0_16px_40px_-12px_rgba(31,36,41,0.3)]"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-base font-semibold text-[#1f2429]">{title}</h2>
        <p className="text-sm text-[#5c646c] mt-2 leading-relaxed">{message}</p>
        <div className="flex items-center justify-end gap-2 mt-6">
          <button
            onClick={onCancel}
            disabled={isBusy}
            className="px-3 py-1.5 rounded-lg text-xs font-medium bg-white border border-[#d8dbd9] text-[#1f2429] hover:bg-[#f5f6f5] disabled:opacity-60 cursor-pointer"
          >
            {cancelLabel}
          </button>
          <button
            onClick={onConfirm}
            disabled={isBusy}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium text-white disabled:opacity-60 cursor-pointer ${
              tone === 'danger'
                ? 'bg-rose-600 hover:bg-rose-500'
                : 'bg-[#1f2429] hover:bg-[#111417]'
            }`}
          >
            {isBusy ? 'Working…' : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
