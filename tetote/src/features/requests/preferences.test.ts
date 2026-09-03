import { describe, expect, it, vi } from "vitest";
import type { ApiClient } from "../../api/client";
import {
  dismissPublicRequest,
  listSavedPublicRequests,
  removeSavedPublicRequest,
  restoreDismissedPublicRequest,
  savePublicRequest,
} from "./preferences";

type MockClient = ApiClient & {
  get: ReturnType<typeof vi.fn>;
  post: ReturnType<typeof vi.fn>;
  delete: ReturnType<typeof vi.fn>;
};

function clientWith(): MockClient {
  return { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn(), request: vi.fn() } as unknown as MockClient;
}

describe("request preference API", () => {
  it("uses the server endpoints for save and dismiss operations", async () => {
    const client = clientWith();
    await savePublicRequest("request/1", client);
    await removeSavedPublicRequest("request/1", client);
    await dismissPublicRequest("request/1", client);
    await restoreDismissedPublicRequest("request/1", client);

    expect(client.post).toHaveBeenNthCalledWith(1, "/saved-requests/request%2F1");
    expect(client.delete).toHaveBeenNthCalledWith(1, "/saved-requests/request%2F1");
    expect(client.post).toHaveBeenNthCalledWith(2, "/requests/request%2F1/dismiss");
    expect(client.delete).toHaveBeenNthCalledWith(2, "/requests/request%2F1/dismiss");
  });

  it("returns saved request cards from the server", async () => {
    const client = clientWith();
    client.get.mockResolvedValue({ items: [{ id: "r1" }, { id: "r2" }] });
    await expect(listSavedPublicRequests(client)).resolves.toEqual([{ id: "r1" }, { id: "r2" }]);
    expect(client.get).toHaveBeenCalledWith("/saved-requests");
  });
});
