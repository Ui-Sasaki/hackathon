import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  View,
  Text,
  TextInput,
  StyleSheet,
  Pressable,
  ScrollView,
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
import {
  structureConfirmedRequest,
  updateStructuredDraft,
  type RequestStructuringState,
} from "../../api/request-structuring";

function maskingErrorMessage(error: unknown): string {
  if (error instanceof ApiAuthenticationError) {
    return "セッションの有効期限が切れました。もう一度ログインしてください。";
  }
  if (error instanceof ApiError && error.status === 422) {
    return "依頼内容を確認して、もう一度お試しください。";
  }
  return "マスキング結果を取得できませんでした。通信環境を確認してください。";
}

function structuringErrorMessage(error: unknown): string {
  if (error instanceof ApiAuthenticationError) {
    return "セッションの有効期限が切れました。もう一度ログインしてください。";
  }
  if (error instanceof ApiError && error.status === 422) {
    return "依頼内容を確認して、もう一度お試しください。";
  }
  return "依頼内容を構造化できませんでした。";
}

export default function RequestConfirmScreen() {
  const router = useRouter();
  const { scale } = useFontSize();
  const styles = createStyles(scale);

  const [maskingState, setMaskingState] =
    useState<MaskingPreviewState | null>(null);
  const [maskingLoading, setMaskingLoading] =
    useState(true);
  const [structuringState, setStructuringState] =
    useState<RequestStructuringState | null>(null);
  const [structuringLoading, setStructuringLoading] =
    useState(false);

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

  const handleSubmit = async () => {
    if (!canProceedAfterMasking(maskingState) || structuringLoading) return;
    setStructuringLoading(true);
    const state = await structureConfirmedRequest(maskingState);
    setStructuringState(state);
    setStructuringLoading(false);
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

            {structuringState?.status === "error" && (
              <View style={styles.structuringBox}>
                <Text style={styles.errorText}>
                  {structuringErrorMessage(structuringState.error)}
                </Text>
              </View>
            )}

            {(structuringState?.status === "draft" || structuringState?.status === "manual") && (
              <View style={styles.structuringBox}>
                <Text style={styles.maskingTitle}>
                  {structuringState.status === "manual"
                    ? "手入力で下書きを仕上げる"
                    : "AIが整理した下書き（未公開）"}
                </Text>
                {structuringState.status === "manual" && (
                  <Text style={styles.errorText}>
                    AIを利用できないため、入力内容を保持して手入力へ切り替えました。
                  </Text>
                )}
                {structuringState.additionalQuestion && (
                  <Text style={styles.questionText}>{structuringState.additionalQuestion}</Text>
                )}
                <Text style={styles.draftLabel}>タイトル</Text>
                <TextInput
                  accessibilityLabel="依頼タイトル"
                  onChangeText={(title) =>
                    setStructuringState((state) => state
                      ? updateStructuredDraft(state, { title })
                      : state)
                  }
                  style={styles.draftInput}
                  value={structuringState.draft.title}
                />
                <Text style={styles.draftLabel}>依頼内容</Text>
                <TextInput
                  accessibilityLabel="構造化した依頼内容"
                  multiline
                  onChangeText={(description) =>
                    setStructuringState((state) => state
                      ? updateStructuredDraft(state, { description })
                      : state)
                  }
                  style={[styles.draftInput, styles.draftDescription]}
                  value={structuringState.draft.description}
                />
                <Text style={styles.draftLabel}>カテゴリ</Text>
                <TextInput
                  accessibilityLabel="依頼カテゴリ"
                  onChangeText={(category) =>
                    setStructuringState((state) => state
                      ? updateStructuredDraft(state, { category })
                      : state)
                  }
                  style={styles.draftInput}
                  value={structuringState.draft.category}
                />
                <Text style={styles.unpublishedText}>
                  この下書きはまだ公開されていません。
                </Text>
              </View>
            )}

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
              disabled={
                !canProceedAfterMasking(maskingState)
                || structuringLoading
                || structuringState?.status === "draft"
                || structuringState?.status === "manual"
              }
              onPress={() => void handleSubmit()}
              style={({ pressed }) => [
                styles.submitButton,
                (!canProceedAfterMasking(maskingState)
                  || structuringLoading
                  || structuringState?.status === "draft"
                  || structuringState?.status === "manual") && styles.disabledButton,
                pressed && styles.pressed,
              ]}
            >
              {structuringLoading ? (
                <ActivityIndicator color="#FFFFFF" />
              ) : (
                <Text style={styles.submitButtonText}>
                  {structuringState?.status === "draft" || structuringState?.status === "manual"
                    ? "下書きを編集中"
                    : "AIで内容を整理する"}
                </Text>
              )}
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

    structuringBox: {
      width: "100%",
      backgroundColor: "#FFF0D6",
      borderRadius: 16,
      padding: 14,
      marginBottom: 20,
      gap: 8,
    },

    questionText: {
      color: "#6F531E",
      fontSize: 13 * scale,
      lineHeight: 19 * scale,
      fontWeight: "800",
    },

    draftLabel: {
      color: "#333333",
      fontSize: 12 * scale,
      fontWeight: "800",
    },

    draftInput: {
      width: "100%",
      minHeight: 44,
      borderWidth: 1,
      borderColor: "#E1C58F",
      borderRadius: 12,
      backgroundColor: "#FFFFFF",
      color: "#333333",
      paddingHorizontal: 12,
      paddingVertical: 10,
      fontSize: 14 * scale,
    },

    draftDescription: {
      minHeight: 90,
      textAlignVertical: "top",
    },

    unpublishedText: {
      color: "#8B651F",
      fontSize: 12 * scale,
      fontWeight: "700",
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

    pressed: {
      opacity: 0.72,
      transform: [{ scale: 0.98 }],
    },
  });
