import {
  createContext,
  ReactNode,
  useContext,
  useState,
} from "react";

export type RequestItem = {
  id: number;
  title: string;
  location: string;
  age: string;
  gender: string;
  distance: string;
  deadline: string;
  tags: string[];
};

const initialRequests: RequestItem[] = [
  {
    id: 1,
    title: "玄関前の除雪のお手伝い",
    location: "足立区",
    age: "81歳",
    gender: "女性",
    distance: "0.8km",
    deadline: "9/28",
    tags: ["#運動", "#力仕事"],
  },
  {
    id: 2,
    title: "庭の芝刈りのお手伝い",
    location: "港区",
    age: "72歳",
    gender: "男性",
    distance: "1.1km",
    deadline: "9/29",
    tags: ["#力仕事", "#日常生活"],
  },
  {
    id: 3,
    title: "スマホの使い方を教えてほしい",
    location: "渋谷区",
    age: "68歳",
    gender: "女性",
    distance: "1.5km",
    deadline: "9/30",
    tags: ["#デジタル", "#付き添い"],
  },
  {
    id: 4,
    title: "重い買い物袋を家まで運んでほしい",
    location: "目黒区",
    age: "76歳",
    gender: "女性",
    distance: "1.9km",
    deadline: "10/1",
    tags: ["#買い物", "#力仕事"],
  },
  {
    id: 5,
    title: "犬の散歩を手伝ってほしい",
    location: "世田谷区",
    age: "63歳",
    gender: "男性",
    distance: "2.2km",
    deadline: "10/2",
    tags: ["#動物", "#散歩"],
  },
  {
    id: 6,
    title: "家具を少し移動するのを手伝ってほしい",
    location: "品川区",
    age: "79歳",
    gender: "男性",
    distance: "2.6km",
    deadline: "10/3",
    tags: ["#家具", "#力仕事"],
  },
  {
    id: 7,
    title: "病院まで一緒に歩いてほしい",
    location: "新宿区",
    age: "84歳",
    gender: "女性",
    distance: "3.0km",
    deadline: "10/4",
    tags: ["#付き添い", "#外出"],
  },
  {
    id: 8,
    title: "パソコンの設定を手伝ってほしい",
    location: "中野区",
    age: "70歳",
    gender: "男性",
    distance: "3.4km",
    deadline: "10/5",
    tags: ["#デジタル", "#パソコン"],
  },
];

type RequestsContextType = {
  requests: RequestItem[];
  savedRequests: RequestItem[];
  dismissRequest: (id: number) => void;
  saveRequest: (id: number) => void;
  removeSavedRequest: (id: number) => void;
  toggleSavedRequest: (id: number) => void;
  isRequestSaved: (id: number) => boolean;
};

const RequestsContext =
  createContext<RequestsContextType | null>(null);

export function RequestsProvider({
  children,
}: {
  children: ReactNode;
}) {
  const [requests, setRequests] =
    useState<RequestItem[]>(initialRequests);

  const [savedRequests, setSavedRequests] =
    useState<RequestItem[]>([]);

  const dismissRequest = (id: number) => {
    setRequests((current) =>
      current.filter(
        (request) => request.id !== id
      )
    );
  };

  const saveRequest = (id: number) => {
    const request = requests.find(
      (item) => item.id === id
    );

    if (!request) return;

    setSavedRequests((current) => {
      const alreadySaved = current.some(
        (item) => item.id === id
      );

      if (alreadySaved) {
        return current;
      }

      return [...current, request];
    });
  };

  const removeSavedRequest = (id: number) => {
    setSavedRequests((current) =>
      current.filter(
        (item) => item.id !== id
      )
    );
  };

  const toggleSavedRequest = (id: number) => {
    const alreadySaved = savedRequests.some(
      (item) => item.id === id
    );

    if (alreadySaved) {
      removeSavedRequest(id);
    } else {
      saveRequest(id);
    }
  };

  const isRequestSaved = (id: number) => {
    return savedRequests.some(
      (item) => item.id === id
    );
  };

  return (
    <RequestsContext.Provider
      value={{
        requests,
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
    throw new Error(
      "useRequests must be used inside RequestsProvider"
    );
  }

  return context;
}