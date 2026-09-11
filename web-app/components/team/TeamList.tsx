'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { approveAccount, rejectAccount, updateMyDisplayName } from '@/lib/api/client';
import { ApiError } from '@/lib/api/types';
import type { SalespersonAccountResponse, SalespersonProfileResponse } from '@/lib/api/types';
import { ConfirmDialog } from '@/components/shared/ConfirmDialog';

interface TeamListProps {
  me: SalespersonProfileResponse;
  initialAccounts: SalespersonAccountResponse[];
}

const STATUS_STYLES: Record<string, string> = {
  pending: 'bg-amber-50 text-amber-700 border-amber-200',
  approved: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  rejected: 'bg-rose-50 text-rose-700 border-rose-200',
};

export function TeamList({ me, initialAccounts }: TeamListProps) {
  const router = useRouter();
  const [accounts, setAccounts] = useState(initialAccounts);
  const [displayName, setDisplayName] = useState(me.display_name || '');
  const [savingName, setSavingName] = useState(false);
  const [nameError, setNameError] = useState<string | null>(null);
  const [nameSaved, setNameSaved] = useState(false);

  const [pendingAction, setPendingAction] = useState<
    { account: SalespersonAccountResponse; kind: 'approve' | 'reject' } | null
  >(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [isActing, setIsActing] = useState(false);

  const saveDisplayName = async () => {
    if (!displayName.trim()) {
      setNameError('Display name cannot be empty.');
      return;
    }
    setSavingName(true);
    setNameError(null);
    setNameSaved(false);
    try {
      await updateMyDisplayName(displayName.trim());
      setNameSaved(true);
      router.refresh();
    } catch (err) {
      setNameError(err instanceof ApiError ? err.message : 'Failed to save display name.');
    } finally {
      setSavingName(false);
    }
  };

  const runAction = async () => {
    if (!pendingAction) return;
    setIsActing(true);
    setActionError(null);
    try {
      const updated =
        pendingAction.kind === 'approve'
          ? await approveAccount(pendingAction.account.id)
          : await rejectAccount(pendingAction.account.id);
      setAccounts((prev) => prev.map((a) => (a.id === updated.id ? updated : a)));
      setPendingAction(null);
      router.refresh();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : 'Action failed.');
    } finally {
      setIsActing(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Your profile */}
      <div className="rounded-xl border border-[#d8dbd9] bg-white p-5 space-y-3 shadow-[0_8px_24px_-8px_rgba(31,36,41,0.1)]">
        <h2 className="text-sm font-semibold text-[#1f2429]">Your Display Name</h2>
        <p className="text-xs text-[#5c646c]">
          This is the name written into a proposal&apos;s Salesperson field when you claim an unassigned one. It must be unique across the team.
        </p>
        <div className="flex flex-col sm:flex-row gap-2">
          <input
            type="text"
            value={displayName}
            onChange={(e) => {
              setDisplayName(e.target.value);
              setNameSaved(false);
            }}
            placeholder="e.g. Olaniyi George"
            className="flex-1 px-3 py-2 rounded-lg bg-white border border-[#d8dbd9] text-sm text-[#1f2429] placeholder:text-[#9aa0a6] focus:outline-none focus:border-[#2563eb]/60"
          />
          <button
            onClick={saveDisplayName}
            disabled={savingName}
            className="px-4 py-2 rounded-lg bg-[#1f2429] hover:bg-[#111417] text-white text-xs font-medium disabled:opacity-60 cursor-pointer"
          >
            {savingName ? 'Saving…' : 'Save Name'}
          </button>
        </div>
        {nameError && <p className="text-xs text-rose-600">{nameError}</p>}
        {nameSaved && !nameError && <p className="text-xs text-emerald-600">Saved.</p>}
      </div>

      {/* Team list */}
      <div className="rounded-xl border border-[#d8dbd9] bg-white overflow-hidden shadow-[0_8px_24px_-8px_rgba(31,36,41,0.1)]">
        <div className="px-5 py-4 border-b border-[#d8dbd9]">
          <h2 className="text-sm font-semibold text-[#1f2429]">Salespeople ({accounts.length})</h2>
        </div>
        {actionError && (
          <p className="px-5 pt-3 text-xs text-rose-600">{actionError}</p>
        )}
        <div className="divide-y divide-[#eef0ee]">
          {accounts.map((account) => {
            const isSelf = account.email === me.email;
            return (
              <div
                key={account.id}
                className="px-5 py-4 flex items-center justify-between gap-3 flex-wrap"
              >
                <div className="min-w-0">
                  <div className="text-sm font-medium text-[#1f2429] truncate">
                    {account.display_name || account.email}
                    {isSelf && <span className="text-[#9aa0a6] font-normal"> (you)</span>}
                  </div>
                  <div className="text-xs text-[#5c646c] font-mono truncate">{account.email}</div>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <span
                    className={`px-2 py-0.5 rounded-full text-[11px] font-medium border uppercase tracking-wide ${
                      STATUS_STYLES[account.status] || 'bg-[#f5f6f5] text-[#5c646c] border-[#d8dbd9]'
                    }`}
                  >
                    {account.status}
                  </span>
                  {account.status === 'pending' && !isSelf && (
                    <>
                      <button
                        onClick={() => setPendingAction({ account, kind: 'approve' })}
                        className="px-2.5 py-1 rounded bg-emerald-50 border border-emerald-200 text-emerald-700 text-[11px] font-medium hover:bg-emerald-100 cursor-pointer"
                      >
                        Approve
                      </button>
                      <button
                        onClick={() => setPendingAction({ account, kind: 'reject' })}
                        className="px-2.5 py-1 rounded bg-rose-50 border border-rose-200 text-rose-700 text-[11px] font-medium hover:bg-rose-100 cursor-pointer"
                      >
                        Reject
                      </button>
                    </>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <ConfirmDialog
        open={pendingAction !== null}
        title={
          pendingAction?.kind === 'approve' ? 'Approve this salesperson?' : 'Reject this account?'
        }
        message={
          pendingAction?.kind === 'approve'
            ? `${pendingAction.account.email} will gain full access to every client proposal in this system — the same access you have. There is no separate, more limited role.`
            : `${pendingAction?.account.email} will not be able to sign in or access any proposal data. You can approve them later if this was a mistake.`
        }
        confirmLabel={pendingAction?.kind === 'approve' ? 'Approve' : 'Reject'}
        tone={pendingAction?.kind === 'reject' ? 'danger' : 'default'}
        isBusy={isActing}
        onConfirm={runAction}
        onCancel={() => setPendingAction(null)}
      />
    </div>
  );
}
