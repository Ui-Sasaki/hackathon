import { Stack, usePathname, useRouter } from "expo-router";
import { useEffect } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";
import { RequestsProvider } from "../context/RequestsContext";
import { ModeProvider } from "../context/ModeContext";
import { FontSizeProvider } from "../context/FontSizeContext";
import { AuthProvider, useAuth } from "../auth/AuthContext";
import { warmUpApi } from "../api/client";
import { SafetyProvider } from "../context/SafetyContext";

function AuthenticatedStack() {
  const { refreshProfile, status } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const isAuthRoute = pathname.startsWith("/auth");
  const needsAuthentication = status === "unauthenticated";

  useEffect(() => {
    if (status === "loading") return;
    if (needsAuthentication && !isAuthRoute) {
      const returnTo = encodeURIComponent(pathname || "/helper");
      router.replace(`/auth/login?returnTo=${returnTo}`);
    }
  }, [isAuthRoute, needsAuthentication, pathname, router, status]);

  if (!isAuthRoute && status === "error") {
    return (
      <View style={styles.loading}>
        <Text style={styles.errorTitle}>認証状態を確認できませんでした</Text>
        <Text style={styles.errorMessage}>通信環境を確認して、もう一度お試しください。</Text>
        <Pressable
          accessibilityRole="button"
          onPress={() => void refreshProfile().catch(() => undefined)}
          style={({ pressed }) => [styles.retryButton, pressed && styles.pressed]}
        >
          <Text style={styles.retryButtonText}>再試行</Text>
        </Pressable>
      </View>
    );
  }

  if (!isAuthRoute && (status === "loading" || needsAuthentication)) {
    return (
      <View style={styles.loading}>
        <ActivityIndicator size="large" color="#245C2D" />
      </View>
    );
  }

  return <Stack screenOptions={{ headerShown: false }} />;
}

export default function RootLayout() {
  // 停止しているサーバーを先に起こす。利用者が登録や送信を押すころには
  // 起動が終わっている状態にして、初回アクセスの失敗を減らす。
  useEffect(() => {
    void warmUpApi();
  }, []);

  return (
    <AuthProvider>
      <ModeProvider>
        <FontSizeProvider>
          <RequestsProvider>
            <SafetyProvider>
              <AuthenticatedStack />
            </SafetyProvider>
          </RequestsProvider>
        </FontSizeProvider>
      </ModeProvider>
    </AuthProvider>
  );
}

const styles = StyleSheet.create({
  loading: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#FFF5E9",
  },
  errorTitle: {
    color: "#2D3A2E",
    fontSize: 18,
    fontWeight: "700",
  },
  errorMessage: {
    color: "#586259",
    fontSize: 14,
    marginTop: 8,
  },
  retryButton: {
    backgroundColor: "#245C2D",
    borderRadius: 8,
    marginTop: 20,
    paddingHorizontal: 24,
    paddingVertical: 12,
  },
  retryButtonText: {
    color: "#FFFFFF",
    fontSize: 15,
    fontWeight: "700",
  },
  pressed: {
    opacity: 0.75,
  },
});
