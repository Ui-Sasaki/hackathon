import TestRenderer, { act, type ReactTestInstance } from "react-test-renderer";
import { beforeEach, describe, expect, it, vi } from "vitest";

import RequestConfirmScreen from "../app/help/request-confirm";

const mocks = vi.hoisted(() => ({
  structure: vi.fn(),
  submitRequestCreation: vi.fn(),
  replace: vi.fn(),
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
    Modal: component("Modal"),
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
    content: "電話番号090-1234-5678を伏せて犬の散歩をお願いします",
    location: "東京都",
    areaCode: "AREA-001",
    time: "30分",
    deadline: "3日後",
  }),
  useRouter: () => ({ back: vi.fn(), replace: mocks.replace }),
}));
vi.mock("@expo/vector-icons", () => ({ Ionicons: () => null }));
vi.mock("../context/FontSizeContext", () => ({ useFontSize: () => ({ scale: 1 }) }));
vi.mock("../api/request-masking", () => {
  const preview = {
    maskedText: "電話番号[電話番号]を伏せて犬の散歩をお願いします",
    detections: [{ type: "phone", placeholder: "[電話番号]", count: 1 }],
    hasDetections: true,
    ruleVersion: "pii-v1",
    status: "masking_confirmation_required",
    requiresMaskingConfirmation: true,
    message: "確認してください",
  };
  return {
    previewRequestMasking: vi.fn().mockResolvedValue({
      status: "ready", preview, confirmed: false, error: null,
    }),
    confirmMaskingPreview: (state: { preview: unknown }) => ({
      ...state, status: "confirmed", confirmed: true,
    }),
    canProceedAfterMasking: (state: { status?: string } | null) => state?.status === "confirmed",
  };
});
vi.mock("../api/request-structuring", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/request-structuring")>();
  return { ...actual, structureConfirmedRequest: mocks.structure };
});
vi.mock("../api/request-creation", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/request-creation")>();
  return { ...actual, submitRequestCreation: mocks.submitRequestCreation };
});

function textContent(node: ReactTestInstance): string {
  return node.children.map((child) => typeof child === "string" ? child : textContent(child)).join("");
}

async function press(root: ReactTestInstance, label: string): Promise<void> {
  const button = root.find(
    (node) => typeof node.props.onPress === "function" && textContent(node).includes(label),
  );
  await act(async () => button.props.onPress());
}

async function renderScreen() {
  let renderer!: TestRenderer.ReactTestRenderer;
  await act(async () => {
    renderer = TestRenderer.create(<RequestConfirmScreen />);
  });
  return renderer;
}

beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  vi.clearAllMocks();
});

describe("TODO 10 request confirmation screen", () => {
  it("moves from confirmed masking to an editable draft without publishing", async () => {
    mocks.structure.mockResolvedValue({
      status: "draft",
      originalText: "電話番号[電話番号]を伏せて犬の散歩をお願いします",
      draft: {
        title: "犬の散歩",
        description: "電話番号[電話番号]を伏せて犬の散歩をお願いします",
        category: "pet_support",
        scheduledAt: null,
        estimatedMinutes: 30,
        approximateArea: null,
        requiredHelpers: 1,
        itemsToBring: [],
        riskLevel: "low",
        riskCandidates: [],
        missingFields: ["scheduledAt"],
        warnings: [],
      },
      additionalQuestion: "希望日時を教えてください",
      error: null,
    });
    const renderer = await renderScreen();

    await press(renderer.root, "マスキング結果を確認しました");
    await press(renderer.root, "AIで内容を整理する");

    const rendered = textContent(renderer.root);
    expect(rendered).toContain("AIが整理した下書き（未公開）");
    expect(rendered).toContain("希望日時を教えてください");
    expect(rendered).toContain("この下書きはまだ公開されていません");
    expect(renderer.root.findByProps({ accessibilityLabel: "依頼タイトル" }).props.value)
      .toBe("犬の散歩");
  });

  it("shows retained input as an editable manual draft after service failure", async () => {
    mocks.structure.mockResolvedValue({
      status: "manual",
      originalText: "電話番号[電話番号]を伏せて犬の散歩をお願いします",
      draft: {
        title: "",
        description: "電話番号[電話番号]を伏せて犬の散歩をお願いします",
        category: "",
        scheduledAt: null,
        estimatedMinutes: null,
        approximateArea: null,
        requiredHelpers: null,
        itemsToBring: [],
        riskLevel: "low",
        riskCandidates: [],
        missingFields: [],
        warnings: [],
      },
      additionalQuestion: null,
      error: new Error("unavailable"),
    });
    const renderer = await renderScreen();

    await press(renderer.root, "マスキング結果を確認しました");
    await press(renderer.root, "AIで内容を整理する");

    expect(textContent(renderer.root)).toContain("手入力で下書きを仕上げる");
    expect(renderer.root.findByProps({ accessibilityLabel: "構造化した依頼内容" }).props.value)
      .toContain("犬の散歩をお願いします");
  });

  it("publishes an edited draft and opens the requester request list", async () => {
    mocks.structure.mockResolvedValue({
      status: "draft",
      originalText: "電話番号[電話番号]を伏せて犬の散歩をお願いします",
      draft: {
        title: "犬の散歩",
        description: "電話番号[電話番号]を伏せて犬の散歩をお願いします",
        category: "pet_support",
        scheduledAt: "2026-09-10T10:00:00+09:00",
        estimatedMinutes: 30,
        approximateArea: null,
        requiredHelpers: 1,
        itemsToBring: [],
        riskLevel: "low",
        riskCandidates: [],
        missingFields: [],
        warnings: [],
      },
      additionalQuestion: null,
      error: null,
    });
    mocks.submitRequestCreation.mockResolvedValue({
      status: "created",
      attempt: { input: {}, idempotencyKey: "operation-1" },
      request: { id: "request-1", title: "犬の散歩" },
      error: null,
    });
    const renderer = await renderScreen();

    await press(renderer.root, "マスキング結果を確認しました");
    await press(renderer.root, "AIで内容を整理する");
    await press(renderer.root, "内容を確認して公開する");

    expect(mocks.submitRequestCreation.mock.calls[0][0].input).toMatchObject({
      title: "犬の散歩",
      description: "電話番号[電話番号]を伏せて犬の散歩をお願いします",
      category: "pet_support",
      scheduledAt: "2026-09-10T10:00:00+09:00",
      estimatedMinutes: 30,
      requiredHelpers: 1,
      areaCode: "AREA-001",
      riskLevel: "low",
      confirmed: true,
    });
    expect(textContent(renderer.root)).toContain("依頼を公開しました");

    await press(renderer.root, "応募者確認へ進む");
    expect(mocks.replace).toHaveBeenCalledWith({
      pathname: "/help/requests",
      params: { requestId: "request-1" },
    });
  });
});
