import {
  View,
  Text,
  TextInput,
  StyleSheet,
  Pressable,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
} from "react-native";
import { useState } from "react";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";

export default function SignupScreen() {
  const router = useRouter();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] =
    useState("");

  const [showPassword, setShowPassword] =
    useState(false);

  const [error, setError] = useState("");

  const handleSignup = () => {
    setError("");

    if (!email || !password || !confirmPassword) {
      setError("すべての項目を入力してください");
      return;
    }

    if (password.length < 8) {
      setError(
        "パスワードは8文字以上にしてください"
      );
      return;
    }

    if (password !== confirmPassword) {
      setError("パスワードが一致していません");
      return;
    }

    router.replace("/onboarding/intro");
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
      <ScrollView
        contentContainerStyle={styles.content}
        keyboardShouldPersistTaps="handled"
      >
        <Pressable
          onPress={() => router.back()}
          style={styles.backButton}
        >
          <Ionicons
            name="chevron-back"
            size={28}
            color="#245C2D"
          />
        </Pressable>

        <Text style={styles.title}>
          新規登録
        </Text>

        <Text style={styles.subtitle}>
          tetoteをはじめましょう
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
                placeholder="8文字以上"
                placeholderTextColor="#AAAAAA"
                secureTextEntry={!showPassword}
                style={styles.passwordTextInput}
              />

              <Pressable
                onPress={() =>
                  setShowPassword((current) => !current)
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

          <View>
            <Text style={styles.label}>
              パスワード確認
            </Text>

            <TextInput
              value={confirmPassword}
              onChangeText={setConfirmPassword}
              placeholder="もう一度入力してください"
              placeholderTextColor="#AAAAAA"
              secureTextEntry={!showPassword}
              style={styles.input}
            />
          </View>

          {error ? (
            <Text style={styles.error}>
              {error}
            </Text>
          ) : null}

          <Pressable
            onPress={handleSignup}
            style={({ pressed }) => [
              styles.signupButton,
              pressed && styles.pressed,
            ]}
          >
            <Text style={styles.signupButtonText}>
              新規登録
            </Text>
          </Pressable>
        </View>

        <View style={styles.loginRow}>
          <Text style={styles.bottomText}>
            すでにアカウントをお持ちですか？
          </Text>

          <Pressable
            onPress={() =>
              router.replace("/auth/login")
            }
          >
            <Text style={styles.loginLink}>
              ログイン
            </Text>
          </Pressable>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: "#FFF5E9",
  },

  content: {
    flexGrow: 1,
    width: "100%",
    maxWidth: 520,
    alignSelf: "center",
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

  signupButton: {
    height: 58,
    backgroundColor: "#245C2D",
    borderRadius: 999,
    alignItems: "center",
    justifyContent: "center",
    marginTop: 10,
  },

  signupButtonText: {
    color: "#FFFFFF",
    fontSize: 17,
    fontWeight: "800",
  },

  loginRow: {
    marginTop: "auto",
    paddingTop: 50,
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

  loginLink: {
    color: "#245C2D",
    fontSize: 13,
    fontWeight: "800",
  },

  pressed: {
    opacity: 0.75,
    transform: [{ scale: 0.98 }],
  },
});