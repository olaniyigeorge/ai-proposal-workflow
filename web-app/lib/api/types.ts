export type ProposalStatus =
  | 'DRAFT'
  | 'GENERATING'
  | 'GENERATION_FAILED'
  | 'IN_REVIEW'
  | 'PENDING_APPROVAL'
  | 'APPROVED'
  | 'DOCUMENT_GENERATING'
  | 'DOCUMENT_GENERATION_FAILED'
  | 'DOCUMENT_READY'
  | 'DELIVERING'
  | 'DELIVERY_FAILED'
  | 'DELIVERED'
  | 'REJECTED'
  | 'CLOSED';

export type SectionKey =
  | 'introduction'
  | 'proposed_solution'
  | 'deliverables'
  | 'timeline'
  | 'pricing'
  | 'next_steps';

export type ContentOrigin =
  | 'template_default'
  | 'ai_generated'
  | 'human_edited'
  | 'human_edited_after_generation';

export type SectionApprovalStatus = 'pending' | 'approved';

export interface ProposalSectionResponse {
  id: string;
  section_key: SectionKey | string;
  title: string;
  order_index: number;
  content: string;
  content_origin: ContentOrigin | string;
  approval_status: SectionApprovalStatus | string;
  regeneration_count: number;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface ProposalSummaryResponse {
  id: string;
  status: ProposalStatus | string;
  client_name: string;
  client_email: string;
  company_name: string;
  salesperson_name: string;
  created_at: string;
  updated_at: string;
}

export interface ProposalDetailResponse {
  id: string;
  status: ProposalStatus | string;
  client_name: string;
  client_email: string;
  company_name: string;
  salesperson_name: string;
  date_of_call: string;
  client_needs_summary: string;
  project_scope: string;
  goals_and_objectives: string;
  recommended_services: string;
  proposed_timeline: string;
  estimated_pricing: string;
  created_at: string;
  updated_at: string;
  sections: ProposalSectionResponse[];
}

export interface ApiErrorDetail {
  code?: string;
  message: string;
  detail?: string | Record<string, unknown>;
  status?: number;
}

export class ApiError extends Error {
  status: number;
  code?: string;
  detail?: string | Record<string, unknown>;

  constructor(status: number, message: string, code?: string, detail?: string | Record<string, unknown>) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.detail = detail;
  }
}
