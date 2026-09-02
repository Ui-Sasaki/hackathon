import { describe, expect, it, vi } from "vitest";

import { ApiClient } from "./client";
import { ApiError } from "./errors";
import { resolveApproximateLocation } from "./location";

const jsonResponse = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

function geolocationSuccess(latitude: number, longitude: number): Geolocation {
  return {
    getCurrentPosition: vi.fn((success: PositionCallback) =>
      success({ coords: { latitude, longitude } } as GeolocationPosition),
    ),
  } as unknown as Geolocation;
}

function geolocationFailure(code: number): Geolocation {
  return {
    getCurrentPosition: vi.fn((_success: PositionCallback, failure?: PositionErrorCallback | null) =>
      failure?.({ code, PERMISSION_DENIED: 1, POSITION_UNAVAILABLE: 2, TIMEOUT: 3 } as GeolocationPositionError),
    ),
  } as unknown as Geolocation;
}

describe("TODO 08: approximate location API", () => {
  it("sends consented coordinates and keeps only the approximate area in state", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(200, {
        areaCode: "AREA-002",
        areaLabel: "札幌市",
        source: "current_location",
        fallbackUsed: false,
      }),
    );
    const client = new ApiClient({ baseUrl: "https://api.example.test", fetch: fetchMock });

    const state = await resolveApproximateLocation({
      consentGranted: true,
      client,
      geolocation: geolocationSuccess(43.082, 141.35),
    });

    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      consentGranted: true,
      latitude: 43.082,
      longitude: 141.35,
    });
    expect(state).toEqual({
      status: "resolved",
      location: {
        areaCode: "AREA-002",
        areaLabel: "札幌市",
        source: "current_location",
        fallbackUsed: false,
      },
      error: null,
    });
    expect(JSON.stringify(state)).not.toContain("43.082");
    expect(JSON.stringify(state)).not.toContain("141.35");
  });

  it("uses the registered region when location consent is refused", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(200, {
        areaCode: "AREA-001",
        areaLabel: "東京都",
        source: "registered_region",
        fallbackUsed: true,
      }),
    );
    const client = new ApiClient({ baseUrl: "https://api.example.test", fetch: fetchMock });

    const state = await resolveApproximateLocation({
      consentGranted: false,
      client,
      geolocation: geolocationSuccess(43.082, 141.35),
    });

    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      consentGranted: false,
      failureReason: "denied",
    });
    expect(state).toMatchObject({
      status: "resolved",
      location: { areaCode: "AREA-001", source: "registered_region", fallbackUsed: true },
    });
  });

  it("falls back to the registered region when consented location acquisition fails", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(200, {
        areaCode: "AREA-001",
        areaLabel: "東京都",
        source: "registered_region",
        fallbackUsed: true,
      }),
    );
    const client = new ApiClient({ baseUrl: "https://api.example.test", fetch: fetchMock });

    const state = await resolveApproximateLocation({
      consentGranted: true,
      client,
      geolocation: geolocationFailure(3),
    });

    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      consentGranted: true,
      failureReason: "timeout",
    });
    expect(state).toMatchObject({
      status: "resolved",
      location: { source: "registered_region", fallbackUsed: true },
    });
  });

  it("reflects the API error when neither current nor registered region is available", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(422, {
        error: {
          code: "REGION_SELECTION_REQUIRED",
          message: "地域を選択してください",
          details: {},
          requestId: "trace_location",
        },
      }),
    );
    const client = new ApiClient({ baseUrl: "https://api.example.test", fetch: fetchMock });

    const state = await resolveApproximateLocation({
      consentGranted: true,
      client,
      geolocation: null,
    });

    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      consentGranted: true,
      failureReason: "unsupported",
    });
    expect(state.status).toBe("error");
    if (state.status === "error") {
      expect(state.error).toBeInstanceOf(ApiError);
      expect(state.error).toMatchObject({ status: 422, code: "REGION_SELECTION_REQUIRED" });
    }
  });
});
