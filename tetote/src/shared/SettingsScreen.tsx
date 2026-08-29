import { useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  Pressable,
  ScrollView,
  Switch,
  Modal,
} from "react-native";
import {
  useRouter,
  usePathname,
} from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useFontSize } from "../context/FontSizeContext";
import { useAuth } from "../auth/AuthContext";

export default function HelperSettingsScreen() {
  const router = useRouter();
  const pathname = usePathname();
  const { signOut } = useAuth();

  const handleBack = () => {
    if (pathname.startsWith("/help")) {
      router.replace("/help/profile");
    } else {
      router.replace("/helper/profile");
    }
  };

  const [notificationsEnabled, setNotificationsEnabled] =
    useState(true);

  const [locationEnabled, setLocationEnabled] =
    useState(true);

  const { fontSize, setFontSize, scale } =
    useFontSize();

  const [deleteModalVisible, setDeleteModalVisible] =
    useState(false);

  const [logoutModalVisible, setLogoutModalVisible] =
    useState(false);
  const [logoutError, setLogoutError] = useState("");
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  const fs = (size: number) => size * scale;

  const handleLogout = async () => {
    if (isLoggingOut) return;
    setLogoutError("");
    setIsLoggingOut(true);
    try {
      await signOut();
      setLogoutModalVisible(false);
      router.replace("/auth/login");
    } catch {
      setLogoutError("ログアウトに失敗しました。もう一度お試しください");
    } finally {
      setIsLoggingOut(false);
    }
  };

  const handleDeleteAccount = () => {
    setDeleteModalVisible(false);
    router.replace("/auth/login");
  };

  return (
    <View style={styles.screen}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.container}>
          <View style={styles.header}>
            <Pressable
  onPress={handleBack}
  style={({ pressed }) => [
    styles.backButton,
    pressed && styles.pressed,
  ]}
>
              <Ionicons
                name="chevron-back"
                size={30}
                color="#159326"
              />
            </Pressable>

            <Text
              style={[
                styles.title,
                { fontSize: fs(24) },
              ]}
            >
              設定
            </Text>

            <View style={styles.headerSpacer} />
          </View>

          <View style={styles.settingsGroup}>
            <View style={styles.settingRow}>
              <Text
                style={[
                  styles.settingText,
                  { fontSize: fs(15) },
                ]}
              >
                通知
              </Text>

              <Switch
                value={notificationsEnabled}
                onValueChange={setNotificationsEnabled}
                trackColor={{
                  false: "#D9D9D9",
                  true: "#159326",
                }}
                thumbColor="#FFFFFF"
              />
            </View>

            <View style={styles.divider} />

            <View style={styles.settingRow}>
              <Text
                style={[
                  styles.settingText,
                  { fontSize: fs(15) },
                ]}
              >
                位置情報
              </Text>

              <Switch
                value={locationEnabled}
                onValueChange={setLocationEnabled}
                trackColor={{
                  false: "#D9D9D9",
                  true: "#159326",
                }}
                thumbColor="#FFFFFF"
              />
            </View>
          </View>

          <View style={styles.fontSection}>
            <Text
              style={[
                styles.fontSectionTitle,
                { fontSize: fs(15) },
              ]}
            >
              文字サイズ
            </Text>

            <Text
              style={[
                styles.fontDescription,
                { fontSize: fs(12) },
              ]}
            >
              アプリ内の文字の大きさを変更できます
            </Text>

            <View style={styles.fontOptions}>
              <Pressable
                onPress={() => setFontSize("small")}
                style={({ pressed }) => [
                  styles.fontOption,
                  fontSize === "small" &&
                    styles.fontOptionSelected,
                  pressed &&
                    styles.fontOptionPressed,
                ]}
              >
                <Text
                  style={[
                    styles.smallPreview,
                    fontSize === "small" &&
                      styles.fontPreviewSelected,
                  ]}
                >
                  あ
                </Text>

                <Text
                  style={[
                    styles.fontOptionLabel,
                    fontSize === "small" &&
                      styles.fontOptionLabelSelected,
                  ]}
                >
                  小
                </Text>
              </Pressable>

              <Pressable
                onPress={() => setFontSize("medium")}
                style={({ pressed }) => [
                  styles.fontOption,
                  fontSize === "medium" &&
                    styles.fontOptionSelected,
                  pressed &&
                    styles.fontOptionPressed,
                ]}
              >
                <Text
                  style={[
                    styles.mediumPreview,
                    fontSize === "medium" &&
                      styles.fontPreviewSelected,
                  ]}
                >
                  あ
                </Text>

                <Text
                  style={[
                    styles.fontOptionLabel,
                    fontSize === "medium" &&
                      styles.fontOptionLabelSelected,
                  ]}
                >
                  中
                </Text>
              </Pressable>

              <Pressable
                onPress={() => setFontSize("large")}
                style={({ pressed }) => [
                  styles.fontOption,
                  fontSize === "large" &&
                    styles.fontOptionSelected,
                  pressed &&
                    styles.fontOptionPressed,
                ]}
              >
                <Text
                  style={[
                    styles.largePreview,
                    fontSize === "large" &&
                      styles.fontPreviewSelected,
                  ]}
                >
                  あ
                </Text>

                <Text
                  style={[
                    styles.fontOptionLabel,
                    fontSize === "large" &&
                      styles.fontOptionLabelSelected,
                  ]}
                >
                  大
                </Text>
              </Pressable>
            </View>
          </View>

          <View style={styles.menuGroup}>
            <SettingButton
              label="ヘルプ"
              onPress={() => {}}
              scale={scale}
            />

            <SettingButton
              label="利用規約"
              onPress={() => {}}
              scale={scale}
            />

            <SettingButton
              label="プライバシーポリシー"
              onPress={() => {}}
              scale={scale}
              last
            />
          </View>

          <View style={styles.accountGroup}>
            <Pressable
              onPress={() =>
                setLogoutModalVisible(true)
              }
              style={({ pressed }) => [
                styles.accountButton,
                pressed && styles.pressed,
              ]}
            >
              <Text
                style={[
                  styles.logoutText,
                  { fontSize: fs(15) },
                ]}
              >
                ログアウト
              </Text>

              <Ionicons
                name="chevron-forward"
                size={20}
                color="#777777"
              />
            </Pressable>

            <View style={styles.divider} />

            <Pressable
              onPress={() =>
                setDeleteModalVisible(true)
              }
              style={({ pressed }) => [
                styles.accountButton,
                pressed && styles.pressed,
              ]}
            >
              <Text
                style={[
                  styles.deleteText,
                  { fontSize: fs(15) },
                ]}
              >
                アカウントを削除
              </Text>

              <Ionicons
                name="chevron-forward"
                size={20}
                color="#D9534F"
              />
            </Pressable>
          </View>
        </View>
      </ScrollView>

      <Modal
        visible={logoutModalVisible}
        transparent
        animationType="fade"
        onRequestClose={() =>
          setLogoutModalVisible(false)
        }
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalCard}>
            <View style={styles.logoutIconCircle}>
              <Ionicons
                name="log-out-outline"
                size={32}
                color="#159326"
              />
            </View>

            <Text
              style={[
                styles.modalTitle,
                { fontSize: fs(20) },
              ]}
            >
              ログアウトしますか？
            </Text>

            <Text
              style={[
                styles.modalDescription,
                {
                  fontSize: fs(14),
                  lineHeight: fs(22),
                },
              ]}
            >
              再度利用する際は、もう一度ログインする必要があります。
            </Text>

            <Pressable
              onPress={handleLogout}
              disabled={isLoggingOut}
              style={({ pressed }) => [
                styles.logoutConfirmButton,
                isLoggingOut && styles.disabled,
                pressed && styles.pressed,
              ]}
            >
              <Text
                style={[
                  styles.logoutConfirmButtonText,
                  { fontSize: fs(15) },
                ]}
              >
                {isLoggingOut ? "ログアウト中…" : "ログアウト"}
              </Text>
            </Pressable>

            {logoutError ? (
              <Text style={styles.logoutError}>{logoutError}</Text>
            ) : null}

            <Pressable
              onPress={() =>
                setLogoutModalVisible(false)
              }
              style={({ pressed }) => [
                styles.cancelButton,
                pressed && styles.pressed,
              ]}
            >
              <Text
                style={[
                  styles.cancelButtonText,
                  { fontSize: fs(15) },
                ]}
              >
                キャンセル
              </Text>
            </Pressable>
          </View>
        </View>
      </Modal>

      <Modal
        visible={deleteModalVisible}
        transparent
        animationType="fade"
        onRequestClose={() =>
          setDeleteModalVisible(false)
        }
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalCard}>
            <View style={styles.warningCircle}>
              <Ionicons
                name="warning"
                size={34}
                color="#D9534F"
              />
            </View>

            <Text
              style={[
                styles.modalTitle,
                { fontSize: fs(20) },
              ]}
            >
              アカウントを削除しますか？
            </Text>

            <Text
              style={[
                styles.modalDescription,
                {
                  fontSize: fs(14),
                  lineHeight: fs(22),
                },
              ]}
            >
              アカウントを削除すると、これまでの活動履歴やプロフィール情報など、すべてのデータが削除されます。
            </Text>

            <Text
              style={[
                styles.modalWarning,
                { fontSize: fs(13) },
              ]}
            >
              この操作は取り消すことができません。
            </Text>

            <Pressable
              onPress={handleDeleteAccount}
              style={({ pressed }) => [
                styles.deleteButton,
                pressed && styles.pressed,
              ]}
            >
              <Text
                style={[
                  styles.deleteButtonText,
                  { fontSize: fs(15) },
                ]}
              >
                アカウントを削除
              </Text>
            </Pressable>

            <Pressable
              onPress={() =>
                setDeleteModalVisible(false)
              }
              style={({ pressed }) => [
                styles.cancelButton,
                pressed && styles.pressed,
              ]}
            >
              <Text
                style={[
                  styles.cancelButtonText,
                  { fontSize: fs(15) },
                ]}
              >
                キャンセル
              </Text>
            </Pressable>
          </View>
        </View>
      </Modal>
    </View>
  );
}

function SettingButton({
  label,
  onPress,
  scale,
  last = false,
}: {
  label: string;
  onPress: () => void;
  scale: number;
  last?: boolean;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        styles.menuButton,
        last && styles.menuButtonLast,
        pressed && styles.pressed,
      ]}
    >
      <Text
        style={[
          styles.settingText,
          { fontSize: 15 * scale },
        ]}
      >
        {label}
      </Text>

      <Ionicons
        name="chevron-forward"
        size={20}
        color="#777777"
      />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: "#FFF5E9",
  },

  scrollContent: {
    flexGrow: 1,
    alignItems: "center",
    paddingBottom: 40,
  },

  container: {
    width: "100%",
    maxWidth: 520,
    paddingHorizontal: 28,
    paddingTop: 40,
  },

  header: {
    width: "100%",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 36,
  },

  backButton: {
    width: 44,
    height: 44,
    alignItems: "center",
    justifyContent: "center",
  },

  title: {
    color: "#159326",
    fontWeight: "900",
  },

  headerSpacer: {
    width: 44,
  },

  settingsGroup: {
    width: "100%",
    backgroundColor: "#FFFFFF",
    borderRadius: 18,
    paddingHorizontal: 18,
    marginBottom: 20,
  },

  settingRow: {
    minHeight: 64,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },

  settingText: {
    color: "#111111",
    fontWeight: "700",
  },

  divider: {
    height: 1,
    backgroundColor: "#EEEEEE",
  },

  fontSection: {
    width: "100%",
    backgroundColor: "#FFFFFF",
    borderRadius: 18,
    paddingHorizontal: 18,
    paddingTop: 17,
    paddingBottom: 18,
    marginBottom: 20,
  },

  fontSectionTitle: {
    color: "#111111",
    fontWeight: "800",
  },

  fontDescription: {
    color: "#888888",
    marginTop: 4,
  },

  fontOptions: {
    width: "100%",
    flexDirection: "row",
    gap: 10,
    marginTop: 16,
  },

  fontOption: {
    flex: 1,
    height: 82,
    borderRadius: 15,
    backgroundColor: "#F3F3F3",
    borderWidth: 2,
    borderColor: "transparent",
    alignItems: "center",
    justifyContent: "center",
  },

  fontOptionSelected: {
    backgroundColor: "#EDF7EE",
    borderColor: "#159326",
  },

  fontOptionPressed: {
    opacity: 0.7,
  },

  smallPreview: {
    color: "#555555",
    fontSize: 17,
    fontWeight: "800",
  },

  mediumPreview: {
    color: "#555555",
    fontSize: 23,
    fontWeight: "800",
  },

  largePreview: {
    color: "#555555",
    fontSize: 30,
    fontWeight: "800",
  },

  fontPreviewSelected: {
    color: "#159326",
  },

  fontOptionLabel: {
    color: "#777777",
    fontSize: 11,
    fontWeight: "700",
    marginTop: 4,
  },

  fontOptionLabelSelected: {
    color: "#159326",
    fontWeight: "900",
  },

  menuGroup: {
    width: "100%",
    backgroundColor: "#FFFFFF",
    borderRadius: 18,
    overflow: "hidden",
    marginBottom: 20,
  },

  menuButton: {
    minHeight: 62,
    paddingHorizontal: 18,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    borderBottomWidth: 1,
    borderBottomColor: "#EEEEEE",
  },

  menuButtonLast: {
    borderBottomWidth: 0,
  },

  accountGroup: {
    width: "100%",
    backgroundColor: "#FFFFFF",
    borderRadius: 18,
    paddingHorizontal: 18,
  },

  accountButton: {
    minHeight: 64,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },

  logoutText: {
    color: "#111111",
    fontWeight: "700",
  },

  deleteText: {
    color: "#D9534F",
    fontWeight: "800",
  },

  modalOverlay: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.35)",
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 28,
  },

  modalCard: {
    width: "100%",
    maxWidth: 390,
    backgroundColor: "#FFF5E9",
    borderRadius: 26,
    paddingHorizontal: 28,
    paddingTop: 30,
    paddingBottom: 25,
    alignItems: "center",
  },

  logoutIconCircle: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: "#E5F2E7",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 18,
  },

  warningCircle: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: "#FCE3E1",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 18,
  },

  modalTitle: {
    color: "#111111",
    fontWeight: "900",
    textAlign: "center",
  },

  modalDescription: {
    color: "#555555",
    textAlign: "center",
    marginTop: 16,
  },

  modalWarning: {
    color: "#D9534F",
    fontWeight: "800",
    textAlign: "center",
    marginTop: 10,
  },

  logoutConfirmButton: {
    width: "100%",
    height: 52,
    borderRadius: 999,
    backgroundColor: "#159326",
    alignItems: "center",
    justifyContent: "center",
    marginTop: 26,
  },

  logoutConfirmButtonText: {
    color: "#FFFFFF",
    fontWeight: "800",
  },

  logoutError: {
    color: "#D9534F",
    fontSize: 13,
    fontWeight: "600",
    marginTop: 12,
    textAlign: "center",
  },

  disabled: {
    opacity: 0.55,
  },

  deleteButton: {
    width: "100%",
    height: 52,
    borderRadius: 999,
    backgroundColor: "#D9534F",
    alignItems: "center",
    justifyContent: "center",
    marginTop: 26,
  },

  deleteButtonText: {
    color: "#FFFFFF",
    fontWeight: "800",
  },

  cancelButton: {
    width: "100%",
    height: 52,
    borderRadius: 999,
    backgroundColor: "#E5E5E5",
    alignItems: "center",
    justifyContent: "center",
    marginTop: 10,
  },

  cancelButtonText: {
    color: "#333333",
    fontWeight: "800",
  },

  pressed: {
    opacity: 0.7,
    transform: [{ scale: 0.98 }],
  },
});
