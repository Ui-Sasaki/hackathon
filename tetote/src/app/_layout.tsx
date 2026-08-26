import { Stack, usePathname, useRouter } from "expo-router";
import { useEffect } from "react";
import { ActivityIndicator, StyleSheet, View } from "react-native";
import { RequestsProvider } from "../context/RequestsContext";
import { ModeProvider } from "../context/ModeContext";
import { FontSizeProvider } from "../context/FontSizeContext";
import { AuthProvider, useAuth } from "../auth/AuthContext";

function AuthenticatedStack() {
  const { status } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const isAuthRoute = pathname.startsWith("/auth");
  const needsAuthentication =
    status === "unauthenticated" || status === "error";

  useEffect(() => {
    if (status === "loading") return;
    if (needsAuthentication && !isAuthRoute) {
      const returnTo = encodeURIComponent(pathname || "/helper");
      router.replace(`/auth/login?returnTo=${returnTo}`);
    }
  }, [isAuthRoute, needsAuthentication, pathname, router, status]);

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
  return (
    <AuthProvider>
      <ModeProvider>
        <FontSizeProvider>
          <RequestsProvider>
            <AuthenticatedStack />
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
});
