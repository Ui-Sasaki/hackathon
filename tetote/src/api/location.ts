import { apiClient, ApiClient } from "./client";

export type LocationFailureReason = "denied" | "timeout" | "unsupported" | "unavailable";

type LocationResolveInput =
  | {
      consentGranted: true;
      latitude: number;
      longitude: number;
    }
  | {
      consentGranted: boolean;
      failureReason: LocationFailureReason;
    };

export type ApproximateLocation = {
  areaCode: string;
  areaLabel: string;
  source: "current_location" | "selected_region" | "registered_region" | "default_region";
  fallbackUsed: boolean;
};

export type ApproximateLocationState =
  | { status: "resolved"; location: ApproximateLocation; error: null }
  | { status: "error"; location: null; error: unknown };

type GeolocationLike = Pick<Geolocation, "getCurrentPosition">;

export type ResolveApproximateLocationOptions = {
  consentGranted: boolean;
  client?: ApiClient;
  geolocation?: GeolocationLike | null;
};

function failureReason(error: GeolocationPositionError): LocationFailureReason {
  if (error.code === error.PERMISSION_DENIED) return "denied";
  if (error.code === error.TIMEOUT) return "timeout";
  return "unavailable";
}

function currentPosition(geolocation: GeolocationLike): Promise<GeolocationPosition> {
  return new Promise((resolve, reject) => {
    geolocation.getCurrentPosition(resolve, reject, {
      enableHighAccuracy: false,
      timeout: 10_000,
      maximumAge: 60_000,
    });
  });
}

async function locationInput(
  consentGranted: boolean,
  geolocation: GeolocationLike | null,
): Promise<LocationResolveInput> {
  if (!consentGranted) return { consentGranted: false, failureReason: "denied" };
  if (!geolocation) return { consentGranted: true, failureReason: "unsupported" };

  try {
    const position = await currentPosition(geolocation);
    return {
      consentGranted: true,
      latitude: position.coords.latitude,
      longitude: position.coords.longitude,
    };
  } catch (error) {
    return {
      consentGranted: true,
      failureReason:
        typeof error === "object" && error !== null && "code" in error
          ? failureReason(error as GeolocationPositionError)
          : "unavailable",
    };
  }
}

export async function resolveApproximateLocation({
  consentGranted,
  client = apiClient,
  geolocation = typeof navigator === "undefined" ? null : navigator.geolocation,
}: ResolveApproximateLocationOptions): Promise<ApproximateLocationState> {
  const body = await locationInput(consentGranted, geolocation);
  try {
    const location = await client.post<ApproximateLocation>("/locations/resolve", body);
    return { status: "resolved", location, error: null };
  } catch (error) {
    return { status: "error", location: null, error };
  }
}
