import React from 'react';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import { getProposal } from '@/lib/api/client';
import { ProposalDetailResponse } from '@/lib/api/types';
import { ProposalStatusBadge } from '@/components/proposals/ProposalStatusBadge';
import { SectionApprovalBadge } from '@/components/proposals/SectionApprovalBadge';
import { ContentOriginBadge } from '@/components/proposals/ContentOriginBadge';
import { SectionEditor } from '@/components/proposals/SectionEditor';
import { RegenerateSectionButton } from '@/components/proposals/RegenerateSectionButton';
import {
  canEditSection,
  editInvalidatesApproval,
  isRegenerableSectionKey,
  MAX_REGENERATION_ATTEMPTS,
  pendingSectionCount,
} from '@/lib/proposal-status';

export const dynamic = 'force-dynamic';

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function ProposalDetailPage({ params }: PageProps) {
  const { id } = await params;
  let proposal: ProposalDetailResponse | null = null;
  let errorMessage: string | null = null;

  try {
    proposal = await getProposal(id);
  } catch (err: any) {
    if (err?.status === 404) {
      notFound();
    }
    errorMessage = err?.message || 'Failed to load proposal details';
  }

  if (!proposal) {
    return (
      <div className="space-y-6">
        <Link
          href="/proposals"
          className="inline-flex items-center gap-1.5 text-xs text-zinc-400 hover:text-white transition-colors"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
          </svg>
          Back to Proposals
        </Link>
        <div className="p-8 rounded-xl border border-rose-800/40 bg-rose-950/30 text-rose-200">
          <h2 className="text-base font-semibold text-rose-300">Error Loading Proposal</h2>
          <p className="text-xs text-rose-400/90 mt-1">{errorMessage}</p>
        </div>
      </div>
    );
  }

  const pendingCount = pendingSectionCount(proposal);
  const totalSections = proposal.sections ? proposal.sections.length : 0;
  const sectionsEditable = canEditSection(proposal);
  const editWillInvalidateApproval = editInvalidatesApproval(proposal);

  return (
    <div className="space-y-8 pb-16">
      {/* Navigation & Header */}
      <div className="space-y-4">
        <Link
          href="/proposals"
          className="inline-flex items-center gap-1.5 text-xs font-medium text-zinc-400 hover:text-indigo-300 transition-colors"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
          </svg>
          Back to Proposals
        </Link>

        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-[#1e2436]">
          <div>
            <div className="flex items-center gap-3 flex-wrap">
              <h1 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
                {proposal.company_name}
              </h1>
              <ProposalStatusBadge status={proposal.status} size="md" />
            </div>
            <div className="flex items-center gap-3 text-xs text-zinc-400 mt-2 flex-wrap">
              <span>Client: <strong className="text-zinc-200">{proposal.client_name}</strong></span>
              <span className="text-zinc-600">�</span>
              <span className="font-mono text-zinc-300">{proposal.client_email}</span>
              <span className="text-zinc-600">�</span>
              <span>Salesperson: <strong className="text-zinc-200">{proposal.salesperson_name}</strong></span>
              <span className="text-zinc-600">�</span>
              <span>Call Date: {proposal.date_of_call}</span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span className="px-3 py-1.5 rounded-lg bg-[#121520] border border-[#1e2436] text-xs font-mono text-zinc-400">
              ID: {proposal.id.slice(0, 8)}...
            </span>
          </div>
        </div>
      </div>

      {/* Phase Notification Banner */}
      <div className="p-4 rounded-xl bg-indigo-950/30 border border-indigo-800/40 text-xs text-indigo-200 flex items-start gap-3">
        <div className="w-5 h-5 rounded-md bg-indigo-600/30 border border-indigo-500/40 flex items-center justify-center text-indigo-400 flex-shrink-0 mt-0.5">
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>
        <div className="space-y-1">
          <div className="font-semibold text-indigo-300">Phase 4 Section Regeneration Active</div>
          <div className="text-indigo-300/80 leading-relaxed">
            Section content is editable in place, and Proposed Solution / Deliverables can be regenerated via Claude with a required instruction (capped at 3 attempts each). Final Approval remains disabled below and will activate once Phase 5 lands.
          </div>
        </div>
      </div>

      {/* Grid: Left column (Intake summary) & Right column (Sections list) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 items-start">
        {/* Left Column: Pinned Intake Data & Workflow Actions */}
        <div className="lg:col-span-1 space-y-6">
          {/* Canonical Intake Summary Card */}
          <div className="rounded-xl border border-[#1e2436] bg-[#121520] p-5 space-y-5 shadow-lg shadow-black/20">
            <div className="flex items-center justify-between pb-3 border-b border-[#1e2436]">
              <h2 className="text-sm font-semibold text-white tracking-tight flex items-center gap-2">
                <svg className="w-4 h-4 text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                </svg>
                Canonical Intake Facts
              </h2>
              <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-zinc-800 text-zinc-400">
                Pinned
              </span>
            </div>

            <div className="space-y-4 text-xs">
              <div>
                <span className="text-zinc-500 font-medium">Estimated Pricing</span>
                <div className="mt-1 font-semibold text-zinc-100 bg-[#090a0f] p-2.5 rounded-lg border border-[#1e2436]">
                  {proposal.estimated_pricing}
                </div>
              </div>

              <div>
                <span className="text-zinc-500 font-medium">Proposed Timeline</span>
                <div className="mt-1 text-zinc-200 bg-[#090a0f] p-2.5 rounded-lg border border-[#1e2436] whitespace-pre-line">
                  {proposal.proposed_timeline}
                </div>
              </div>

              <div>
                <span className="text-zinc-500 font-medium">Recommended Services</span>
                <div className="mt-1 text-zinc-300 bg-[#090a0f] p-2.5 rounded-lg border border-[#1e2436] leading-relaxed whitespace-pre-line">
                  {proposal.recommended_services}
                </div>
              </div>

              <div>
                <span className="text-zinc-500 font-medium">Client Needs Summary</span>
                <div className="mt-1 text-zinc-300 bg-[#090a0f] p-2.5 rounded-lg border border-[#1e2436] leading-relaxed whitespace-pre-line">
                  {proposal.client_needs_summary}
                </div>
              </div>

              <div>
                <span className="text-zinc-500 font-medium">Project Scope</span>
                <div className="mt-1 text-zinc-300 bg-[#090a0f] p-2.5 rounded-lg border border-[#1e2436] leading-relaxed whitespace-pre-line">
                  {proposal.project_scope}
                </div>
              </div>

              <div>
                <span className="text-zinc-500 font-medium">Goals & Objectives</span>
                <div className="mt-1 text-zinc-300 bg-[#090a0f] p-2.5 rounded-lg border border-[#1e2436] leading-relaxed whitespace-pre-line">
                  {proposal.goals_and_objectives}
                </div>
              </div>
            </div>
          </div>

          {/* Workflow Action Panel (Read-only / Coming Soon) */}
          <div className="rounded-xl border border-[#1e2436] bg-[#121520] p-5 space-y-4 shadow-lg shadow-black/20">
            <h2 className="text-sm font-semibold text-white tracking-tight flex items-center gap-2 pb-3 border-b border-[#1e2436]">
              <svg className="w-4 h-4 text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              Proposal Actions
            </h2>

            <div className="space-y-3">
              {/* Approval guard summary */}
              <div className="p-3 rounded-lg bg-[#090a0f] border border-[#1e2436] text-xs">
                <div className="flex justify-between items-center text-zinc-300 mb-1">
                  <span>Sections Approved:</span>
                  <span className="font-semibold text-indigo-300">
                    {totalSections - pendingCount} of {totalSections}
                  </span>
                </div>
                <div className="w-full h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-indigo-500 transition-all duration-300"
                    style={{
                      width: totalSections > 0 ? `${((totalSections - pendingCount) / totalSections) * 100}%` : '0%',
                    }}
                  />
                </div>
              </div>

              {/* Approve Whole Proposal Button (Disabled) */}
              <button
                disabled
                className="w-full py-2.5 px-4 rounded-lg bg-emerald-950/40 border border-emerald-800/40 text-emerald-400/60 font-medium text-xs flex items-center justify-between cursor-not-allowed"
              >
                <span>Approve Proposal</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400">
                  Phase 5
                </span>
              </button>

              {/* Generate PDF Button (Disabled) */}
              <button
                disabled
                className="w-full py-2.5 px-4 rounded-lg bg-zinc-800/40 border border-zinc-700/40 text-zinc-500 font-medium text-xs flex items-center justify-between cursor-not-allowed"
              >
                <span>Generate PDF Document</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400">
                  Phase 6
                </span>
              </button>

              {/* Deliver to Client Button (Disabled) */}
              <button
                disabled
                className="w-full py-2.5 px-4 rounded-lg bg-zinc-800/40 border border-zinc-700/40 text-zinc-500 font-medium text-xs flex items-center justify-between cursor-not-allowed"
              >
                <span>Send PDF to Client</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400">
                  Phase 7
                </span>
              </button>
            </div>
          </div>
        </div>

        {/* Right Column: Sections List */}
        <div className="lg:col-span-2 space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-white tracking-tight">
              Proposal Sections ({proposal.sections?.length || 0})
            </h2>
            <span className="text-xs text-zinc-400">
              Order preserved from template
            </span>
          </div>

          <div className="space-y-5">
            {proposal.sections?.map((section) => (
              <div
                key={section.id}
                className="rounded-xl border border-[#1e2436] bg-[#121520] p-6 space-y-4 shadow-lg shadow-black/20 hover:border-[#2e3752] transition-colors"
              >
                {/* Section Header */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-[#1e2436]">
                  <div className="flex items-center gap-3">
                    <span className="w-6 h-6 rounded-md bg-indigo-950 border border-indigo-800/50 text-indigo-300 font-mono text-xs flex items-center justify-center font-bold">
                      {section.order_index}
                    </span>
                    <h3 className="font-semibold text-white text-base">
                      {section.title}
                    </h3>
                  </div>

                  <div className="flex items-center gap-2 flex-wrap">
                    <ContentOriginBadge origin={section.content_origin} />
                    <SectionApprovalBadge status={section.approval_status} />
                  </div>
                </div>

                {/* Section Content (editable in place) */}
                <SectionEditor
                  proposalId={proposal.id}
                  section={section}
                  editable={sectionsEditable}
                  invalidatesApproval={editWillInvalidateApproval}
                />

                {/* Section Footer: Meta & Action Triggers */}
                <div className="pt-2 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs text-zinc-500 border-t border-[#1e2436]/50">
                  <div className="flex items-center gap-3">
                    <span>Version {section.version}</span>
                    {isRegenerableSectionKey(section.section_key) ? (
                      <>
                        <span>·</span>
                        <span>
                          Regenerations:{' '}
                          <strong className="text-zinc-400">
                            {section.regeneration_count}/{MAX_REGENERATION_ATTEMPTS}
                          </strong>
                        </span>
                      </>
                    ) : (
                      <>
                        <span>·</span>
                        <span className="text-zinc-600">Pinned — not AI-generated</span>
                      </>
                    )}
                  </div>

                  <div className="flex items-center gap-2">
                    {isRegenerableSectionKey(section.section_key) && (
                      <RegenerateSectionButton
                        proposalId={proposal.id}
                        section={section}
                        editable={sectionsEditable}
                      />
                    )}
                    <button
                      disabled
                      className="px-2.5 py-1 rounded bg-zinc-800/50 border border-zinc-700/50 text-zinc-500 text-[11px] font-medium cursor-not-allowed"
                    >
                      Approve (Phase 5)
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
