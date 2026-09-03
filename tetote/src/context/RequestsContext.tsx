import {
  createContext,
  ReactNode,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";

import {
  listPublicRequests,
  requestListErrorMessage,
  toRequestCard,
  type RequestCard,
} from "../features/requests/client";
import { useAuth } from "../auth/AuthContext";

export type RequestItem = RequestCard;

type RequestsStatus = "loading" | "ready" | "error";

type RequestsContextType = {
  requests: RequestItem[];
  status: RequestsStatus;
  errorMessage: string | null;
  reload: () => void;
  savedRequests: RequestItem[];
  dismissRequest: (id: string) => void;
  saveRequest: (id: string) => void;
  removeSavedRequest: (id: string) => void;
  toggleSavedRequest: (id: string) => void;
  isRequestSaved: (id: string) => boolean;
};

const RequestsContext = createContext<RequestsContextType | null>(null);

export function RequestsProvider({ children }: { children: ReactNode }) {
  const { status: authStatus } = useAuth();
  const [requests, setRequests] = useState<RequestItem[]>([]);
  const [status, setStatus] = useState<RequestsStatus>("loading");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [savedRequests, setSavedRequests] = useState<RequestItem[]>([]);
  // 一覧から閉じたカードは、再読み込み後も再表示しない。
  const [dismissedIds, setDismissedIds] = useState<Set<string>>(new Set());

  const fetchRequests = useCallback(() => {
    void listPublicRequests()
      .then((page) => {
        setRequests(page.items.map(toRequestCard));
        setStatus("ready");
      })
      .catch((error: unknown) => {
        setErrorMessage(requestListErrorMessage(error));
        setStatus("error");
      });
  }, []);

  // セッション復元前の401が認証済みセッションを消さないよう、復元完了後に取得する。
  useEffect(() => {
    if (authStatus !== "authenticated") return;
    fetchRequests();
  }, [authStatus, fetchRequests]);

  const reload = useCallback(() => {
    setStatus("loading");
    setErrorMessage(null);
    fetchRequests();
  }, [fetchRequests]);

  // 非表示・保存はローカル状態で扱う。APIへの永続化（/requests/{id}/dismiss、
  // /saved-requests）はバックエンド実装済みで、接続は #78 / #79 の範囲。
  const dismissRequest = (id: string) => {
    setDismissedIds((current) => new Set(current).add(id));
  };

  const visibleRequests = requests.filter(
    (request) => !dismissedIds.has(request.id),
  );

  const saveRequest = (id: string) => {
    const request = requests.find((item) => item.id === id);
    if (!request) return;

    setSavedRequests((current) => {
      const alreadySaved = current.some((item) => item.id === id);
      if (alreadySaved) return current;
      return [...current, request];
    });
  };

  const removeSavedRequest = (id: string) => {
    setSavedRequests((current) => current.filter((item) => item.id !== id));
  };

  const toggleSavedRequest = (id: string) => {
    const alreadySaved = savedRequests.some((item) => item.id === id);
    if (alreadySaved) {
      removeSavedRequest(id);
    } else {
      saveRequest(id);
    }
  };

  const isRequestSaved = (id: string) => {
    return savedRequests.some((item) => item.id === id);
  };

  return (
    <RequestsContext.Provider
      value={{
        requests: visibleRequests,
        status,
        errorMessage,
        reload,
        savedRequests,
        dismissRequest,
        saveRequest,
        removeSavedRequest,
        toggleSavedRequest,
        isRequestSaved,
      }}
    >
      {children}
    </RequestsContext.Provider>
  );
}

export function useRequests() {
  const context = useContext(RequestsContext);

  if (!context) {
    throw new Error("useRequests must be used inside RequestsProvider");
  }

  return context;
}
