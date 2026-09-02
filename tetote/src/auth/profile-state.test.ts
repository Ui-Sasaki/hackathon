import { describe, expect, it } from "vitest";
import { AuthExpiredError, ProfileValidationError } from "./client";
import { profileErrorKind, profileErrorMessage } from "./profile-state";

describe("profile request errors", () => {
  it("classifies authentication and validation errors", () => {
    expect(profileErrorKind(new AuthExpiredError())).toBe("unauthorized");
    expect(profileErrorKind(new ProfileValidationError())).toBe("validation");
  });

  it("treats transport failures as network errors", () => {
    expect(profileErrorKind(new TypeError("Failed to fetch"))).toBe("network");
    expect(profileErrorMessage("network")).toContain("通信");
  });
});
