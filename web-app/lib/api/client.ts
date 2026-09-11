import {
  ProposalDetailResponse,
  ProposalSummaryResponse,
  ClaudeCallLogResponse,
  DocumentArtifactResponse,
  DeliveryDraftResponse,
  DeliveryRecordResponse,
  ActivityLogEntryResponse,
  SalespersonAccountResponse,
  SalespersonProfileResponse,
  ApiError,
} from './types';
import { getClientAuthToken } from '../auth/session';

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api/v1';

interface RequestOptions extends RequestInit {
  token?: string;
}

async function request<T>(
  endpoint: string,
  options: RequestOptions = {}
): Promise<T> {
  const { token, headers = {}, ...rest } = options;

  // Server Components must pass `token` explicitly (see
  // lib/auth/serverSession.ts::getServerAuthToken()) — this no longer
  // guesses DEV_TOKEN when window is undefined. That guess used to send a
  // fake token on every server-rendered request regardless of environment,
  // which production's real backend correctly rejected as a malformed JWT
  // ("Invalid or expired token: Not enough segments" — a confusing error
  // for what was actually just a missing token). Falling through to no
  // token at all here instead gets the clear "Authentication required" 401.
  const authToken =
    token || (typeof window !== 'undefined' ? getClientAuthToken() : undefined);

  const requestHeaders: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'application/json',
    ...(headers as Record<string, string>),
  };

  if (authToken) {
    requestHeaders['Authorization'] = `Bearer ${authToken}`;
  }

  const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  const url = `${API_BASE_URL}${cleanEndpoint}`;

  let response: Response;

  try {
    response = await fetch(url, {
      headers: requestHeaders,
      ...rest,
    });
  } catch (networkError: any) {
    throw new ApiError(
      0,
      `Network connection error: Failed to connect to ${API_BASE_URL}. Ensure the backend service is running.`,
      'NETWORK_ERROR',
      networkError?.message
    );
  }

  if (!response.ok) {
    let errorDetail: any;

    try {
      errorDetail = await response.json();
    } catch {
      errorDetail = await response.text();
    }

    const message =
      typeof errorDetail === 'object' &&
      errorDetail !== null &&
      'detail' in errorDetail
        ? typeof errorDetail.detail === 'string'
          ? errorDetail.detail
          : JSON.stringify(errorDetail.detail)
        : `Request failed with status ${response.status}`;

    throw new ApiError(
      response.status,
      message,
      `HTTP_${response.status}`,
      errorDetail
    );
  }

  if (response.status === 204) {
    return {} as T;
  }

  return response.json() as Promise<T>;
}

export async function listProposals(
  skip: number = 0,
  limit: number = 50,
  token?: string
): Promise<ProposalSummaryResponse[]> {
  return request<ProposalSummaryResponse[]>(
    `/proposals?skip=${skip}&limit=${limit}`,
    {
      method: 'GET',
      token,
      cache: 'no-store',
    }
  );
}

export async function getProposal(
  id: string,
  token?: string
): Promise<ProposalDetailResponse> {
  return request<ProposalDetailResponse>(`/proposals/${id}`, {
    method: 'GET',
    token,
    cache: 'no-store',
  });
}

export async function updateSectionContent(
  proposalId: string,
  sectionKey: string,
  content: string,
  token?: string
): Promise<ProposalDetailResponse> {
  return request<ProposalDetailResponse>(
    `/proposals/${proposalId}/sections/${sectionKey}`,
    {
      method: 'PATCH',
      token,
      body: JSON.stringify({ content }),
    }
  );
}

export async function regenerateSection(
  proposalId: string,
  sectionKey: string,
  instruction: string,
  token?: string
): Promise<ProposalDetailResponse> {
  return request<ProposalDetailResponse>(
    `/proposals/${proposalId}/sections/${sectionKey}/regenerate`,
    {
      method: 'POST',
      token,
      body: JSON.stringify({ instruction }),
    }
  );
}

export async function generateProposal(
  proposalId: string,
  token?: string
): Promise<ProposalDetailResponse> {
  return request<ProposalDetailResponse>(`/proposals/${proposalId}/generate`, {
    method: 'POST',
    token,
  });
}

export async function approveSection(
  proposalId: string,
  sectionKey: string,
  token?: string
): Promise<ProposalDetailResponse> {
  return request<ProposalDetailResponse>(
    `/proposals/${proposalId}/sections/${sectionKey}/approve`,
    { method: 'POST', token }
  );
}

export async function submitForApproval(
  proposalId: string,
  token?: string
): Promise<ProposalDetailResponse> {
  return request<ProposalDetailResponse>(
    `/proposals/${proposalId}/submit-for-approval`,
    { method: 'POST', token }
  );
}

export async function approveProposal(
  proposalId: string,
  token?: string
): Promise<ProposalDetailResponse> {
  return request<ProposalDetailResponse>(`/proposals/${proposalId}/approve`, {
    method: 'POST',
    token,
  });
}

export async function requestChanges(
  proposalId: string,
  reason?: string,
  token?: string
): Promise<ProposalDetailResponse> {
  return request<ProposalDetailResponse>(
    `/proposals/${proposalId}/request-changes`,
    {
      method: 'POST',
      token,
      body: JSON.stringify({ reason: reason || null }),
    }
  );
}

export async function rejectProposal(
  proposalId: string,
  reason?: string,
  token?: string
): Promise<ProposalDetailResponse> {
  return request<ProposalDetailResponse>(`/proposals/${proposalId}/reject`, {
    method: 'POST',
    token,
    body: JSON.stringify({ reason: reason || null }),
  });
}

export async function getClaudeCalls(
  proposalId: string,
  token?: string
): Promise<ClaudeCallLogResponse[]> {
  return request<ClaudeCallLogResponse[]>(
    `/proposals/${proposalId}/claude-calls`,
    { method: 'GET', token, cache: 'no-store' }
  );
}

export async function generateDocument(
  proposalId: string,
  token?: string
): Promise<ProposalDetailResponse> {
  return request<ProposalDetailResponse>(
    `/proposals/${proposalId}/generate-document`,
    { method: 'POST', token }
  );
}

export async function getDocument(
  proposalId: string,
  token?: string
): Promise<DocumentArtifactResponse> {
  return request<DocumentArtifactResponse>(`/proposals/${proposalId}/document`, {
    method: 'GET',
    token,
    cache: 'no-store',
  });
}

export async function getDeliveryDraft(
  proposalId: string,
  token?: string
): Promise<DeliveryDraftResponse> {
  return request<DeliveryDraftResponse>(`/proposals/${proposalId}/delivery-draft`, {
    method: 'GET',
    token,
    cache: 'no-store',
  });
}

export async function deliverProposal(
  proposalId: string,
  token?: string
): Promise<ProposalDetailResponse> {
  return request<ProposalDetailResponse>(`/proposals/${proposalId}/deliver`, {
    method: 'POST',
    token,
  });
}

export async function getDeliveryRecords(
  proposalId: string,
  token?: string
): Promise<DeliveryRecordResponse[]> {
  return request<DeliveryRecordResponse[]>(`/proposals/${proposalId}/delivery`, {
    method: 'GET',
    token,
    cache: 'no-store',
  });
}

export async function getActivityLog(
  proposalId: string,
  token?: string
): Promise<ActivityLogEntryResponse[]> {
  return request<ActivityLogEntryResponse[]>(`/proposals/${proposalId}/activity`, {
    method: 'GET',
    token,
    cache: 'no-store',
  });
}

export async function getMe(token?: string): Promise<SalespersonProfileResponse> {
  return request<SalespersonProfileResponse>('/auth/me', {
    method: 'GET',
    token,
    cache: 'no-store',
  });
}

export async function updateMyDisplayName(
  displayName: string,
  token?: string
): Promise<SalespersonProfileResponse> {
  return request<SalespersonProfileResponse>('/auth/me', {
    method: 'PATCH',
    token,
    body: JSON.stringify({ display_name: displayName }),
  });
}

export async function listAccounts(token?: string): Promise<SalespersonAccountResponse[]> {
  return request<SalespersonAccountResponse[]>('/auth/accounts', {
    method: 'GET',
    token,
    cache: 'no-store',
  });
}

export async function approveAccount(
  accountId: string,
  token?: string
): Promise<SalespersonAccountResponse> {
  return request<SalespersonAccountResponse>(`/auth/pending/${accountId}/approve`, {
    method: 'POST',
    token,
  });
}

export async function rejectAccount(
  accountId: string,
  token?: string
): Promise<SalespersonAccountResponse> {
  return request<SalespersonAccountResponse>(`/auth/pending/${accountId}/reject`, {
    method: 'POST',
    token,
  });
}

export async function claimProposal(
  proposalId: string,
  token?: string
): Promise<ProposalDetailResponse> {
  return request<ProposalDetailResponse>(`/proposals/${proposalId}/claim`, {
    method: 'POST',
    token,
  });
}

export async function unclaimProposal(
  proposalId: string,
  token?: string
): Promise<ProposalDetailResponse> {
  return request<ProposalDetailResponse>(`/proposals/${proposalId}/unclaim`, {
    method: 'POST',
    token,
  });
}

export async function transferProposal(
  proposalId: string,
  targetAccountId: string,
  token?: string
): Promise<ProposalDetailResponse> {
  return request<ProposalDetailResponse>(`/proposals/${proposalId}/transfer`, {
    method: 'POST',
    token,
    body: JSON.stringify({ target_account_id: targetAccountId }),
  });
}

export const api = {
  listProposals,
  getProposal,
  updateSectionContent,
  regenerateSection,
  generateProposal,
  approveSection,
  submitForApproval,
  approveProposal,
  requestChanges,
  rejectProposal,
  getClaudeCalls,
  generateDocument,
  getDocument,
  getDeliveryDraft,
  deliverProposal,
  getDeliveryRecords,
  getActivityLog,
  getMe,
  updateMyDisplayName,
  listAccounts,
  approveAccount,
  rejectAccount,
  claimProposal,
  unclaimProposal,
  transferProposal,
};