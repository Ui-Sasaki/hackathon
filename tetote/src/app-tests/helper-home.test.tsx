import TestRenderer, { act, type ReactTestInstance } from "react-test-renderer";
import { beforeEach, describe, expect, it, vi } from "vitest";

import HomeScreen from "../app/helper/index";

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  replace: vi.fn(),
  toggleMode: vi.fn(),
  reload: vi.fn(),
  dismissRequest: vi.fn(),
  toggleSavedRequest: vi.fn(),
  isRequestSaved: vi.fn(),
  requests: [] as {
    id: string;
    title: string;
    description: string;
    location: string;
    distance: string;
    deadline: string;
    meta: string;
    tags: string[];
  }[],
  status: "ready" as "loading" | "ready" | "error",
  errorMessage: null as string | null,
}));

vi.mock("react-native", async () => {
  const React = await import("react");
  const component = (name: string) => {
    function MockComponent({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) {
      return React.createElement(name, props, children);
    }
    MockComponent.displayName = `Mock${name}`;
    return MockComponent;
  };
  class Value {
    value: number;
    constructor(value: number) {
      this.value = value;
    }
    setValue(value: number) {
      this.value = value;
    }
    interpolate() {
      return "0deg";
    }
  }
  return {
    ActivityIndicator: component("ActivityIndicator"),
    Animated: {
      Value,
      View: component("AnimatedView"),
      parallel: () => ({ start: (callback?: () => void) => callback?.() }),
      spring: () => ({}),
      timing: () => ({}),
    },
    PanResponder: { create: () => ({ panHandlers: {} }) },
    Pressable: component("Pressable"),
    ScrollView: component("ScrollView"),
    StyleSheet: { create: <T,>(styles: T) => styles },
    Text: component("Text"),
    View: component("View"),
  };
});
vi.mock("expo-router", () => ({
  useRouter: () => ({ push: mocks.push, replace: mocks.replace }),
}));
vi.mock("@expo/vector-icons", () => ({ Ionicons: () => null }));
vi.mock("../context/RequestsContext", () => ({
  useRequests: () => ({
    requests: mocks.requests,
    status: mocks.status,
    errorMessage: mocks.errorMessage,
    reload: mocks.reload,
    dismissRequest: mocks.dismissRequest,
    toggleSavedRequest: mocks.toggleSavedRequest,
    isRequestSaved: mocks.isRequestSaved,
  }),
}));
vi.mock("../context/ModeContext", () => ({
  useMode: () => ({ mode: "helper", toggleMode: mocks.toggleMode }),
}));
vi.mock("../context/FontSizeContext", () => ({
  useFontSize: () => ({ scale: 1 }),
}));

function textContent(node: ReactTestInstance): string {
  return node.children.map((child) => typeof child === "string" ? child : textContent(child)).join("");
}

async function renderScreen() {
  let renderer!: TestRenderer.ReactTestRenderer;
  await act(async () => {
    renderer = TestRenderer.create(<HomeScreen />);
  });
  return renderer;
}

beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  vi.clearAllMocks();
  mocks.requests = [];
  mocks.status = "ready";
  mocks.errorMessage = null;
  mocks.isRequestSaved.mockReturnValue(false);
});

describe("helper request list screen", () => {
  it("does not show fallback cards when the API list is empty", async () => {
    const renderer = await renderScreen();

    expect(textContent(renderer.root)).toContain("公開中の依頼はありません");
    expect(textContent(renderer.root)).not.toContain("犬の散歩");
  });

  it("opens request details with the API request id", async () => {
    mocks.requests = [{
      id: "request-api-1",
      title: "庭の片付け",
      description: "落ち葉を集める手伝いです。",
      location: "大学周辺",
      distance: "1km",
      deadline: "9/10",
      meta: "約30分・1人募集",
      tags: ["#日常生活"],
    }];
    const renderer = await renderScreen();
    const detailButton = renderer.root.find(
      (node) => typeof node.props.onPress === "function" && textContent(node).includes("詳細情報"),
    );

    await act(async () => detailButton.props.onPress());

    expect(mocks.push).toHaveBeenCalledWith({
      pathname: "/helper/request",
      params: {
        requestId: "request-api-1",
        title: "庭の片付け",
        description: "落ち葉を集める手伝いです。",
      },
    });
  });
});
