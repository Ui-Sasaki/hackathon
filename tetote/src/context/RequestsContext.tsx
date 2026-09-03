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
import {
  dismissPublicRequest,
  listSavedPublicRequests,
  removeSavedPublicRequest,
  savePublicRequest,
} from "../features/requests/preferences";

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
  const [requests, setRequests] = useState<RequestItem[]>([]);
  const [status, setStatus] = useState<RequestsStatus>("loading");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [savedIds, setSavedIds] = useState<Set<string>>(new Set());
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

  // 初期状態が loading のため、初回はそのまま取得だけを行う。
  useEffect(() => {
    fetchRequests();
  }, [fetchRequests]);

  useEffect(() => {
    void listSavedPublicRequests()
      .then((items) => {
        setSavedIds(new Set(items.map((item) => item.id)));
        setSavedRequests(items.map(toRequestCard));
      })
      .catch(() => undefined);
  }, []);

  const reload = useCallback(() => {
    setStatus("loading");
    setErrorMessage(null);
    fetchRequests();
  }, [fetchRequests]);

  const dismissRequest = (id: string) => {
    setDismissedIds((current) => new Set(current).add(id));
    void dismissPublicRequest(id).catch(() => {
      setDismissedIds((current) => {
        const next = new Set(current);
        next.delete(id);
        return next;
      });
    });
  };

  const visibleRequests = requests.filter(
    (request) => !dismissedIds.has(request.id),
  );

  const saveRequest = (id: string) => {
    const request = requests.find((item) => item.id === id);
    if (!request) return;
    setSavedIds((current) => new Set(current).add(id));
    setSavedRequests((current) => current.some((item) => item.id === id) ? current : [...current, request]);
    void savePublicRequest(id).catch(() => {
      setSavedIds((current) => {
        const next = new Set(current);
        next.delete(id);
        return next;
      });
      setSavedRequests((current) => current.filter((item) => item.id !== id));
    });
  };

  const removeSavedRequest = (id: string) => {
    setSavedIds((current) => {
      const next = new Set(current);
      next.delete(id);
      return next;
    });
    const previous = savedRequests.find((item) => item.id === id);
    setSavedRequests((current) => current.filter((item) => item.id !== id));
    void removeSavedPublicRequest(id).catch(() => {
      setSavedIds((current) => new Set(current).add(id));
      if (previous) setSavedRequests((current) => [...current, previous]);
    });
  };

  const toggleSavedRequest = (id: string) => {
    const alreadySaved = savedIds.has(id);
    if (alreadySaved) {
      removeSavedRequest(id);
    } else {
      saveRequest(id);
    }
  };

  const isRequestSaved = (id: string) => {
    return savedIds.has(id);
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
