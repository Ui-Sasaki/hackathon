import { apiClient, ApiClient } from "./client";

export type MaskingDetection = {
  type: string;
  placeholder: string;
  count: number;
};

export type MaskingPreview = {
  maskedText: string;
  detections: MaskingDetection[];
  hasDetections: boolean;
  ruleVersion: string;
  status: "masking_confirmation_required";
  requiresMaskingConfirmation: true;
  message: string;
};

export type MaskingPreviewState =
  | { status: "ready"; preview: MaskingPreview; confirmed: false; error: null }
  | { status: "confirmed"; preview: MaskingPreview; confirmed: true; error: null }
  | { status: "error"; preview: null; confirmed: false; error: unknown };

export async function previewRequestMasking(
  text: string,
  client: ApiClient = apiClient,
): Promise<MaskingPreviewState> {
  try {
    const preview = await client.post<MaskingPreview>("/requests/masking-preview", { text });
    return { status: "ready", preview, confirmed: false, error: null };
  } catch (error) {
    return { status: "error", preview: null, confirmed: false, error };
  }
}

export function confirmMaskingPreview(
  state: MaskingPreviewState,
): MaskingPreviewState {
  if (state.status !== "ready") return state;
  return { ...state, status: "confirmed", confirmed: true };
}

export function canProceedAfterMasking(state: MaskingPreviewState | null): boolean {
  return state?.status === "confirmed";
}
