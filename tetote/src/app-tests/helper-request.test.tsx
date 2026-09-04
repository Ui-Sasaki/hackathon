import TestRenderer, { act, type ReactTestInstance } from "react-test-renderer";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ApplicationScreen from "../app/helper/request";

const mocks = vi.hoisted(() => ({
  back: vi.fn(),
  push: vi.fn(),
  getRequest: vi.fn(),
  createApplication: vi.fn(),
  withdrawApplication: vi.fn(),
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
  return {
    ActivityIndicator: component("ActivityIndicator"),
    Pressable: component("Pressable"),
    ScrollView: component("ScrollView"),
    StyleSheet: { create: <T,>(styles: T) => styles },
    Text: component("Text"),
    TextInput: component("TextInput"),
    View: component("View"),
  };
});
vi.mock("expo-router", () => ({
  useLocalSearchParams: () => ({
    requestId: "request-api-1",
    title: "古いタイトル",
    description: "古い説明",
  }),
  useRouter: () => ({ back: mocks.back, push: mocks.push }),
}));
vi.mock("../features/requests/client", () => ({
  getRequest: mocks.getRequest,
  requestListErrorMessage: () => "依頼詳細を読み込めませんでした。",
}));
vi.mock("../features/applications/client", () => ({
  applicationErrorMessage: () => "応募を送信できませんでした。",
  createApplication: mocks.createApplication,
  withdrawalErrorMessage: () => "応募を取り下げできませんでした。",
  withdrawApplication: mocks.withdrawApplication,
}));

function textContent(node: ReactTestInstance): string {
  return node.children.map((child) => typeof child === "string" ? child : textContent(child)).join("");
}

async function renderScreen() {
  let renderer!: TestRenderer.ReactTestRenderer;
  await act(async () => {
    renderer = TestRenderer.create(<ApplicationScreen />);
  });
  return renderer;
}

beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  vi.clearAllMocks();
  mocks.getRequest.mockResolvedValue({
    id: "request-api-1",
    requesterId: "requester-1",
    title: "APIの依頼タイトル",
    description: "APIから取得した依頼詳細です。",
    category: "cleaning",
    areaLabel: "大学周辺",
    distanceKm: 1,
    scheduledAt: "2026-09-10T10:00:00+09:00",
    estimatedMinutes: 30,
    requiredHelpers: 1,
    acceptedHelpers: 0,
    status: "published",
    warnings: [],
    version: 1,
  });
});

describe("helper request detail screen", () => {
  it("loads request detail by id and displays the API content", async () => {
    const renderer = await renderScreen();

    expect(mocks.getRequest).toHaveBeenCalledWith("request-api-1");
    expect(textContent(renderer.root)).toContain("APIの依頼タイトル");
    expect(textContent(renderer.root)).toContain("APIから取得した依頼詳細です。");
    expect(textContent(renderer.root)).not.toContain("古い説明");
    expect(renderer.root.findByProps({ accessibilityLabel: "対応可能日時" }).props.value)
      .toBe("2026-09-10T10:00:00+09:00");
  });

  it("submits an application to the loaded request id", async () => {
    mocks.createApplication.mockResolvedValue({
      id: "application-1",
      requestId: "request-api-1",
      helperId: "helper-1",
      message: "対応できます",
      availableAt: "2026-09-10T10:00:00+09:00",
      status: "applied",
      createdAt: "2026-09-04T00:00:00Z",
      updatedAt: null,
    });
    const renderer = await renderScreen();

    await act(async () => {
      renderer.root.findByProps({ accessibilityLabel: "応募理由" }).props.onChangeText("対応できます");
      renderer.root.findByProps({ accessibilityLabel: "対応可能日時" }).props.onChangeText("2026-09-10T10:00:00+09:00");
    });
    const submitButton = renderer.root.find(
      (node) => typeof node.props.onPress === "function" && textContent(node).includes("応募を送信する"),
    );
    await act(async () => submitButton.props.onPress());

    expect(mocks.createApplication).toHaveBeenCalledWith("request-api-1", {
      message: "対応できます",
      availableAt: "2026-09-10T10:00:00+09:00",
    });
  });
});
