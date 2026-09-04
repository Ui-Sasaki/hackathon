import { apiClient, type ApiClient } from "./client";
import type { CreatedRequest } from "./request-creation";

export type RequestListFilters = {
  category?: string;
  areaCode?: string;
};

export type RequestListOrigin = {
  areaCode: string;
  source: "current_location" | "selected_region" | "registered_region" | "default_region";
};

type RequestListResponse = {
  items: CreatedRequest[];
  nextCursor: string | null;
  origin: RequestListOrigin;
};

export type RequestListState =
  | { status: "loading"; filters: RequestListFilters; items: []; nextCursor: null; origin: null; error: null }
  | { status: "ready"; filters: RequestListFilters; items: CreatedRequest[]; nextCursor: string | null; origin: RequestListOrigin; error: null }
  | { status: "empty"; filters: RequestListFilters; items: []; nextCursor: null; origin: RequestListOrigin; error: null }
  | { status: "error"; filters: RequestListFilters; items: []; nextCursor: null; origin: null; error: unknown };

export function requestListLoadingState(filters: RequestListFilters = {}): RequestListState {
  return { status: "loading", filters, items: [], nextCursor: null, origin: null, error: null };
}

function requestListPath(filters: RequestListFilters): string {
  const query = new URLSearchParams();
  if (filters.category) query.set("category", filters.category);
  if (filters.areaCode) query.set("areaCode", filters.areaCode);
  const encoded = query.toString();
  return encoded ? `/requests?${encoded}` : "/requests";
}

export async function listRequests(
  filters: RequestListFilters = {},
  client: ApiClient = apiClient,
): Promise<RequestListState> {
  try {
    const response = await client.get<RequestListResponse>(requestListPath(filters));
    if (response.items.length === 0) {
      return {
        status: "empty",
        filters,
        items: [],
        nextCursor: null,
        origin: response.origin,
        error: null,
      };
    }
    return { status: "ready", filters, ...response, error: null };
  } catch (error) {
    return { status: "error", filters, items: [], nextCursor: null, origin: null, error };
  }
}
