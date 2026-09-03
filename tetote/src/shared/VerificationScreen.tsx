import { useReducer, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  Pressable,
  ScrollView,
  ActivityIndicator,
} from "react-native";
import { usePathname, useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import * as ImagePicker from "expo-image-picker";

import { useFontSize } from "../context/FontSizeContext";
import { useAuth } from "../auth/AuthContext";
import {
  DocumentImage,
  DocumentImageType,
  VerificationMethod,
  submitVerification,
  uploadVerificationDocument,
} from "../verification/client";
import {
  canSubmit,
  describeFailure,
  initialSubmissionState,
  isBusy,
  submissionReducer,
} from "../verification/state";

const VERIFICATION_LABELS: Record<string, string> = {
  unverified: "未申請",
  pending: "審査中",
  approved: "確認済み",
  rejected: "却下",
  expired: "期限切れ",
};

const SUPPORTED_TYPES: DocumentImageType[] = ["image/jpeg", "image/png"];

export default function VerificationScreen() {
  const router = useRouter();
  const pathname = usePathname();
  const { scale } = useFontSize();
  const styles = createStyles(scale);
  const { profile, refreshProfile } = useAuth();

  const [state, dispatch] = useReducer(submissionReducer, initialSubmissionState);
  const [method, setMethod] = useState<VerificationMethod>("university_email");
  const [document, setDocument] = useState<DocumentImage | null>(null);
  const [documentLabel, setDocumentLabel] = useState<string | null>(null);
  const [pickerMessage, setPickerMessage] = useState<string | null>(null);

  const verificationStatus = profile?.verificationStatus ?? "unverified";
  const emailVerified = profile?.emailVerified ?? false;

  const submittable = canSubmit({
    state,
    verificationStatus,
    method,
    hasDocument: document !== null,
  });

  const goBack = () => {
    router.replace(pathname.startsWith("/help") ? "/help/profile" : "/helper/profile");
  };

  const pickDocument = async () => {
    setPickerMessage(null);
    const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permission.granted) {
      setPickerMessage("写真へのアクセスが許可されませんでした");
      return;
    }

    const picked = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      allowsEditing: false,
      quality: 0.8,
    });
    if (picked.canceled || picked.assets.length === 0) {
      return;
    }

    // 端末ローカルURIはここで実体へ変換し、URIそのものはAPIへ渡さない。
    const asset = picked.assets[0];
    const blob = await (await fetch(asset.uri)).blob();
    const contentType = blob.type as DocumentImageType;
    if (!SUPPORTED_TYPES.includes(contentType)) {
      setPickerMessage("JPEGまたはPNGの画像を選んでください");
      return;
    }

    setDocument({
      data: blob,
      contentType,
      byteSize: blob.size,
      fileName: asset.fileName ?? undefined,
    });
    setDocumentLabel(`${contentType === "image/png" ? "PNG" : "JPEG"}・${Math.ceil(blob.size / 1024)}KB`);
  };

  const submit = async () => {
    if (!submittable) {
      return;
    }
    dispatch({ type: "upload_started" });
    try {
      let uploadId: string | undefined;
      if (method === "student_card" && document) {
        uploadId = await uploadVerificationDocument(document);
      }
      dispatch({ type: "upload_finished" });
      await submitVerification({ method, uploadId });
      dispatch({ type: "succeeded" });
      // 申請後の状態はサーバーを正本として取り直す。
      await refreshProfile().catch(() => undefined);
    } catch (error) {
      // 画像の中身とファイル名はログへ出さない。理由コードと文言だけを扱う。
      const { code, message } = describeFailure(error);
      dispatch({ type: "failed", code, message });
    }
  };

  return (
    <View style={styles.screen}>
      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        <View style={styles.container}>
          <Pressable
            onPress={goBack}
            style={({ pressed }) => [styles.backButton, pressed && styles.pressed]}
          >
            <Ionicons name="arrow-back" size={18} color="#111111" />
            <Text style={styles.backText}>戻る</Text>
          </Pressable>

          <Text style={styles.title}>本人確認</Text>
          <Text style={styles.description}>
            大学生であることを確認します。確認できると依頼者に安心してもらえます
          </Text>

          <View style={styles.card}>
            <Text style={styles.cardTitle}>いまの状態</Text>

            <View style={styles.statusRow}>
              <Text style={styles.statusLabel}>メールアドレスの確認</Text>
              <Text style={styles.statusValue}>{emailVerified ? "確認済み" : "未確認"}</Text>
            </View>

            <View style={styles.statusRow}>
              <Text style={styles.statusLabel}>本人確認</Text>
              <Text style={styles.statusValue}>
                {VERIFICATION_LABELS[verificationStatus] ?? "未申請"}
              </Text>
            </View>
          </View>

          {verificationStatus === "pending" && (
            <View style={[styles.card, styles.noticeCard]}>
              <Ionicons name="time-outline" size={22} color="#245C2D" />
              <Text style={styles.cardText}>
                審査中です。結果が出るまでお待ちください。
              </Text>
            </View>
          )}

          {verificationStatus === "approved" && (
            <View style={[styles.card, styles.noticeCard]}>
              <Ionicons name="checkmark-circle" size={22} color="#245C2D" />
              <Text style={styles.cardText}>本人確認は完了しています。</Text>
            </View>
          )}

          {verificationStatus !== "pending" && verificationStatus !== "approved" && (
            <View style={styles.card}>
              <Text style={styles.cardTitle}>申請の方法を選ぶ</Text>

              <Pressable
                onPress={() => setMethod("university_email")}
                style={({ pressed }) => [
                  styles.methodButton,
                  method === "university_email" && styles.methodButtonSelected,
                  pressed && styles.pressed,
                ]}
              >
                <Ionicons
                  name={method === "university_email" ? "radio-button-on" : "radio-button-off"}
                  size={20}
                  color="#245C2D"
                />
                <Text style={styles.methodText}>大学のメールアドレスで確認する</Text>
              </Pressable>

              <Pressable
                onPress={() => setMethod("student_card")}
                style={({ pressed }) => [
                  styles.methodButton,
                  method === "student_card" && styles.methodButtonSelected,
                  pressed && styles.pressed,
                ]}
              >
                <Ionicons
                  name={method === "student_card" ? "radio-button-on" : "radio-button-off"}
                  size={20}
                  color="#245C2D"
                />
                <Text style={styles.methodText}>学生証の写真を送る</Text>
              </Pressable>

              {method === "student_card" && (
                <View style={styles.documentArea}>
                  <Text style={styles.cardText}>
                    学生証の写真はJPEGまたはPNG、10MBまでです。審査以外には使いません。
                  </Text>

                  <Pressable
                    onPress={pickDocument}
                    disabled={isBusy(state)}
                    style={({ pressed }) => [
                      styles.secondaryButton,
                      isBusy(state) && styles.disabled,
                      pressed && styles.pressed,
                    ]}
                  >
                    <Ionicons name="image-outline" size={20} color="#111111" />
                    <Text style={styles.secondaryButtonText}>
                      {document ? "写真を選び直す" : "写真を選ぶ"}
                    </Text>
                  </Pressable>

                  {documentLabel && (
                    <Text style={styles.documentLabel}>選択中: {documentLabel}</Text>
                  )}

                  {pickerMessage && <Text style={styles.errorText}>{pickerMessage}</Text>}
                </View>
              )}

              <Pressable
                onPress={submit}
                disabled={!submittable}
                style={({ pressed }) => [
                  styles.primaryButton,
                  !submittable && styles.disabled,
                  pressed && styles.pressed,
                ]}
              >
                <Text style={styles.primaryButtonText}>この方法で申請する</Text>
              </Pressable>

              {isBusy(state) && (
                <View style={styles.busyRow}>
                  <ActivityIndicator size="small" color="#245C2D" />
                  <Text style={styles.cardText}>
                    {state.status === "uploading" ? "写真を送っています..." : "申請しています..."}
                  </Text>
                </View>
              )}
            </View>
          )}

          {state.status === "submitted" && (
            <View style={[styles.card, styles.noticeCard]}>
              <Ionicons name="checkmark-circle" size={22} color="#245C2D" />
              <Text style={styles.cardText}>申請を受け付けました。結果をお待ちください。</Text>
            </View>
          )}

          {state.status === "error" && (
            <View style={[styles.card, styles.errorCard]}>
              <View style={styles.cardHeader}>
                <Ionicons name="alert-circle" size={22} color="#B4402A" />
                <Text style={[styles.cardTitle, styles.errorTitle]}>申請できませんでした</Text>
              </View>

              <Text style={styles.cardText}>{state.message}</Text>

              <Pressable
                onPress={() => dispatch({ type: "retry" })}
                style={({ pressed }) => [styles.secondaryButton, pressed && styles.pressed]}
              >
                <Ionicons name="refresh" size={20} color="#111111" />
                <Text style={styles.secondaryButtonText}>もう一度試す</Text>
              </Pressable>
            </View>
          )}
        </View>
      </ScrollView>
    </View>
  );
}

const createStyles = (scale: number) =>
  StyleSheet.create({
    screen: { flex: 1, backgroundColor: "#FFF5E9", alignItems: "center" },

    scrollContent: { flexGrow: 1, alignItems: "center" },

    container: {
      flex: 1,
      width: "100%",
      maxWidth: 520,
      paddingHorizontal: 28,
      paddingTop: 42,
      paddingBottom: 28,
    },

    backButton: {
      alignSelf: "flex-start",
      height: 42,
      paddingHorizontal: 14,
      borderRadius: 999,
      backgroundColor: "#D9D9D9",
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "center",
      gap: 4,
    },

    backText: { color: "#111111", fontSize: 15 * scale, fontWeight: "800" },

    title: {
      marginTop: 28,
      textAlign: "center",
      color: "#245C2D",
      fontSize: 25 * scale,
      fontWeight: "800",
    },

    description: {
      marginTop: 8,
      textAlign: "center",
      color: "#666666",
      fontSize: 14 * scale,
    },

    card: {
      marginTop: 22,
      width: "100%",
      borderRadius: 22,
      backgroundColor: "#FFFFFF",
      paddingHorizontal: 22,
      paddingVertical: 22,
      gap: 14,
    },

    noticeCard: { flexDirection: "row", alignItems: "center", gap: 10 },

    errorCard: { backgroundColor: "#FDEDE9" },

    cardHeader: { flexDirection: "row", alignItems: "center", gap: 8 },

    cardTitle: { color: "#245C2D", fontSize: 17 * scale, fontWeight: "800" },

    errorTitle: { color: "#B4402A" },

    cardText: {
      flex: 1,
      color: "#444444",
      fontSize: 14 * scale,
      lineHeight: 21 * scale,
    },

    statusRow: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
    },

    statusLabel: { color: "#444444", fontSize: 14 * scale },

    statusValue: { color: "#111111", fontSize: 15 * scale, fontWeight: "800" },

    methodButton: {
      flexDirection: "row",
      alignItems: "center",
      gap: 10,
      borderRadius: 14,
      borderWidth: 1,
      borderColor: "#CFCFCF",
      paddingHorizontal: 14,
      paddingVertical: 14,
    },

    methodButtonSelected: { borderColor: "#245C2D", backgroundColor: "#F1F7F1" },

    methodText: { flex: 1, color: "#111111", fontSize: 15 * scale, fontWeight: "700" },

    documentArea: { gap: 12 },

    documentLabel: { color: "#245C2D", fontSize: 13 * scale, fontWeight: "700" },

    errorText: { color: "#B4402A", fontSize: 13 * scale, fontWeight: "700" },

    busyRow: { flexDirection: "row", alignItems: "center", gap: 9 },

    primaryButton: {
      width: "100%",
      height: 54,
      borderRadius: 999,
      backgroundColor: "#159326",
      alignItems: "center",
      justifyContent: "center",
    },

    primaryButtonText: { color: "#FFFFFF", fontSize: 16 * scale, fontWeight: "800" },

    secondaryButton: {
      width: "100%",
      height: 48,
      borderRadius: 999,
      backgroundColor: "#D9D9D9",
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "center",
      gap: 8,
    },

    secondaryButtonText: { color: "#111111", fontSize: 15 * scale, fontWeight: "800" },

    disabled: { opacity: 0.5 },

    pressed: { opacity: 0.72, transform: [{ scale: 0.97 }] },
  });
