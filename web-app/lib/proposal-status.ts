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
    badgeClass: 'bg-zinc-800/80 text-zinc-300 border-zinc-700/60',
    dotClass: 'bg-zinc-400',
    description: 'Intake received. Sections not yet generated.',
  },
  GENERATING: {
    label: 'Generating AI Content',
    badgeClass: 'bg-indigo-950/80 text-indigo-300 border-indigo-700/60',
    dotClass: 'bg-indigo-400 animate-pulse',
    description: 'Claude is generating proposal sections in the background.',
    isTransient: true,
  },
  GENERATION_FAILED: {
    label: 'Generation Failed',
    badgeClass: 'bg-rose-950/80 text-rose-300 border-rose-700/60',
    dotClass: 'bg-rose-400',
    description: 'Section generation encountered an error. Retry available.',
    isFailed: true,
  },
  IN_REVIEW: {
    label: 'In Review',
    badgeClass: 'bg-amber-950/80 text-amber-300 border-amber-700/60',
    dotClass: 'bg-amber-400',
    description: 'Proposal is under salesperson review and editing.',
  },
  PENDING_APPROVAL: {
    label: 'Pending Approval',
    badgeClass: 'bg-sky-950/80 text-sky-300 border-sky-700/60',
    dotClass: 'bg-sky-400',
    description: 'Ready for final review and approval.',
  },
  APPROVED: {
    label: 'Approved',
    badgeClass: 'bg-emerald-950/80 text-emerald-300 border-emerald-700/60',
    dotClass: 'bg-emerald-400',
    description: 'All sections approved. Ready for document rendering.',
  },
  DOCUMENT_GENERATING: {
    label: 'Rendering Document',
    badgeClass: 'bg-indigo-950/80 text-indigo-300 border-indigo-700/60',
    dotClass: 'bg-indigo-400 animate-pulse',
    description: 'Generating high-fidelity branded PDF.',
    isTransient: true,
  },
  DOCUMENT_GENERATION_FAILED: {
    label: 'PDF Render Failed',
    badgeClass: 'bg-rose-950/80 text-rose-300 border-rose-700/60',
    dotClass: 'bg-rose-400',
    description: 'Document rendering failed. Retry available.',
    isFailed: true,
  },
  DOCUMENT_READY: {
    label: 'Document Ready',
    badgeClass: 'bg-teal-950/80 text-teal-300 border-teal-700/60',
    dotClass: 'bg-teal-400',
    description: 'Final PDF generated and stored. Ready for client delivery.',
  },
  DELIVERING: {
    label: 'Sending to Client',
    badgeClass: 'bg-indigo-950/80 text-indigo-300 border-indigo-700/60',
    dotClass: 'bg-indigo-400 animate-pulse',
    description: 'Sending proposal email with PDF attachment.',
    isTransient: true,
  },
  DELIVERY_FAILED: {
    label: 'Delivery Failed',
    badgeClass: 'bg-rose-950/80 text-rose-300 border-rose-700/60',
    dotClass: 'bg-rose-400',
    description: 'Email delivery failed or bounced. Retry available.',
    isFailed: true,
  },
  DELIVERED: {
    label: 'Delivered',
    badgeClass: 'bg-emerald-950/80 text-emerald-300 border-emerald-700/60',
    dotClass: 'bg-emerald-400',
    description: 'Delivered to client via email.',
  },
  REJECTED: {
    label: 'Changes Requested',
    badgeClass: 'bg-rose-950/80 text-rose-300 border-rose-700/60',
    dotClass: 'bg-rose-400',
    description: 'Approval rejected with feedback. Returned to In Review.',
  },
  CLOSED: {
    label: 'Closed',
    badgeClass: 'bg-slate-900 text-slate-400 border-slate-700/50',
    dotClass: 'bg-slate-500',
    description: 'Workflow concluded.',
  },
};

export function getStatusConfig(status: ProposalStatus | string): StatusConfig {
  const normalized = status as ProposalStatus;
  return (
    PROPOSAL_STATUS_CONFIG[normalized] || {
      label: status,
      badgeClass: 'bg-zinc-800 text-zinc-300 border-zinc-700',
      dotClass: 'bg-zinc-400',
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
    badgeClass: 'bg-amber-950/60 text-amber-300 border-amber-800/40',
    dotClass: 'bg-amber-400',
  },
  approved: {
    label: 'Section Approved',
    badgeClass: 'bg-emerald-950/60 text-emerald-300 border-emerald-800/40',
    dotClass: 'bg-emerald-400',
  },
};

export function getSectionStatusConfig(status: SectionApprovalStatus | string): SectionStatusConfig {
  const normalized = status as SectionApprovalStatus;
  return (
    SECTION_STATUS_CONFIG[normalized] || {
      label: status,
      badgeClass: 'bg-zinc-800 text-zinc-300 border-zinc-700',
      dotClass: 'bg-zinc-400',
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
    badgeClass: 'bg-zinc-800/80 text-zinc-400 border-zinc-700/50',
    description: 'Default template structure',
  },
  ai_generated: {
    label: 'AI Generated',
    badgeClass: 'bg-violet-950/70 text-violet-300 border-violet-800/40',
    description: 'Generated by Claude from intake submission',
  },
  human_edited: {
    label: 'Human Edited',
    badgeClass: 'bg-blue-950/70 text-blue-300 border-blue-800/40',
    description: 'Manually edited by salesperson',
  },
  human_edited_after_generation: {
    label: 'Edited After AI',
    badgeClass: 'bg-cyan-950/70 text-cyan-300 border-cyan-800/40',
    description: 'AI-generated then customized by salesperson',
  },
};

export function getContentOriginConfig(origin: ContentOrigin | string): ContentOriginConfig {
  const normalized = origin as ContentOrigin;
  return (
    CONTENT_ORIGIN_CONFIG[normalized] || {
      label: origin.replace(/_/g, ' '),
      badgeClass: 'bg-zinc-800 text-zinc-400 border-zinc-700',
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

// Only these sections have any AI-generated content at all (see
// backend/app/domain/generation.py GENERATED_SECTION_KEYS) — Timeline,
// Pricing, and Next Steps are pinned facts/boilerplate with nothing for
// Claude to regenerate. Introduction is generated (not pinned) specifically
// so the client's raw intake wording gets paraphrased/cleaned up rather than
// reaching the client verbatim — see docs/edge-cases.md.
export const GENERATED_SECTION_KEYS: SectionKey[] = [
  'introduction',
  'proposed_solution',
  'deliverables',
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
