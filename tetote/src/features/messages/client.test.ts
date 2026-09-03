import { describe, expect, it, vi } from "vitest";

import { ApiClient } from "../../api/client";
import {
  listMessages,
  mergeMessages,
  sendMessage,
  startMessagePolling,
  type Message,
} from "./client";

const message = (id: string, sentAt: string): Message => ({
  id,
  matchId: "match-1",
  senderId: "user-1",
  body: id,
  sentAt,
  readAt: null,
  moderationStatus: "allowed",
});

const response = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

describe("message API polling", () => {
  it("loads messages for the encoded match id", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      response({ items: [message("message-1", "2026-09-03T10:00:00Z")], nextCursor: null }),
    );
    const client = new ApiClient({ baseUrl: "https://api.example.test", fetch: fetchMock });

    await expect(listMessages("match/1", client)).resolves.toMatchObject({
      items: [{ id: "message-1" }],
    });
    expect(fetchMock.mock.calls[0][0]).toBe(
      "https://api.example.test/matches/match%2F1/messages",
    );
  });

  it("sends only the message body and reuses an in-flight duplicate send", async () => {
    let resolveFetch!: (value: Response) => void;
    const fetchMock = vi.fn().mockReturnValue(
      new Promise<Response>((resolve) => {
        resolveFetch = resolve;
      }),
    );
    const client = new ApiClient({ baseUrl: "https://api.example.test", fetch: fetchMock });

    const first = sendMessage("match-1", "こんにちは", client);
    const duplicate = sendMessage("match-1", "こんにちは", client);
    expect(first).toBe(duplicate);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(JSON.parse((fetchMock.mock.calls[0][1] as RequestInit).body as string)).toEqual({
      body: "こんにちは",
    });

    resolveFetch(response(message("message-1", "2026-09-03T10:00:00Z"), 201));
    await first;
  });

  it("deduplicates by id and sorts messages by server time", () => {
    expect(
      mergeMessages(
        [message("later", "2026-09-03T10:01:00Z")],
        [message("earlier", "2026-09-03T10:00:00Z"), message("later", "2026-09-03T10:01:00Z")],
      ).map(({ id }) => id),
    ).toEqual(["earlier", "later"]);
  });

  it("polls immediately and repeatedly without starting after cancellation", async () => {
    vi.useFakeTimers();
    const fetchMock = vi.fn().mockResolvedValue(response({ items: [], nextCursor: null }));
    const client = new ApiClient({ baseUrl: "https://api.example.test", fetch: fetchMock });
    const onMessages = vi.fn();
    const stop = startMessagePolling({
      matchId: "match-1",
      client,
      intervalMs: 100,
      onMessages,
      onError: vi.fn(),
    });

    await vi.advanceTimersByTimeAsync(0);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(100);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    stop();
    await vi.advanceTimersByTimeAsync(200);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    vi.useRealTimers();
  });
});
