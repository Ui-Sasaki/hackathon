import {
  View,
  Text,
  TextInput,
  StyleSheet,
  Pressable,
  KeyboardAvoidingView,
  Platform,
  Modal,
} from "react-native";
import { useState } from "react";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";

export default function LoginScreen() {
  const router = useRouter();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const [showPassword, setShowPassword] =
    useState(false);

  const [showSuccess, setShowSuccess] =
    useState(false);

  const [error, setError] = useState("");

  const handleLogin = () => {
    setError("");

    if (!email || !password) {
      setError("メールアドレスとパスワードを入力してください");
      return;
    }

    setShowSuccess(true);

    setTimeout(() => {
      setShowSuccess(false);
      router.replace("/helper");
    }, 2000);
  };

  return (
    <KeyboardAvoidingView
      style={styles.screen}
      behavior={
        Platform.OS === "ios"
          ? "padding"
          : undefined
      }
    >
      <View style={styles.content}>
        <Pressable
          onPress={() => router.replace("/auth")}
          style={styles.backButton}
        >
          <Ionicons
            name="chevron-back"
            size={28}
            color="#245C2D"
          />
        </Pressable>

        <Text style={styles.title}>
          ログイン
        </Text>

        <Text style={styles.subtitle}>
          おかえりなさい
        </Text>

        <View style={styles.form}>
          <View>
            <Text style={styles.label}>
              メールアドレス
            </Text>

            <TextInput
              value={email}
              onChangeText={setEmail}
              placeholder="example@email.com"
              placeholderTextColor="#AAAAAA"
              keyboardType="email-address"
              autoCapitalize="none"
              style={styles.input}
            />
          </View>

          <View>
            <Text style={styles.label}>
              パスワード
            </Text>

            <View style={styles.passwordInput}>
              <TextInput
                value={password}
                onChangeText={setPassword}
                placeholder="パスワード"
                placeholderTextColor="#AAAAAA"
                secureTextEntry={!showPassword}
                style={styles.passwordTextInput}
              />

              <Pressable
                onPress={() =>
                  setShowPassword(
                    (current) => !current
                  )
                }
              >
                <Ionicons
                  name={
                    showPassword
                      ? "eye-outline"
                      : "eye-off-outline"
                  }
                  size={22}
                  color="#777777"
                />
              </Pressable>
            </View>
          </View>

          {error ? (
            <Text style={styles.error}>
              {error}
            </Text>
          ) : null}

          <Pressable
            onPress={handleLogin}
            style={({ pressed }) => [
              styles.loginButton,
              pressed && styles.pressed,
            ]}
          >
            <Text style={styles.loginButtonText}>
              ログイン
            </Text>
          </Pressable>
        </View>

        <View style={styles.signupRow}>
          <Text style={styles.bottomText}>
            アカウントをお持ちでないですか？
          </Text>

          <Pressable
            onPress={() =>
              router.replace("/auth/signup")
            }
          >
            <Text style={styles.signupLink}>
              新規登録
            </Text>
          </Pressable>
        </View>
      </View>

      {/* SUCCESS POPUP */}
      <Modal
        visible={showSuccess}
        transparent
        animationType="fade"
        statusBarTranslucent
      >
        <View style={styles.modalOverlay}>
          <View style={styles.successModal}>
            <View style={styles.checkCircle}>
              <Ionicons
                name="checkmark"
                size={38}
                color="#FFFFFF"
              />
            </View>

            <Text style={styles.successTitle}>
              サインイン完了しました！
            </Text>

            <Text style={styles.successSubtitle}>
              おかえりなさい！
            </Text>
          </View>
        </View>
      </Modal>
    </KeyboardAvoidingView>
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
    paddingTop: 55,
    paddingBottom: 40,
  },

  backButton: {
    width: 44,
    height: 44,
    justifyContent: "center",
    marginLeft: -8,
  },

  title: {
    color: "#245C2D",
    fontSize: 30,
    fontWeight: "900",
    marginTop: 28,
  },

  subtitle: {
    color: "#777777",
    fontSize: 15,
    marginTop: 7,
  },

  form: {
    marginTop: 45,
    gap: 25,
  },

  label: {
    color: "#333333",
    fontSize: 14,
    fontWeight: "700",
    marginBottom: 9,
  },

  input: {
    width: "100%",
    height: 56,
    backgroundColor: "#FFFFFF",
    borderRadius: 16,
    paddingHorizontal: 18,
    color: "#111111",
    fontSize: 16,
  },

  passwordInput: {
    width: "100%",
    height: 56,
    backgroundColor: "#FFFFFF",
    borderRadius: 16,
    paddingHorizontal: 18,
    flexDirection: "row",
    alignItems: "center",
  },

  passwordTextInput: {
    flex: 1,
    height: "100%",
    color: "#111111",
    fontSize: 16,
  },

  error: {
    color: "#D9534F",
    fontSize: 13,
    fontWeight: "600",
  },

  loginButton: {
    height: 58,
    backgroundColor: "#245C2D",
    borderRadius: 999,
    alignItems: "center",
    justifyContent: "center",
    marginTop: 10,
  },

  loginButtonText: {
    color: "#FFFFFF",
    fontSize: 17,
    fontWeight: "800",
  },

  signupRow: {
    marginTop: "auto",
    flexDirection: "row",
    justifyContent: "center",
    alignItems: "center",
    flexWrap: "wrap",
    gap: 5,
  },

  bottomText: {
    color: "#777777",
    fontSize: 13,
  },

  signupLink: {
    color: "#245C2D",
    fontSize: 13,
    fontWeight: "800",
  },

  pressed: {
    opacity: 0.75,
    transform: [{ scale: 0.98 }],
  },

  /* SUCCESS POPUP */

  modalOverlay: {
    flex: 1,
    backgroundColor: "rgba(0, 0, 0, 0.25)",
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 28,
  },

  successModal: {
    width: "100%",
    maxWidth: 360,
    backgroundColor: "#FFF5E9",
    borderRadius: 28,
    paddingHorizontal: 24,
    paddingVertical: 38,
    alignItems: "center",

    shadowColor: "#000000",
    shadowOpacity: 0.15,
    shadowRadius: 16,
    shadowOffset: {
      width: 0,
      height: 8,
    },

    elevation: 8,
  },

  checkCircle: {
    width: 70,
    height: 70,
    borderRadius: 35,
    backgroundColor: "#245C2D",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 20,
  },

  successTitle: {
    color: "#245C2D",
    fontSize: 20,
    fontWeight: "900",
    textAlign: "center",
  },

  successSubtitle: {
    color: "#777777",
    fontSize: 14,
    fontWeight: "600",
    marginTop: 9,
    textAlign: "center",
  },
});
