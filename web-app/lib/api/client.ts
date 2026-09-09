import {
  ProposalDetailResponse,
  ProposalSummaryResponse,
  ApiError,
} from './types';
import { DEV_TOKEN, getClientAuthToken } from '../auth/session';

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

  const authToken =
    token ||
    (typeof window !== 'undefined' ? getClientAuthToken() : DEV_TOKEN);

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

export const api = {
  listProposals,
  getProposal,
};