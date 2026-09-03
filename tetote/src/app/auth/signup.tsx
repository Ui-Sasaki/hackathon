import {
  View,
  Text,
  TextInput,
  StyleSheet,
  Pressable,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  Modal,
} from "react-native";
import { useState } from "react";
import { useRouter } from "expo-router";
import { apiConfigurationProblem } from "../../api/config";
import { Ionicons } from "@expo/vector-icons";
import { useAuth } from "../../auth/AuthContext";

export default function SignupScreen() {
  const router = useRouter();
  const { signUp } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] =
    useState("");

  const [showPassword, setShowPassword] =
    useState(false);

  const [error, setError] = useState("");

  const [showSuccess, setShowSuccess] =
    useState(false);

  const [isSubmitting, setIsSubmitting] =
    useState(false);

  const handleSignup = async () => {
    if (isSubmitting) return;

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

    setIsSubmitting(true);

    try {
      const result = await signUp(
        email.trim(),
        password
      );

      if (!result.ok) {
        setError(result.message);
        return;
      }

      setShowSuccess(true);

      setTimeout(() => {
        setShowSuccess(false);
        router.replace("/onboarding/intro");
      }, 800);
    } catch {
      // 接続先の設定漏れは通信障害と対処が違うため、分かる場合はそちらを示す。
      setError(
        apiConfigurationProblem() ??
          "通信に失敗しました。接続を確認してもう一度お試しください"
      );
    } finally {
      setIsSubmitting(false);
    }
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
          onPress={() =>
            router.replace("/auth")
          }
          style={styles.backButton}
          disabled={isSubmitting}
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
              autoCorrect={false}
              editable={!isSubmitting}
              style={styles.input}
            />
          </View>

          <View>
            <Text style={styles.label}>
              パスワード
            </Text>

            <View
              style={styles.passwordInput}
            >
              <TextInput
                value={password}
                onChangeText={setPassword}
                placeholder="8文字以上"
                placeholderTextColor="#AAAAAA"
                secureTextEntry={
                  !showPassword
                }
                editable={!isSubmitting}
                style={
                  styles.passwordTextInput
                }
              />

              <Pressable
                onPress={() =>
                  setShowPassword(
                    (current) =>
                      !current
                  )
                }
                disabled={isSubmitting}
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
              onChangeText={
                setConfirmPassword
              }
              placeholder="もう一度入力してください"
              placeholderTextColor="#AAAAAA"
              secureTextEntry={
                !showPassword
              }
              editable={!isSubmitting}
              style={styles.input}
              onSubmitEditing={
                handleSignup
              }
            />
          </View>

          {error ? (
            <Text style={styles.error}>
              {error}
            </Text>
          ) : null}

          <Pressable
            onPress={handleSignup}
            disabled={isSubmitting}
            style={({ pressed }) => [
              styles.signupButton,
              isSubmitting &&
                styles.disabled,
              pressed &&
                !isSubmitting &&
                styles.pressed,
            ]}
          >
            <Text
              style={
                styles.signupButtonText
              }
            >
              {isSubmitting
                ? "登録中…"
                : "新規登録"}
            </Text>
          </Pressable>
        </View>

        <View style={styles.loginRow}>
          <Text
            style={styles.bottomText}
          >
            すでにアカウントをお持ちですか？
          </Text>

          <Pressable
            onPress={() =>
              router.replace(
                "/auth/login"
              )
            }
            disabled={isSubmitting}
          >
            <Text
              style={[
                styles.loginLink,
                isSubmitting &&
                  styles.disabledText,
              ]}
            >
              ログイン
            </Text>
          </Pressable>
        </View>
      </ScrollView>

      <Modal
        visible={showSuccess}
        transparent
        animationType="fade"
        statusBarTranslucent
      >
        <View
          style={styles.modalOverlay}
        >
          <View
            style={styles.successModal}
          >
            <View
              style={styles.checkCircle}
            >
              <Ionicons
                name="checkmark"
                size={38}
                color="#FFFFFF"
              />
            </View>

            <Text
              style={
                styles.successTitle
              }
            >
              サインアップ完了しました！
            </Text>

            <Text
              style={
                styles.successSubtitle
              }
            >
              tetoteへようこそ
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
    transform: [
      {
        scale: 0.98,
      },
    ],
  },

  disabled: {
    opacity: 0.55,
  },

  disabledText: {
    opacity: 0.55,
  },

  modalOverlay: {
    flex: 1,
    backgroundColor:
      "rgba(0, 0, 0, 0.25)",
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