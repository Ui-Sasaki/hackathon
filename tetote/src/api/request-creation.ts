import { apiClient, type ApiClient } from "./client";
import { ApiError } from "./errors";

export type CreateRequestInput = {
  title: string;
  description: string;
  category: string;
  scheduledAt: string;
  estimatedMinutes: number;
  requiredHelpers: number;
  areaCode: string;
  riskLevel: "low" | "medium";
  confirmed: true;
};

export type CreatedRequest = {
  id: string;
  requesterId: string;
  title: string;
  description: string;
  category: string;
  riskLevel: "low" | "medium" | "high" | "prohibited";
  areaCode: string;
  areaLabel: string;
  distanceKm: number | null;
  acceptedHelpers: number;
  scheduledAt: string;
  estimatedMinutes: number;
  requiredHelpers: number;
  status: string;
  version: number;
  warnings: string[];
  createdAt: string;
  updatedAt: string;
};

export type RequestCreationAttempt = {
  input: CreateRequestInput;
  idempotencyKey: string;
};

export type RequestCreationState =
  | { status: "created"; attempt: RequestCreationAttempt; request: CreatedRequest; error: null }
  | { status: "conflict" | "validation_error" | "error"; attempt: RequestCreationAttempt; request: null; error: unknown };

export function beginRequestCreation(
  input: CreateRequestInput,
  createIdempotencyKey: () => string = () => globalThis.crypto.randomUUID(),
): RequestCreationAttempt {
  return { input, idempotencyKey: createIdempotencyKey() };
}

export async function submitRequestCreation(
  attempt: RequestCreationAttempt,
  client: ApiClient = apiClient,
): Promise<RequestCreationState> {
  try {
    const request = await client.post<CreatedRequest>("/requests", attempt.input, {
      headers: { "Idempotency-Key": attempt.idempotencyKey },
    });
    return { status: "created", attempt, request, error: null };
  } catch (error) {
    if (error instanceof ApiError && error.status === 409) {
      return { status: "conflict", attempt, request: null, error };
    }
    if (error instanceof ApiError && error.status === 422) {
      return { status: "validation_error", attempt, request: null, error };
    }
    return { status: "error", attempt, request: null, error };
  }
}
