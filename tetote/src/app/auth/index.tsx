import {
  View,
  Text,
  StyleSheet,
  Pressable,
  Image,
} from "react-native";
import { useRouter } from "expo-router";

import NameLogo from "../../../assets/onboarding_asset/name.svg";

export default function AuthScreen() {
  const router = useRouter();

  return (
    <View style={styles.screen}>
      <View style={styles.content}>
        <View style={styles.logoWrapper}>
          <NameLogo
            width={180}
            height={90}
          />
        </View>

        <View style={styles.textArea}>
          <Text style={styles.title}>
            はじめまして。
          </Text>

          <Text style={styles.subtitle}>
            小さな「助けて」と「手伝いたい」を、
            {"\n"}
            もっと近くに。
          </Text>
        </View>

        <View style={styles.mascotArea}>
          <Image
            source={require("../../../assets/onboarding_asset/c1.png")}
            style={styles.mascot}
            resizeMode="contain"
          />
        </View>

        <View style={styles.buttons}>
          <Pressable
            onPress={() => router.push("/auth/signup")}
            style={({ pressed }) => [
              styles.primaryButton,
              pressed && styles.pressed,
            ]}
          >
            <Text style={styles.primaryButtonText}>
              新規登録
            </Text>
          </Pressable>

          <Pressable
            onPress={() => router.push("/auth/login")}
            style={({ pressed }) => [
              styles.secondaryButton,
              pressed && styles.pressed,
            ]}
          >
            <Text style={styles.secondaryButtonText}>
              ログイン
            </Text>
          </Pressable>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: "#FFF5E9",
    alignItems: "center",
  },

  content: {
    flex: 1,
    width: "100%",
    maxWidth: 520,
    paddingHorizontal: 28,
    paddingTop: 70,
    paddingBottom: 40,
  },

  logoWrapper: {
    alignItems: "center",
    justifyContent: "center",
  },

  textArea: {
    marginTop: 55,
    alignItems: "center",
  },

  title: {
    color: "#245C2D",
    fontSize: 30,
    fontWeight: "900",
    textAlign: "center",
  },

  subtitle: {
    color: "#555555",
    fontSize: 16,
    lineHeight: 27,
    fontWeight: "600",
    marginTop: 14,
    textAlign: "center",
  },

  mascotArea: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    minHeight: 180,
  },

  mascot: {
    width: 230,
    height: 230,
  },

  buttons: {
    gap: 12,
  },

  primaryButton: {
    height: 54,
    borderRadius: 999,
    backgroundColor: "#245C2D",
    alignItems: "center",
    justifyContent: "center",
  },

  primaryButtonText: {
    color: "#FFFFFF",
    fontSize: 17,
    fontWeight: "800",
  },

  secondaryButton: {
    height: 54,
    borderRadius: 999,
    borderWidth: 2,
    borderColor: "#245C2D",
    alignItems: "center",
    justifyContent: "center",
  },

  secondaryButtonText: {
    color: "#245C2D",
    fontSize: 17,
    fontWeight: "800",
  },

  pressed: {
    opacity: 0.75,
    transform: [{ scale: 0.98 }],
  },
});