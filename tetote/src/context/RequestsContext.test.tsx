import TestRenderer, { act } from "react-test-renderer";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { RequestsProvider } from "./RequestsContext";

const mocks = vi.hoisted(() => ({
  authStatus: "loading" as "loading" | "authenticated" | "unauthenticated" | "error",
  listPublicRequests: vi.fn(),
  listSavedPublicRequests: vi.fn(),
}));

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({ status: mocks.authStatus }),
}));
vi.mock("../features/requests/client", () => ({
  listPublicRequests: mocks.listPublicRequests,
  requestListErrorMessage: vi.fn(() => "error"),
  toRequestCard: vi.fn((item) => item),
}));
vi.mock("../features/requests/preferences", () => ({
  dismissPublicRequest: vi.fn(),
  listSavedPublicRequests: mocks.listSavedPublicRequests,
  removeSavedPublicRequest: vi.fn(),
  savePublicRequest: vi.fn(),
}));

beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  vi.clearAllMocks();
  mocks.authStatus = "loading";
  mocks.listPublicRequests.mockResolvedValue({ items: [] });
  mocks.listSavedPublicRequests.mockResolvedValue([]);
});

describe("RequestsProvider authentication boundary", () => {
  it("does not request protected data while authentication is loading", async () => {
    await act(async () => {
      TestRenderer.create(<RequestsProvider>{null}</RequestsProvider>);
    });

    expect(mocks.listPublicRequests).not.toHaveBeenCalled();
    expect(mocks.listSavedPublicRequests).not.toHaveBeenCalled();
  });

  it("requests protected data after authentication succeeds", async () => {
    mocks.authStatus = "authenticated";

    await act(async () => {
      TestRenderer.create(<RequestsProvider>{null}</RequestsProvider>);
    });

    expect(mocks.listPublicRequests).toHaveBeenCalledOnce();
    expect(mocks.listSavedPublicRequests).toHaveBeenCalledOnce();
  });

  it("starts requesting when authentication finishes", async () => {
    let renderer!: TestRenderer.ReactTestRenderer;
    await act(async () => {
      renderer = TestRenderer.create(<RequestsProvider>{null}</RequestsProvider>);
    });

    mocks.authStatus = "authenticated";
    await act(async () => {
      renderer.update(<RequestsProvider>{null}</RequestsProvider>);
    });

    expect(mocks.listPublicRequests).toHaveBeenCalledOnce();
    expect(mocks.listSavedPublicRequests).toHaveBeenCalledOnce();
  });
});
