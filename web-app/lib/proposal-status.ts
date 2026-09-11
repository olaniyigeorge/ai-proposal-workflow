import {
  ProposalStatus,
  SectionApprovalStatus,
  ContentOrigin,
  ProposalDetailResponse,
  ProposalSectionResponse,
  SectionKey,
} from './api/types';

export interface StatusConfig {
  label: string;
  badgeClass: string;
  dotClass: string;
  description: string;
  isTransient?: boolean;
  isFailed?: boolean;
}

export const PROPOSAL_STATUS_CONFIG: Record<ProposalStatus, StatusConfig> = {
  DRAFT: {
    label: 'Draft',
    badgeClass: 'bg-[#f5f6f5] text-[#5c646c] border-[#d8dbd9]',
    dotClass: 'bg-[#8a8f8c]',
    description: 'Intake received. Sections not yet generated.',
  },
  GENERATING: {
    label: 'Generating AI Content',
    badgeClass: 'bg-[#2563eb]/10 text-[#2563eb] border-[#2563eb]/20',
    dotClass: 'bg-[#2563eb] animate-pulse',
    description: 'Claude is generating proposal sections in the background.',
    isTransient: true,
  },
  GENERATION_FAILED: {
    label: 'Generation Failed',
    badgeClass: 'bg-rose-50 text-rose-700 border-rose-200',
    dotClass: 'bg-rose-500',
    description: 'Section generation encountered an error. Retry available.',
    isFailed: true,
  },
  IN_REVIEW: {
    label: 'In Review',
    badgeClass: 'bg-amber-50 text-amber-700 border-amber-200',
    dotClass: 'bg-amber-500',
    description: 'Proposal is under salesperson review and editing.',
  },
  PENDING_APPROVAL: {
    label: 'Pending Approval',
    badgeClass: 'bg-sky-50 text-sky-700 border-sky-200',
    dotClass: 'bg-sky-500',
    description: 'Ready for final review and approval.',
  },
  APPROVED: {
    label: 'Approved',
    badgeClass: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    dotClass: 'bg-emerald-500',
    description: 'All sections approved. Ready for document rendering.',
  },
  DOCUMENT_GENERATING: {
    label: 'Rendering Document',
    badgeClass: 'bg-[#2563eb]/10 text-[#2563eb] border-[#2563eb]/20',
    dotClass: 'bg-[#2563eb] animate-pulse',
    description: 'Generating high-fidelity branded PDF.',
    isTransient: true,
  },
  DOCUMENT_GENERATION_FAILED: {
    label: 'PDF Render Failed',
    badgeClass: 'bg-rose-50 text-rose-700 border-rose-200',
    dotClass: 'bg-rose-500',
    description: 'Document rendering failed. Retry available.',
    isFailed: true,
  },
  DOCUMENT_READY: {
    label: 'Document Ready',
    badgeClass: 'bg-teal-50 text-teal-700 border-teal-200',
    dotClass: 'bg-teal-500',
    description: 'Final PDF generated and stored. Ready for client delivery.',
  },
  DELIVERING: {
    label: 'Sending to Client',
    badgeClass: 'bg-[#2563eb]/10 text-[#2563eb] border-[#2563eb]/20',
    dotClass: 'bg-[#2563eb] animate-pulse',
    description: 'Sending proposal email with PDF attachment.',
    isTransient: true,
  },
  DELIVERY_FAILED: {
    label: 'Delivery Failed',
    badgeClass: 'bg-rose-50 text-rose-700 border-rose-200',
    dotClass: 'bg-rose-500',
    description: 'Email delivery failed or bounced. Retry available.',
    isFailed: true,
  },
  DELIVERED: {
    label: 'Delivered',
    badgeClass: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    dotClass: 'bg-emerald-500',
    description: 'Delivered to client via email.',
  },
  REJECTED: {
    label: 'Changes Requested',
    badgeClass: 'bg-rose-50 text-rose-700 border-rose-200',
    dotClass: 'bg-rose-500',
    description: 'Approval rejected with feedback. Returned to In Review.',
  },
  CLOSED: {
    label: 'Closed',
    badgeClass: 'bg-[#f5f6f5] text-[#8a8f8c] border-[#d8dbd9]',
    dotClass: 'bg-[#8a8f8c]',
    description: 'Workflow concluded.',
  },
};

export function getStatusConfig(status: ProposalStatus | string): StatusConfig {
  const normalized = status as ProposalStatus;
  return (
    PROPOSAL_STATUS_CONFIG[normalized] || {
      label: status,
      badgeClass: 'bg-[#f5f6f5] text-[#5c646c] border-[#d8dbd9]',
      dotClass: 'bg-[#8a8f8c]',
      description: status,
    }
  );
}

export function isTransientStatus(status: ProposalStatus | string): boolean {
  return ['GENERATING', 'DOCUMENT_GENERATING', 'DELIVERING'].includes(status);
}

export function isFailedStatus(status: ProposalStatus | string): boolean {
  return [
    'GENERATION_FAILED',
    'DOCUMENT_GENERATION_FAILED',
    'DELIVERY_FAILED',
  ].includes(status);
}

export interface SectionStatusConfig {
  label: string;
  badgeClass: string;
  dotClass: string;
}

export const SECTION_STATUS_CONFIG: Record<SectionApprovalStatus, SectionStatusConfig> = {
  pending: {
    label: 'Pending Review',
    badgeClass: 'bg-amber-50 text-amber-700 border-amber-200',
    dotClass: 'bg-amber-500',
  },
  approved: {
    label: 'Section Approved',
    badgeClass: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    dotClass: 'bg-emerald-500',
  },
};

export function getSectionStatusConfig(status: SectionApprovalStatus | string): SectionStatusConfig {
  const normalized = status as SectionApprovalStatus;
  return (
    SECTION_STATUS_CONFIG[normalized] || {
      label: status,
      badgeClass: 'bg-[#f5f6f5] text-[#5c646c] border-[#d8dbd9]',
      dotClass: 'bg-[#8a8f8c]',
    }
  );
}

export interface ContentOriginConfig {
  label: string;
  badgeClass: string;
  description: string;
}

export const CONTENT_ORIGIN_CONFIG: Record<ContentOrigin, ContentOriginConfig> = {
  template_default: {
    label: 'Template Boilerplate',
    badgeClass: 'bg-[#f5f6f5] text-[#5c646c] border-[#d8dbd9]',
    description: 'Default template structure',
  },
  ai_generated: {
    label: 'AI Generated',
    badgeClass: 'bg-violet-50 text-violet-700 border-violet-200',
    description: 'Generated by Claude from intake submission',
  },
  human_edited: {
    label: 'Human Edited',
    badgeClass: 'bg-blue-50 text-blue-700 border-blue-200',
    description: 'Manually edited by salesperson',
  },
  human_edited_after_generation: {
    label: 'Edited After AI',
    badgeClass: 'bg-cyan-50 text-cyan-700 border-cyan-200',
    description: 'AI-generated then customized by salesperson',
  },
};

export function getContentOriginConfig(origin: ContentOrigin | string): ContentOriginConfig {
  const normalized = origin as ContentOrigin;
  return (
    CONTENT_ORIGIN_CONFIG[normalized] || {
      label: origin.replace(/_/g, ' '),
      badgeClass: 'bg-[#f5f6f5] text-[#5c646c] border-[#d8dbd9]',
      description: origin,
    }
  );
}

export function pendingSectionCount(proposal: ProposalDetailResponse): number {
  if (!proposal.sections) return 0;
  return proposal.sections.filter(
    (s) => s.approval_status.toLowerCase() !== 'approved'
  ).length;
}

export function canSubmitForApproval(proposal: ProposalDetailResponse): boolean {
  return proposal.status === 'IN_REVIEW';
}

const EDITABLE_SECTION_STATUSES: ProposalStatus[] = [
  'IN_REVIEW',
  'PENDING_APPROVAL',
  'APPROVED',
];

export function canEditSection(proposal: ProposalDetailResponse): boolean {
  return EDITABLE_SECTION_STATUSES.includes(proposal.status as ProposalStatus);
}

export function editInvalidatesApproval(proposal: ProposalDetailResponse): boolean {
  return proposal.status === 'PENDING_APPROVAL' || proposal.status === 'APPROVED';
}

// Every section has some Claude-generated content as of 2026-09-11 (see
// backend/app/domain/generation.py GENERATED_SECTION_KEYS) — Timeline and
// Pricing wrap a generated lead-in around the pinned/verbatim date or price
// (the number itself is never something Claude is asked to restate), and
// Next Steps is a fully generated closing paragraph. Introduction is
// generated (not pinned) specifically so the client's raw intake wording
// gets paraphrased/cleaned up rather than reaching the client verbatim —
// see docs/edge-cases.md.
export const GENERATED_SECTION_KEYS: SectionKey[] = [
  'introduction',
  'proposed_solution',
  'deliverables',
  'timeline',
  'pricing',
  'next_steps',
];

export const MAX_REGENERATION_ATTEMPTS = 3;

export function isRegenerableSectionKey(sectionKey: SectionKey | string): boolean {
  return GENERATED_SECTION_KEYS.includes(sectionKey as SectionKey);
}

export function canRegenerateSection(
  proposal: ProposalDetailResponse,
  section: ProposalSectionResponse
): boolean {
  return (
    canEditSection(proposal) &&
    isRegenerableSectionKey(section.section_key) &&
    section.regeneration_count < MAX_REGENERATION_ATTEMPTS
  );
}

// "Approve Proposal" is the bulk action (system-flow.md §3): it force-approves
// every still-pending section and finalizes in one call, so it's available
// whenever the state machine allows it — not gated on pendingSectionCount,
// which was a Phase-1-era assumption from before the bulk-approve semantics
// were decided in Phase 5. The UI still surfaces the pending count so the
// salesperson knows what they're about to force-approve.
export function canApproveProposal(proposal: ProposalDetailResponse): boolean {
  return proposal.status === 'IN_REVIEW' || proposal.status === 'PENDING_APPROVAL';
}

export function canApproveSection(proposal: ProposalDetailResponse): boolean {
  return proposal.status === 'IN_REVIEW';
}

export function canRequestChangesOrReject(proposal: ProposalDetailResponse): boolean {
  return proposal.status === 'PENDING_APPROVAL';
}

export function canTriggerGeneration(proposal: ProposalDetailResponse): boolean {
  return proposal.status === 'DRAFT' || proposal.status === 'GENERATION_FAILED';
}

export function canGenerateDocument(proposal: ProposalDetailResponse): boolean {
  return (
    proposal.status === 'APPROVED' || proposal.status === 'DOCUMENT_GENERATION_FAILED'
  );
}

export function documentIsReady(proposal: ProposalDetailResponse): boolean {
  return (
    proposal.status === 'DOCUMENT_READY' ||
    proposal.status === 'DELIVERING' ||
    proposal.status === 'DELIVERY_FAILED' ||
    proposal.status === 'DELIVERED' ||
    proposal.status === 'CLOSED'
  );
}

export function canDeliver(proposal: ProposalDetailResponse): boolean {
  return proposal.status === 'DOCUMENT_READY' || proposal.status === 'DELIVERY_FAILED';
}

export function deliveryInProgress(proposal: ProposalDetailResponse): boolean {
  return proposal.status === 'DELIVERING';
}

export function isDelivered(proposal: ProposalDetailResponse): boolean {
  return proposal.status === 'DELIVERED' || proposal.status === 'CLOSED';
}

// Fields that free-text answers, tested for "thin" content below. Pricing/
// timeline/date are naturally short ("$5,000", "6 weeks") and aren't useful
// thinness signals, so they're deliberately excluded.
const NARRATIVE_FIELDS: (keyof ProposalDetailResponse)[] = [
  'client_needs_summary',
  'project_scope',
  'goals_and_objectives',
  'recommended_services',
];

const THIN_WORD_THRESHOLD = 4;

/**
 * Flags an intake that's too sparse to write a real proposal from — e.g. a
 * test/demo submission, or a discovery call where the notes never actually
 * got filled in. Claude will still dutifully generate grammatically fine
 * sections from "Goals: Goals" / "Scope: deliverables", but the result reads
 * as content-free to the client — this is a business-quality problem the
 * pipeline can't catch on its own, so the salesperson needs to be told to go
 * back to the client for more detail before this ships. Threshold: 2+
 * narrative fields under 4 words, which a genuine discovery-call answer
 * essentially never is (see docs/edge-cases.md, 2026-09-11).
 */
export function thinIntakeFields(proposal: ProposalDetailResponse): string[] {
  return NARRATIVE_FIELDS.filter((field) => {
    const value = proposal[field];
    if (typeof value !== 'string') return false;
    const wordCount = value.trim().split(/\s+/).filter(Boolean).length;
    return wordCount > 0 && wordCount < THIN_WORD_THRESHOLD;
  });
}

export function hasThinIntake(proposal: ProposalDetailResponse): boolean {
  return thinIntakeFields(proposal).length >= 2;
}

const FIELD_LABELS: Record<string, string> = {
  client_needs_summary: "the client's needs",
  project_scope: 'the project scope',
  goals_and_objectives: 'their goals and objectives',
  recommended_services: 'recommended services/deliverables',
};

/** A pre-filled mailto: link so the salesperson can ask the client for more
 * detail in one click rather than writing the request from scratch. */
export function buildRequestMoreInfoMailto(proposal: ProposalDetailResponse): string {
  const thin = thinIntakeFields(proposal);
  const topics = thin.map((f) => FIELD_LABELS[f] || f).join(', ');
  const subject = `Quick follow-up on your ${proposal.company_name} proposal`;
  const body = [
    `Hi ${proposal.client_name},`,
    '',
    "Before we finalize your proposal, we'd like a bit more detail so we can " +
      `tailor it properly — specifically around ${topics}.`,
    '',
    'Could you share a few more sentences on this when you get a chance?',
    '',
    'Thanks,',
  ].join('\n');
  return `mailto:${encodeURIComponent(proposal.client_email)}?subject=${encodeURIComponent(
    subject
  )}&body=${encodeURIComponent(body)}`;
}
