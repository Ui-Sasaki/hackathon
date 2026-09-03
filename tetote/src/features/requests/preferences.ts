import { apiClient, type ApiClient } from "../../api/client";
import type { PublicRequest } from "./client";

export async function savePublicRequest(
  requestId: string,
  client: ApiClient = apiClient,
): Promise<void> {
  await client.post<void>(`/saved-requests/${encodeURIComponent(requestId)}`);
}

export async function removeSavedPublicRequest(
  requestId: string,
  client: ApiClient = apiClient,
): Promise<void> {
  await client.delete<void>(`/saved-requests/${encodeURIComponent(requestId)}`);
}

export async function dismissPublicRequest(
  requestId: string,
  client: ApiClient = apiClient,
): Promise<void> {
  await client.post<void>(`/requests/${encodeURIComponent(requestId)}/dismiss`);
}

export async function restoreDismissedPublicRequest(
  requestId: string,
  client: ApiClient = apiClient,
): Promise<void> {
  await client.delete<void>(`/requests/${encodeURIComponent(requestId)}/dismiss`);
}

export type SavedRequestsResponse = {
  items: PublicRequest[];
};

export async function listSavedPublicRequests(
  client: ApiClient = apiClient,
): Promise<PublicRequest[]> {
  const response = await client.get<SavedRequestsResponse>("/saved-requests");
  return response.items;
}
