import { apiClient, type ApiClient } from "../../api/client";

export type Message = {
  id: string;
  matchId: string;
  senderId: string;
  body: string;
  sentAt: string;
  readAt: string | null;
  moderationStatus: "allowed" | "flagged" | "hidden";
};

export type MessageListResponse = {
  items: Message[];
  nextCursor: string | null;
};

export const MESSAGE_POLL_INTERVAL_MS = 3_000;

export function listMessages(
  matchId: string,
  client: ApiClient = apiClient,
): Promise<MessageListResponse> {
  return client.get<MessageListResponse>(
    `/matches/${encodeURIComponent(matchId)}/messages`,
  );
}

const pendingSends = new WeakMap<ApiClient, Map<string, Promise<Message>>>();

export function sendMessage(
  matchId: string,
  body: string,
  client: ApiClient = apiClient,
): Promise<Message> {
  let sends = pendingSends.get(client);
  if (!sends) {
    sends = new Map();
    pendingSends.set(client, sends);
  }

  const key = `${matchId}\u0000${body}`;
  const pending = sends.get(key);
  if (pending) return pending;

  const request = client
    .post<Message>(`/matches/${encodeURIComponent(matchId)}/messages`, { body })
    .finally(() => sends?.delete(key));
  sends.set(key, request);
  return request;
}

export function mergeMessages(current: Message[], incoming: Message[]): Message[] {
  const messagesById = new Map(current.map((message) => [message.id, message]));
  for (const message of incoming) messagesById.set(message.id, message);
  return [...messagesById.values()].sort(
    (left, right) =>
      new Date(left.sentAt).getTime() - new Date(right.sentAt).getTime(),
  );
}

export function startMessagePolling({
  matchId,
  onMessages,
  onError,
  client = apiClient,
  intervalMs = MESSAGE_POLL_INTERVAL_MS,
}: {
  matchId: string;
  onMessages: (messages: Message[]) => void;
  onError: (error: unknown) => void;
  client?: ApiClient;
  intervalMs?: number;
}): () => void {
  let active = true;
  let timeout: ReturnType<typeof setTimeout> | undefined;

  const poll = async () => {
    try {
      const response = await listMessages(matchId, client);
      if (active) onMessages(response.items);
    } catch (error) {
      if (active) onError(error);
    } finally {
      if (active) timeout = setTimeout(poll, intervalMs);
    }
  };

  void poll();
  return () => {
    active = false;
    if (timeout !== undefined) clearTimeout(timeout);
  };
}
