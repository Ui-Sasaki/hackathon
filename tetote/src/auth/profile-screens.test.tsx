import { TextInput } from "react-native";
import TestRenderer, { act, type ReactTestInstance } from "react-test-renderer";
import { beforeEach, describe, expect, it, vi } from "vitest";

import HelperProfileScreen from "../app/onboarding/helper/helper-profile";
import RequesterProfileScreen from "../app/onboarding/requester/requester-profile";
import ProfileScreen from "../shared/ProfileScreen";
import { ProfileValidationError, type AuthProfile } from "./client";

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  replace: vi.fn(),
  refreshProfile: vi.fn(),
  updateProfile: vi.fn(),
}));

vi.mock("react-native", async () => {
  const React = await import("react");
  const component = (name: string) => {
    function MockComponent({
      children,
      ...props
    }: React.PropsWithChildren<Record<string, unknown>>) {
      return React.createElement(name, props, children);
    }
    MockComponent.displayName = `Mock${name}`;
    return MockComponent;
  };
  return {
    ActivityIndicator: component("ActivityIndicator"),
    Alert: { alert: vi.fn() },
    Modal: component("Modal"),
    Pressable: component("Pressable"),
    ScrollView: component("ScrollView"),
    StyleSheet: { create: <T,>(styles: T) => styles },
    Text: component("Text"),
    TextInput: component("TextInput"),
    View: component("View"),
    useWindowDimensions: () => ({ width: 390, height: 844 }),
  };
});
vi.mock("expo-router", () => ({
  usePathname: () => "/help/profile",
  useRouter: () => ({ push: mocks.push, replace: mocks.replace }),
}));
vi.mock("expo-image-picker", () => ({
  MediaTypeOptions: { Images: "images" },
  requestMediaLibraryPermissionsAsync: vi.fn(),
  launchImageLibraryAsync: vi.fn(),
}));
vi.mock("@expo/vector-icons", () => ({ Ionicons: () => null }));
vi.mock("../context/FontSizeContext", () => ({
  useFontSize: () => ({ scale: 1 }),
}));
vi.mock("./AuthContext", () => ({
  useAuth: () => ({
    profile,
    refreshProfile: mocks.refreshProfile,
    updateProfile: mocks.updateProfile,
  }),
}));

const profile: AuthProfile = {
  id: "usr_101",
  displayName: "山田 花子",
  role: "member",
  emailVerified: true,
  verificationStatus: "approved",
  status: "active",
  areaCode: "AREA-001",
};

beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  vi.clearAllMocks();
  mocks.refreshProfile.mockResolvedValue(profile);
  mocks.updateProfile.mockResolvedValue(profile);
});

function textContent(node: ReactTestInstance): string {
  return node.children
    .map((child) => typeof child === "string" ? child : textContent(child))
    .join("");
}

function press(root: ReactTestInstance, label: string): Promise<void> {
  const button = root.find(
    (node) => typeof node.props.onPress === "function" && textContent(node).includes(label),
  );
  return act(async () => button.props.onPress());
}

async function renderScreen(Component: React.ComponentType) {
  let renderer!: TestRenderer.ReactTestRenderer;
  await act(async () => {
    renderer = TestRenderer.create(<Component />);
  });
  return renderer;
}

describe.each([
  ["依頼者", RequesterProfileScreen, "/onboarding/requester/preferences"],
  ["支援者", HelperProfileScreen, "/onboarding/helper/help"],
])("%sオンボーディング", (_label, Component, destination) => {
  it("API連携済みフィールドだけを保存してから遷移する", async () => {
    const renderer = await renderScreen(Component);
    const root = renderer.root;

    const nameInput = root.findByProps({ placeholder: "名前を入力" });
    await act(async () => nameInput.props.onChangeText("更新 花子"));
    await press(root, "次に進む");

    expect(mocks.updateProfile).toHaveBeenCalledWith({
      displayName: "更新 花子",
      areaCode: "AREA-001",
    });
    expect(mocks.push).toHaveBeenCalled();
    const route = mocks.push.mock.calls[0][0];
    expect(typeof route === "string" ? route : route.pathname).toBe(destination);
  });

  it("保存失敗時は遷移せず入力検証エラーを表示する", async () => {
    mocks.updateProfile.mockRejectedValue(new ProfileValidationError());
    const renderer = await renderScreen(Component);

    await press(renderer.root, "次に進む");

    expect(textContent(renderer.root)).toContain("名前と地域の入力内容を確認してください");
    expect(mocks.push).not.toHaveBeenCalled();
  });
});

describe("共通プロフィール", () => {
  it("取得した本人確認状態を表示し、同じ状態管理で編集内容を保存する", async () => {
    const renderer = await renderScreen(ProfileScreen);
    const root = renderer.root;

    expect(textContent(root)).toContain("本人確認済み");
    const inputs = root.findAllByType(TextInput);
    await act(async () => inputs[0].props.onChangeText("更新 花子"));
    await press(root, "保存する");

    expect(mocks.updateProfile).toHaveBeenCalledWith({
      displayName: "更新 花子",
      areaCode: "AREA-001",
    });
    expect(textContent(root)).toContain("プロフィールを更新しました");
  });
});
