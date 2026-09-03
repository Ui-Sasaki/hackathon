import { apiClient, type ApiClient } from "./client";
import { ApiError, ApiNetworkError } from "./errors";
import type { MaskingPreviewState } from "./request-masking";

export type StructuredRequestDraft = {
  title: string;
  description: string;
  category: string;
  scheduledAt: string | null;
  estimatedMinutes: number | null;
  approximateArea: string | null;
  requiredHelpers: number | null;
  itemsToBring: string[];
  riskLevel: "low" | "medium" | "high" | "prohibited";
  riskCandidates: string[];
  missingFields: string[];
  warnings: string[];
};

type StructuredRequestResponse = StructuredRequestDraft & {
  masking: {
    detections: { type: string; placeholder: string; count: number }[];
    ruleVersion: string;
    confirmed: boolean;
  };
  status: "draft";
  requiresConfirmation: true;
  autoPublished: false;
  additionalQuestion: string | null;
  metadata: {
    modelName: string;
    promptVersion: string;
    processedAt: string;
  };
};

export type RequestStructuringState =
  | { status: "idle"; originalText: string; draft: null; additionalQuestion: null; error: null }
  | { status: "draft"; originalText: string; draft: StructuredRequestDraft; additionalQuestion: string | null; error: null }
  | { status: "manual"; originalText: string; draft: StructuredRequestDraft; additionalQuestion: null; error: unknown }
  | { status: "error"; originalText: string; draft: null; additionalQuestion: null; error: unknown };

function fallbackDraft(text: string): StructuredRequestDraft {
  return {
    title: "",
    description: text,
    category: "",
    scheduledAt: null,
    estimatedMinutes: null,
    approximateArea: null,
    requiredHelpers: null,
    itemsToBring: [],
    riskLevel: "low",
    riskCandidates: [],
    missingFields: [],
    warnings: [],
  };
}

function canUseManualFallback(error: unknown): boolean {
  return error instanceof ApiNetworkError
    || (error instanceof ApiError && (error.status === 502 || error.status === 503));
}

export async function structureConfirmedRequest(
  maskingState: MaskingPreviewState | null,
  client: ApiClient = apiClient,
): Promise<RequestStructuringState> {
  if (maskingState?.status !== "confirmed") {
    return {
      status: "error",
      originalText: "",
      draft: null,
      additionalQuestion: null,
      error: new Error("MASKING_CONFIRMATION_REQUIRED"),
    };
  }

  const originalText = maskingState.preview.maskedText;
  try {
    const response = await client.post<StructuredRequestResponse>("/requests/structure", {
      text: originalText,
      maskingConfirmed: true,
    });
    const {
      additionalQuestion,
      masking: _masking,
      metadata: _metadata,
      status: _status,
      requiresConfirmation: _requiresConfirmation,
      autoPublished: _autoPublished,
      ...draft
    } = response;
    return { status: "draft", originalText, draft, additionalQuestion, error: null };
  } catch (error) {
    if (canUseManualFallback(error)) {
      return {
        status: "manual",
        originalText,
        draft: fallbackDraft(originalText),
        additionalQuestion: null,
        error,
      };
    }
    return { status: "error", originalText, draft: null, additionalQuestion: null, error };
  }
}

export function updateStructuredDraft(
  state: RequestStructuringState,
  changes: Partial<StructuredRequestDraft>,
): RequestStructuringState {
  if ((state.status !== "draft" && state.status !== "manual") || !state.draft) return state;
  return { ...state, draft: { ...state.draft, ...changes } };
}
