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
import { GenerateProposalButton } from '@/components/proposals/GenerateProposalButton';
import { ApproveSectionButton } from '@/components/proposals/ApproveSectionButton';
import { ApprovalPanel } from '@/components/proposals/ApprovalPanel';
import { ClaudeCallLogPanel } from '@/components/proposals/ClaudeCallLogPanel';
import { ActivityTimeline } from '@/components/proposals/ActivityTimeline';
import { GenerateDocumentButton } from '@/components/proposals/GenerateDocumentButton';
import { DocumentPreview } from '@/components/proposals/DocumentPreview';
import { DeliveryPanel } from '@/components/proposals/DeliveryPanel';
import { getServerAuthToken } from '@/lib/auth/serverSession';
import {
  buildRequestMoreInfoMailto,
  canApproveSection,
  canDeliver,
  canEditSection,
  canGenerateDocument,
  canTriggerGeneration,
  deliveryInProgress,
  documentIsReady,
  editInvalidatesApproval,
  hasThinIntake,
  isDelivered,
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
    const token = await getServerAuthToken();
    proposal = await getProposal(id, token);
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
          className="inline-flex items-center gap-1.5 text-xs text-[#5c646c] hover:text-[#1f2429] transition-colors"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
          </svg>
          Back to Proposals
        </Link>
        <div className="p-8 rounded-xl border border-rose-200 bg-rose-50 text-rose-800">
          <h2 className="text-base font-semibold text-rose-900">Error Loading Proposal</h2>
          <p className="text-xs text-rose-700 mt-1">{errorMessage}</p>
        </div>
      </div>
    );
  }

  const pendingCount = pendingSectionCount(proposal);
  const totalSections = proposal.sections ? proposal.sections.length : 0;
  const sectionsEditable = canEditSection(proposal);
  const editWillInvalidateApproval = editInvalidatesApproval(proposal);
  const sectionsApprovable = canApproveSection(proposal);
  const needsGeneration = canTriggerGeneration(proposal);
  const needsDocumentGeneration = canGenerateDocument(proposal);
  const documentReady = documentIsReady(proposal);
  const deliveryAllowed = canDeliver(proposal);
  const deliveryInFlight = deliveryInProgress(proposal);
  const deliveryDone = isDelivered(proposal);
  const thinIntake = hasThinIntake(proposal);

  return (
    <div className="space-y-8 pb-16 animate-fade-in-up">
      {/* Navigation & Header */}
      <div className="space-y-4">
        <Link
          href="/proposals"
          className="inline-flex items-center gap-1.5 text-xs font-medium text-[#5c646c] hover:text-[#2563eb] transition-colors"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
          </svg>
          Back to Proposals
        </Link>

        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-[#d8dbd9]">
          <div>
            <div className="flex items-center gap-3 flex-wrap">
              <h1 className="text-2xl sm:text-3xl font-bold text-[#1f2429] tracking-tight">
                {proposal.company_name}
              </h1>
              <ProposalStatusBadge status={proposal.status} size="md" />
            </div>
            <div className="flex items-center gap-3 text-xs text-[#5c646c] mt-2 flex-wrap">
              <span>Client: <strong className="text-[#1f2429]">{proposal.client_name}</strong></span>
              <span className="text-[#c2c7c4]">·</span>
              <span className="font-mono text-[#374151]">{proposal.client_email}</span>
              <span className="text-[#c2c7c4]">·</span>
              <span>Salesperson: <strong className="text-[#1f2429]">{proposal.salesperson_name}</strong></span>
              <span className="text-[#c2c7c4]">·</span>
              <span>Call Date: {proposal.date_of_call}</span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span className="px-3 py-1.5 rounded-lg bg-[#f5f6f5] border border-[#d8dbd9] text-xs font-mono text-[#5c646c]">
              ID: {proposal.id.slice(0, 8)}...
            </span>
          </div>
        </div>
      </div>

      {/* Thin-intake warning — flags a proposal built from sparse/placeholder-
          like discovery-call answers (e.g. "Goals: Goals") before it ever
          reaches the client, since Claude will produce grammatically fine
          but content-empty sections from thin input. See docs/edge-cases.md. */}
      {thinIntake && (
        <div className="p-4 rounded-xl bg-amber-50 border border-amber-200 text-xs text-amber-900 flex items-start gap-3">
          <div className="w-5 h-5 rounded-md bg-amber-100 border border-amber-300 flex items-center justify-center text-amber-600 flex-shrink-0 mt-0.5">
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v3.75m0 3.75h.008v.008H12v-.008zM21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <div className="space-y-2 flex-1">
            <div className="font-semibold text-amber-900">Intake looks thin</div>
            <div className="text-amber-800/90 leading-relaxed">
              Several intake fields are only a word or two — the generated sections will read as generic rather than tailored. Consider following up with the client for more detail before this goes any further.
            </div>
            <a
              href={buildRequestMoreInfoMailto(proposal)}
              className="inline-flex items-center gap-1.5 text-amber-800 hover:text-amber-900 font-medium underline underline-offset-2"
            >
              Email client for more detail
            </a>
          </div>
        </div>
      )}

      {/* Context-aware "what's next" hint */}
      {canDeliver(proposal) && (
        <div className="p-4 rounded-xl bg-[#2563eb]/5 border border-[#2563eb]/20 text-xs text-[#1e3a8a] flex items-start gap-3">
          <div className="w-5 h-5 rounded-md bg-[#2563eb]/10 border border-[#2563eb]/30 flex items-center justify-center text-[#2563eb] flex-shrink-0 mt-0.5">
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <div className="space-y-1">
            <div className="font-semibold text-[#1e3a8a]">Ready to send</div>
            <div className="text-[#1e3a8a]/80 leading-relaxed">
              Review the composed email draft and send it to the client from the panel on the left — email only, with a link (never an attachment), and no auto-send. Once sent, this proposal's sections and document can no longer be edited.
            </div>
          </div>
        </div>
      )}

      {/* Grid: Left column (Intake summary) & Right column (Sections list) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 items-start">
        {/* Left Column: Pinned Intake Data & Workflow Actions */}
        <div className="lg:col-span-1 space-y-6">
          {/* Canonical Intake Summary Card */}
          <div className="rounded-xl border border-[#d8dbd9] bg-white p-5 space-y-5 shadow-[0_8px_24px_-8px_rgba(31,36,41,0.1)]">
            <div className="flex items-center justify-between pb-3 border-b border-[#d8dbd9]">
              <h2 className="text-sm font-semibold text-[#1f2429] tracking-tight flex items-center gap-2">
                <svg className="w-4 h-4 text-[#2563eb]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                </svg>
                Canonical Intake Facts
              </h2>
              <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-[#f5f6f5] text-[#5c646c]">
                Pinned
              </span>
            </div>

            <div className="space-y-4 text-xs">
              <div>
                <span className="text-[#5c646c] font-medium">Estimated Pricing</span>
                <div className="mt-1 font-semibold text-[#1f2429] bg-[#f5f6f5] p-2.5 rounded-lg border border-[#d8dbd9]">
                  {proposal.estimated_pricing}
                </div>
              </div>

              <div>
                <span className="text-[#5c646c] font-medium">Proposed Timeline</span>
                <div className="mt-1 text-[#1f2429] bg-[#f5f6f5] p-2.5 rounded-lg border border-[#d8dbd9] whitespace-pre-line">
                  {proposal.proposed_timeline}
                </div>
              </div>

              <div>
                <span className="text-[#5c646c] font-medium">Recommended Services</span>
                <div className="mt-1 text-[#374151] bg-[#f5f6f5] p-2.5 rounded-lg border border-[#d8dbd9] leading-relaxed whitespace-pre-line">
                  {proposal.recommended_services}
                </div>
              </div>

              <div>
                <span className="text-[#5c646c] font-medium">Client Needs Summary</span>
                <div className="mt-1 text-[#374151] bg-[#f5f6f5] p-2.5 rounded-lg border border-[#d8dbd9] leading-relaxed whitespace-pre-line">
                  {proposal.client_needs_summary}
                </div>
              </div>

              <div>
                <span className="text-[#5c646c] font-medium">Project Scope</span>
                <div className="mt-1 text-[#374151] bg-[#f5f6f5] p-2.5 rounded-lg border border-[#d8dbd9] leading-relaxed whitespace-pre-line">
                  {proposal.project_scope}
                </div>
              </div>

              <div>
                <span className="text-[#5c646c] font-medium">Goals & Objectives</span>
                <div className="mt-1 text-[#374151] bg-[#f5f6f5] p-2.5 rounded-lg border border-[#d8dbd9] leading-relaxed whitespace-pre-line">
                  {proposal.goals_and_objectives}
                </div>
              </div>
            </div>
          </div>

          {/* Workflow Action Panel */}
          <div className="rounded-xl border border-[#d8dbd9] bg-white p-5 space-y-4 shadow-[0_8px_24px_-8px_rgba(31,36,41,0.1)]">
            <h2 className="text-sm font-semibold text-[#1f2429] tracking-tight flex items-center gap-2 pb-3 border-b border-[#d8dbd9]">
              <svg className="w-4 h-4 text-[#2563eb]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              Proposal Actions
            </h2>

            <div className="space-y-3">
              {needsGeneration ? (
                <GenerateProposalButton proposalId={proposal.id} status={proposal.status} />
              ) : (
                <>
                  {/* Approval guard summary */}
                  <div className="p-3 rounded-lg bg-[#f5f6f5] border border-[#d8dbd9] text-xs">
                    <div className="flex justify-between items-center text-[#374151] mb-1">
                      <span>Sections Approved:</span>
                      <span className="font-semibold text-[#2563eb]">
                        {totalSections - pendingCount} of {totalSections}
                      </span>
                    </div>
                    <div className="w-full h-1.5 bg-[#e5e7eb] rounded-full overflow-hidden">
                      <div
                        className="h-full bg-[#2563eb] transition-all duration-300"
                        style={{
                          width: totalSections > 0 ? `${((totalSections - pendingCount) / totalSections) * 100}%` : '0%',
                        }}
                      />
                    </div>
                  </div>

                  <ApprovalPanel proposal={proposal} />
                </>
              )}

              {/* Document Generation (Phase 6) */}
              {documentReady ? (
                <DocumentPreview proposalId={proposal.id} />
              ) : needsDocumentGeneration ? (
                <GenerateDocumentButton proposalId={proposal.id} status={proposal.status} />
              ) : (
                <button
                  disabled
                  className="w-full py-2.5 px-4 rounded-lg bg-[#f5f6f5] border border-[#d8dbd9] text-[#9aa0a6] font-medium text-xs flex items-center justify-between cursor-not-allowed"
                >
                  <span>Generate PDF Document</span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-white text-[#9aa0a6] border border-[#d8dbd9]">
                    Requires Approval
                  </span>
                </button>
              )}

              {/* Client Delivery (Phase 7) */}
              <DeliveryPanel
                proposalId={proposal.id}
                status={proposal.status}
                canDeliver={deliveryAllowed}
                inProgress={deliveryInFlight}
                isDelivered={deliveryDone}
              />
            </div>
          </div>
        </div>

        {/* Right Column: Sections List */}
        <div className="lg:col-span-2 space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-[#1f2429] tracking-tight">
              Proposal Sections ({proposal.sections?.length || 0})
            </h2>
            <span className="text-xs text-[#5c646c]">
              Order preserved from template
            </span>
          </div>

          <div className="space-y-5">
            {proposal.sections?.map((section, index) => (
              <div
                key={section.id}
                className="rounded-xl border border-[#d8dbd9] bg-white p-6 space-y-4 shadow-[0_8px_24px_-8px_rgba(31,36,41,0.1)] hover:border-[#c2c7c4] hover:-translate-y-0.5 hover:shadow-[0_12px_28px_-8px_rgba(31,36,41,0.16)] transition-all duration-200 animate-fade-in-up"
                style={{ animationDelay: `${Math.min(index * 60, 300)}ms` }}
              >
                {/* Section Header */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-[#d8dbd9]">
                  <div className="flex items-center gap-3">
                    <span className="w-6 h-6 rounded-md bg-[#2563eb]/10 border border-[#2563eb]/20 text-[#2563eb] font-mono text-xs flex items-center justify-center font-bold">
                      {section.order_index}
                    </span>
                    <h3 className="font-semibold text-[#1f2429] text-base">
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
                <div className="pt-2 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs text-[#5c646c] border-t border-[#eef0ee]">
                  <div className="flex items-center gap-3">
                    <span>Version {section.version}</span>
                    {isRegenerableSectionKey(section.section_key) ? (
                      <>
                        <span>·</span>
                        <span>
                          Regenerations:{' '}
                          <strong className="text-[#374151]">
                            {section.regeneration_count}/{MAX_REGENERATION_ATTEMPTS}
                          </strong>
                        </span>
                      </>
                    ) : (
                      <>
                        <span>·</span>
                        <span className="text-[#9aa0a6]">Pinned — not AI-generated</span>
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
                    <ApproveSectionButton
                      proposalId={proposal.id}
                      sectionKey={section.section_key}
                      approvalStatus={section.approval_status}
                      editable={sectionsApprovable}
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>

          <ClaudeCallLogPanel proposalId={proposal.id} />
          <ActivityTimeline proposalId={proposal.id} />
        </div>
      </div>
    </div>
  );
}
