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

export interface RegenerationLogEntry {
  instruction: string;
  attempted_at: string;
  outcome: 'succeeded' | 'failed' | string;
  resulting_version?: number | null;
  error?: string | null;
}

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
  regeneration_log: RegenerationLogEntry[];
  created_at: string;
  updated_at: string;
}

export interface ProposalSummaryResponse {
  id: string;
  status: ProposalStatus | string;
  client_name: string;
  client_email: string;
  company_name: string;
  salesperson_name: string | null;
  salesperson_account_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProposalDetailResponse {
  id: string;
  status: ProposalStatus | string;
  client_name: string;
  client_email: string;
  company_name: string;
  salesperson_name: string | null;
  salesperson_account_id: string | null;
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

export interface ClaudeCallLogResponse {
  id: string;
  section_key: string;
  call_type: 'full_generation' | 'regeneration' | string;
  status: 'succeeded' | 'failed' | string;
  instruction?: string | null;
  model?: string | null;
  system_prompt: string;
  user_prompt: string;
  response_text?: string | null;
  input_tokens?: number | null;
  output_tokens?: number | null;
  stop_reason?: string | null;
  duration_ms?: number | null;
  error_message?: string | null;
  created_at: string;
}

export interface DocumentArtifactResponse {
  id: string;
  file_size_bytes: number;
  page_count: number;
  created_at: string;
  download_url: string;
}

export interface DeliveryDraftResponse {
  subject: string;
  body: string;
  recipient_email: string;
}

export interface DeliveryRecordResponse {
  id: string;
  status: 'sent' | 'failed' | 'bounced' | string;
  recipient_email: string;
  subject: string;
  sent_at?: string | null;
  error_message?: string | null;
  created_at: string;
}

export type ActivityEventType =
  | 'created'
  | 'generated'
  | 'generation_failed'
  | 'section_edited'
  | 'section_regenerated'
  | 'regeneration_failed'
  | 'section_approved'
  | 'submitted_for_approval'
  | 'proposal_approved'
  | 'changes_requested'
  | 'rejected'
  | 'document_generated'
  | 'document_generation_failed'
  | 'delivered'
  | 'delivery_failed'
  | 'proposal_claimed'
  | 'proposal_unclaimed'
  | 'proposal_transferred';

export interface ActivityLogEntryResponse {
  id: string;
  proposal_id: string;
  event_type: ActivityEventType | string;
  description: string;
  actor?: string | null;
  event_metadata: Record<string, unknown>;
  created_at: string;
}

export type SalespersonAccountStatus = 'pending' | 'approved' | 'rejected';

export interface SalespersonAccountResponse {
  id: string;
  email: string;
  display_name: string | null;
  status: SalespersonAccountStatus | string;
  approved_by?: string | null;
  approved_at?: string | null;
  created_at: string;
}

export interface SalespersonProfileResponse {
  user_id: string;
  email: string;
  role: string;
  display_name: string | null;
  account_id: string | null;
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
