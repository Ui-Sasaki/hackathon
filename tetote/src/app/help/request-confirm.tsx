import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  View,
  Text,
  StyleSheet,
  Pressable,
  ScrollView,
  Modal,
} from "react-native";
import {
  useLocalSearchParams,
  useRouter,
} from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useFontSize } from "../../context/FontSizeContext";
import { ApiAuthenticationError, ApiError } from "../../api/errors";
import {
  canProceedAfterMasking,
  confirmMaskingPreview,
  previewRequestMasking,
  type MaskingPreviewState,
} from "../../api/request-masking";

function maskingErrorMessage(error: unknown): string {
  if (error instanceof ApiAuthenticationError) {
    return "セッションの有効期限が切れました。もう一度ログインしてください。";
  }
  if (error instanceof ApiError && error.status === 422) {
    return "依頼内容を確認して、もう一度お試しください。";
  }
  return "マスキング結果を取得できませんでした。通信環境を確認してください。";
}

export default function RequestConfirmScreen() {
  const router = useRouter();
  const { scale } = useFontSize();
  const styles = createStyles(scale);

  const [successVisible, setSuccessVisible] =
    useState(false);
  const [maskingState, setMaskingState] =
    useState<MaskingPreviewState | null>(null);
  const [maskingLoading, setMaskingLoading] =
    useState(true);

  const {
    content,
    location,
    time,
    deadline,
  } = useLocalSearchParams<{
    content?: string;
    location?: string;
    time?: string;
    deadline?: string;
  }>();

  const retryMaskingPreview = async () => {
    setMaskingLoading(true);
    setMaskingState(null);
    const state = await previewRequestMasking(content ?? "");
    setMaskingState(state);
    setMaskingLoading(false);
  };

  useEffect(() => {
    let active = true;
    void previewRequestMasking(content ?? "").then((state) => {
      if (!active) return;
      setMaskingState(state);
      setMaskingLoading(false);
    });
    return () => {
      active = false;
    };
  }, [content]);

  const handleSubmit = () => {
    if (!canProceedAfterMasking(maskingState)) return;
    setSuccessVisible(true);

    setTimeout(() => {
      setSuccessVisible(false);
      router.replace("/help");
    }, 2000);
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
              onPress={() => router.back()}
              style={({ pressed }) => [
                styles.backButton,
                pressed && styles.pressed,
              ]}
            >
              <Ionicons
                name="arrow-back"
                size={21}
                color="#111111"
              />

              <Text style={styles.backText}>
                戻る
              </Text>
            </Pressable>

            <Text style={styles.title}>
              依頼確認
            </Text>

            <Ionicons
              name="hand-left"
              size={42}
              color="#191600"
            />
          </View>

          <View style={styles.confirmCard}>
            <Text style={styles.sectionTitle}>
              依頼内容
            </Text>

            <View style={styles.infoBox}>
              <Text style={styles.infoText}>
                {maskingState?.preview?.maskedText ?? content ?? "未入力"}
              </Text>
            </View>

            <View style={styles.maskingBox}>
              <Text style={styles.maskingTitle}>個人情報のマスキング確認</Text>
              {maskingLoading && <ActivityIndicator color="#D89B31" />}
              {maskingState?.status === "error" && (
                <>
                  <Text style={styles.errorText}>
                    {maskingErrorMessage(maskingState.error)}
                  </Text>
                  <Pressable onPress={() => void retryMaskingPreview()} style={styles.retryButton}>
                    <Text style={styles.retryButtonText}>再試行する</Text>
                  </Pressable>
                </>
              )}
              {maskingState?.preview && (
                <>
                  <Text style={styles.maskingMeta}>
                    検出種別: {maskingState.preview.detections.map((item) => item.type).join("、") || "なし"}
                  </Text>
                  <Text style={styles.maskingMeta}>
                    ルール版: {maskingState.preview.ruleVersion}
                  </Text>
                  <Pressable
                    disabled={maskingState.status === "confirmed"}
                    onPress={() => setMaskingState(confirmMaskingPreview(maskingState))}
                    style={[
                      styles.maskingConfirmButton,
                      maskingState.status === "confirmed" && styles.confirmedButton,
                    ]}
                  >
                    <Text style={styles.maskingConfirmText}>
                      {maskingState.status === "confirmed"
                        ? "マスキング結果を確認済み"
                        : "マスキング結果を確認しました"}
                    </Text>
                  </Pressable>
                </>
              )}
            </View>

            <Text style={styles.sectionTitle}>
              場所
            </Text>

            <View style={styles.infoBox}>
              <Text style={styles.infoText}>
                {location || "未入力"}
              </Text>
            </View>

            <Text style={styles.sectionTitle}>
              必要な時間
            </Text>

            <View style={styles.smallInfoBox}>
              <Text style={styles.infoText}>
                {time || "未選択"}
              </Text>
            </View>

            <Text style={styles.sectionTitle}>
              依頼期限
            </Text>

            <View style={styles.smallInfoBox}>
              <Text style={styles.infoText}>
                {deadline || "未選択"}
              </Text>
            </View>

            <View style={styles.noticeBox}>
              <Ionicons
                name="information-circle-outline"
                size={22}
                color="#D89B31"
              />

              <Text style={styles.noticeText}>
                内容を確認して、問題がなければ依頼してください
              </Text>
            </View>

            <Pressable
              disabled={!canProceedAfterMasking(maskingState)}
              onPress={handleSubmit}
              style={({ pressed }) => [
                styles.submitButton,
                !canProceedAfterMasking(maskingState) && styles.disabledButton,
                pressed && styles.pressed,
              ]}
            >
              <Text style={styles.submitButtonText}>
                依頼する
              </Text>
            </Pressable>

            <Pressable
              onPress={() => router.back()}
              style={({ pressed }) => [
                styles.editButton,
                pressed && styles.pressed,
              ]}
            >
              <Text style={styles.editButtonText}>
                内容を修正する
              </Text>
            </Pressable>
          </View>
        </View>
      </ScrollView>

      <Modal
        visible={successVisible}
        transparent
        animationType="fade"
        statusBarTranslucent
      >
        <View style={styles.modalOverlay}>
          <View style={styles.successModal}>
            <View style={styles.successIcon}>
              <Ionicons
                name="checkmark"
                size={40}
                color="#FFFFFF"
              />
            </View>

            <Text style={styles.successTitle}>
              依頼完了しました！
            </Text>

            <Text style={styles.successText}>
              応募が来るまでお待ちください
            </Text>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const createStyles = (scale: number) =>
  StyleSheet.create({
    screen: {
      flex: 1,
      backgroundColor: "#FFF5E9",
    },

    scrollContent: {
      flexGrow: 1,
      alignItems: "center",
      paddingBottom: 30,
    },

    container: {
      width: "100%",
      maxWidth: 520,
      paddingHorizontal: 28,
      paddingTop: 38,
    },

    header: {
      width: "100%",
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      marginBottom: 18,
    },

    backButton: {
      minHeight: 38,
      paddingHorizontal: 12,
      borderRadius: 999,
      backgroundColor: "#D9D9D9",
      flexDirection: "row",
      alignItems: "center",
      gap: 3,
    },

    backText: {
      color: "#111111",
      fontSize: 14 * scale,
      fontWeight: "800",
    },

    title: {
      color: "#111111",
      fontSize: 20 * scale,
      fontWeight: "900",
    },

    confirmCard: {
      width: "100%",
      borderWidth: 2,
      borderColor: "#F2A329",
      borderRadius: 28,
      paddingHorizontal: 22,
      paddingTop: 24,
      paddingBottom: 24,
    },

    sectionTitle: {
      color: "#111111",
      fontSize: 15 * scale,
      fontWeight: "900",
      marginBottom: 8,
    },

    maskingBox: {
      width: "100%",
      backgroundColor: "#FFF0D6",
      borderRadius: 16,
      padding: 14,
      marginBottom: 20,
      gap: 8,
    },

    maskingTitle: {
      color: "#8B651F",
      fontSize: 14 * scale,
      fontWeight: "900",
    },

    maskingMeta: {
      color: "#6F531E",
      fontSize: 12 * scale,
      lineHeight: 18 * scale,
      fontWeight: "700",
    },

    errorText: {
      color: "#A52A2A",
      fontSize: 12 * scale,
      lineHeight: 18 * scale,
      fontWeight: "700",
    },

    retryButton: {
      alignSelf: "flex-start",
      borderRadius: 999,
      backgroundColor: "#D9D9D9",
      paddingHorizontal: 14,
      paddingVertical: 8,
    },

    retryButtonText: {
      color: "#333333",
      fontSize: 12 * scale,
      fontWeight: "800",
    },

    maskingConfirmButton: {
      minHeight: 42,
      borderRadius: 999,
      backgroundColor: "#D89B31",
      alignItems: "center",
      justifyContent: "center",
      paddingHorizontal: 12,
    },

    confirmedButton: {
      backgroundColor: "#6E8B3D",
    },

    maskingConfirmText: {
      color: "#FFFFFF",
      fontSize: 13 * scale,
      fontWeight: "800",
    },

    infoBox: {
      width: "100%",
      minHeight: 74,
      borderRadius: 18,
      backgroundColor: "#FFFFFF",
      paddingHorizontal: 16,
      paddingVertical: 14,
      justifyContent: "center",
      marginBottom: 20,
    },

    smallInfoBox: {
      width: "100%",
      minHeight: 48,
      borderRadius: 999,
      backgroundColor: "#FFFFFF",
      paddingHorizontal: 16,
      justifyContent: "center",
      marginBottom: 20,
    },

    infoText: {
      color: "#333333",
      fontSize: 14 * scale,
      lineHeight: 21 * scale,
      fontWeight: "700",
    },

    noticeBox: {
      width: "100%",
      backgroundColor: "#FFF0D6",
      borderRadius: 16,
      paddingHorizontal: 14,
      paddingVertical: 12,
      flexDirection: "row",
      alignItems: "center",
      gap: 9,
      marginTop: 4,
    },

    noticeText: {
      flex: 1,
      color: "#8B651F",
      fontSize: 12 * scale,
      lineHeight: 18 * scale,
      fontWeight: "700",
    },

    submitButton: {
      width: "76%",
      height: 52,
      borderRadius: 999,
      backgroundColor: "#D89B31",
      alignItems: "center",
      justifyContent: "center",
      alignSelf: "center",
      marginTop: 24,
    },

    submitButtonText: {
      color: "#FFFFFF",
      fontSize: 20 * scale,
      fontWeight: "600",
    },

    disabledButton: {
      opacity: 0.45,
    },

    editButton: {
      width: "76%",
      height: 48,
      borderRadius: 999,
      backgroundColor: "#D9D9D9",
      alignItems: "center",
      justifyContent: "center",
      alignSelf: "center",
      marginTop: 10,
    },

    editButtonText: {
      color: "#333333",
      fontSize: 14 * scale,
      fontWeight: "800",
    },

    modalOverlay: {
      flex: 1,
      backgroundColor: "rgba(0, 0, 0, 0.3)",
      alignItems: "center",
      justifyContent: "center",
      paddingHorizontal: 28,
    },

    successModal: {
      width: "100%",
      maxWidth: 360,
      backgroundColor: "#FFF5E9",
      borderRadius: 28,
      paddingHorizontal: 28,
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

    successIcon: {
      width: 70,
      height: 70,
      borderRadius: 35,
      backgroundColor: "#D89B31",
      alignItems: "center",
      justifyContent: "center",
      marginBottom: 20,
    },

    successTitle: {
      color: "#D89B31",
      fontSize: 21 * scale,
      fontWeight: "900",
      textAlign: "center",
    },

    successText: {
      color: "#555555",
      fontSize: 14 * scale,
      fontWeight: "700",
      textAlign: "center",
      marginTop: 10,
    },

    pressed: {
      opacity: 0.72,
      transform: [{ scale: 0.98 }],
    },
  });
