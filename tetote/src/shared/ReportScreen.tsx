import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";

import { useFontSize } from "../context/FontSizeContext";
import { useSafety } from "../context/SafetyContext";
import {
  fetchRequestOwner,
  REPORT_DESCRIPTION_MIN,
  REPORT_REASONS,
  safetyErrorMessage,
  submitReport,
  validateReport,
  type ReportReason,
  type ReportTargetType,
} from "../features/safety/client";

function firstParam(value: string | string[] | undefined): string {
  return Array.isArray(value) ? (value[0] ?? "") : (value ?? "");
}

const TARGET_TYPES: ReportTargetType[] = ["user", "request", "match", "message", "review"];

type SubmitState =
  | { status: "idle" }
  | { status: "submitting" }
  | { status: "done"; severity: "medium" | "high" }
  | { status: "error"; message: string };

export default function ReportScreen() {
  const router = useRouter();
  const { scale } = useFontSize();
  const styles = createStyles(scale);
  const { isBlocked, canBlockUser, blockUser, unblockUser } = useSafety();

  const params = useLocalSearchParams<{
    targetType?: string | string[];
    targetId?: string | string[];
    targetUserId?: string | string[];
    title?: string | string[];
  }>();
  const rawType = firstParam(params.targetType);
  const targetType: ReportTargetType = TARGET_TYPES.includes(rawType as ReportTargetType)
    ? (rawType as ReportTargetType)
    : "request";
  const targetId = firstParam(params.targetId);
  const title = firstParam(params.title);

  const [reason, setReason] = useState<ReportReason | null>(null);
  const [description, setDescription] = useState("");
  const [state, setState] = useState<SubmitState>({ status: "idle" });

  // ブロック対象の利用者。依頼を通報する場合は依頼者IDをAPIから引く。
  const [targetUserId, setTargetUserId] = useState<string>(firstParam(params.targetUserId));
  const [blockBusy, setBlockBusy] = useState(false);
  const [blockMessage, setBlockMessage] = useState<string | null>(null);

  useEffect(() => {
    if (targetUserId || targetType !== "request" || !targetId) return;
    let cancelled = false;
    void fetchRequestOwner(targetId)
      .then((owner) => {
        if (!cancelled) setTargetUserId(owner);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [targetUserId, targetType, targetId]);

  const validation = validateReport({ reason, description });
  const submittable = !validation && state.status !== "submitting" && targetId.length > 0;

  const submit = async () => {
    if (!submittable || !reason) return;
    setState({ status: "submitting" });
    try {
      const report = await submitReport({ targetType, targetId, reason, description });
      setState({ status: "done", severity: report.severity });
    } catch (error) {
      setState({ status: "error", message: safetyErrorMessage(error) });
    }
  };

  const toggleBlock = async () => {
    if (!targetUserId || blockBusy) return;
    setBlockBusy(true);
    setBlockMessage(null);
    try {
      if (isBlocked(targetUserId)) {
        await unblockUser(targetUserId);
        setBlockMessage("ブロックを解除しました");
      } else {
        await blockUser(targetUserId);
        setBlockMessage("ブロックしました。この相手の依頼やメッセージは表示されなくなります");
      }
    } catch (error) {
      setBlockMessage(safetyErrorMessage(error));
    } finally {
      setBlockBusy(false);
    }
  };

  const blocked = targetUserId ? isBlocked(targetUserId) : false;
  const blockable = targetUserId ? canBlockUser(targetUserId) : false;

  return (
    <View style={styles.screen}>
      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        <View style={styles.container}>
          <Pressable
            onPress={() => router.back()}
            style={({ pressed }) => [styles.backButton, pressed && styles.pressed]}
          >
            <Ionicons name="arrow-back" size={18} color="#111111" />
            <Text style={styles.backText}>戻る</Text>
          </Pressable>

          <Text style={styles.title}>通報する</Text>
          <Text style={styles.description}>
            危険な依頼や不適切な行為を運営に知らせます。内容は運営だけが確認します
          </Text>

          {title ? (
            <View style={styles.targetCard}>
              <Text style={styles.targetLabel}>対象</Text>
              <Text style={styles.targetTitle}>{title}</Text>
            </View>
          ) : null}

          {state.status === "done" ? (
            <View style={[styles.card, styles.noticeCard]}>
              <Ionicons name="checkmark-circle" size={22} color="#245C2D" />
              <Text style={styles.cardText}>
                通報を受け付けました。
                {state.severity === "high"
                  ? "危険性が高い内容のため、この依頼は一時的に非公開になります。"
                  : "運営が確認します。"}
              </Text>
            </View>
          ) : (
            <View style={styles.card}>
              <Text style={styles.cardTitle}>理由を選ぶ</Text>

              {REPORT_REASONS.map((item) => (
                <Pressable
                  key={item.value}
                  onPress={() => setReason(item.value)}
                  disabled={state.status === "submitting"}
                  style={({ pressed }) => [
                    styles.reasonRow,
                    reason === item.value && styles.reasonRowSelected,
                    pressed && styles.pressed,
                  ]}
                >
                  <Ionicons
                    name={reason === item.value ? "radio-button-on" : "radio-button-off"}
                    size={20}
                    color="#245C2D"
                  />
                  <Text style={styles.reasonText}>{item.label}</Text>
                </Pressable>
              ))}

              <Text style={styles.cardTitle}>状況を書く</Text>
              <Text style={styles.cardText}>
                いつ・何があったかを{REPORT_DESCRIPTION_MIN}文字以上で書いてください。相手の電話番号や住所は書かないでください
              </Text>

              <TextInput
                value={description}
                onChangeText={setDescription}
                multiline
                editable={state.status !== "submitting"}
                placeholder="例: 依頼の内容と違い、高い場所での作業を頼まれました"
                placeholderTextColor="#888888"
                style={styles.input}
              />

              {validation && description.length > 0 ? (
                <Text style={styles.hint}>{validation}</Text>
              ) : null}

              {state.status === "error" ? (
                <View style={styles.errorBox}>
                  <Ionicons name="alert-circle" size={18} color="#B4402A" />
                  <Text style={styles.errorText}>{state.message}</Text>
                </View>
              ) : null}

              <Pressable
                onPress={() => void submit()}
                disabled={!submittable}
                style={({ pressed }) => [
                  styles.primaryButton,
                  !submittable && styles.disabled,
                  pressed && styles.pressed,
                ]}
              >
                {state.status === "submitting" ? (
                  <ActivityIndicator size="small" color="#FFFFFF" />
                ) : (
                  <Ionicons name="flag" size={18} color="#FFFFFF" />
                )}
                <Text style={styles.primaryButtonText}>
                  {state.status === "error" ? "もう一度送る" : "通報を送る"}
                </Text>
              </Pressable>
            </View>
          )}

          {targetUserId ? (
            <View style={styles.card}>
              <Text style={styles.cardTitle}>この相手をブロック</Text>
              <Text style={styles.cardText}>
                ブロックすると、この相手の依頼・応募・メッセージがあなたの画面に表示されなくなります。いつでも解除できます
              </Text>

              {blockable ? (
                <Pressable
                  onPress={() => void toggleBlock()}
                  disabled={blockBusy}
                  style={({ pressed }) => [
                    blocked ? styles.secondaryButton : styles.dangerButton,
                    blockBusy && styles.disabled,
                    pressed && styles.pressed,
                  ]}
                >
                  {blockBusy ? (
                    <ActivityIndicator size="small" color={blocked ? "#111111" : "#FFFFFF"} />
                  ) : (
                    <Ionicons
                      name={blocked ? "lock-open-outline" : "ban"}
                      size={18}
                      color={blocked ? "#111111" : "#FFFFFF"}
                    />
                  )}
                  <Text style={blocked ? styles.secondaryButtonText : styles.dangerButtonText}>
                    {blocked ? "ブロックを解除する" : "ブロックする"}
                  </Text>
                </Pressable>
              ) : (
                <Text style={styles.hint}>自分自身はブロックできません</Text>
              )}

              {blockMessage ? <Text style={styles.cardText}>{blockMessage}</Text> : null}
            </View>
          ) : null}
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
    description: { marginTop: 8, textAlign: "center", color: "#666666", fontSize: 14 * scale },
    targetCard: {
      marginTop: 20,
      borderRadius: 14,
      backgroundColor: "#F1F7F1",
      paddingHorizontal: 16,
      paddingVertical: 12,
    },
    targetLabel: { color: "#666666", fontSize: 12 * scale, fontWeight: "700" },
    targetTitle: { color: "#111111", fontSize: 16 * scale, fontWeight: "800", marginTop: 2 },
    card: {
      marginTop: 20,
      width: "100%",
      borderRadius: 22,
      backgroundColor: "#FFFFFF",
      paddingHorizontal: 22,
      paddingVertical: 22,
      gap: 12,
    },
    noticeCard: { flexDirection: "row", alignItems: "center", gap: 10 },
    cardTitle: { color: "#245C2D", fontSize: 17 * scale, fontWeight: "800" },
    cardText: { flex: 1, color: "#444444", fontSize: 14 * scale, lineHeight: 21 * scale },
    reasonRow: {
      flexDirection: "row",
      alignItems: "center",
      gap: 10,
      borderRadius: 12,
      borderWidth: 1,
      borderColor: "#CFCFCF",
      paddingHorizontal: 14,
      paddingVertical: 11,
    },
    reasonRowSelected: { borderColor: "#245C2D", backgroundColor: "#F1F7F1" },
    reasonText: { flex: 1, color: "#111111", fontSize: 15 * scale, fontWeight: "700" },
    input: {
      minHeight: 120,
      borderRadius: 14,
      borderWidth: 1,
      borderColor: "#CFCFCF",
      backgroundColor: "#FFFDF9",
      paddingHorizontal: 14,
      paddingVertical: 12,
      color: "#111111",
      fontSize: 15 * scale,
      lineHeight: 22 * scale,
      textAlignVertical: "top",
    },
    hint: { color: "#B4402A", fontSize: 13 * scale, fontWeight: "700" },
    errorBox: {
      flexDirection: "row",
      alignItems: "center",
      gap: 8,
      backgroundColor: "#FDEDE9",
      borderRadius: 12,
      paddingHorizontal: 14,
      paddingVertical: 10,
    },
    errorText: { flex: 1, color: "#B4402A", fontSize: 14 * scale, fontWeight: "700" },
    primaryButton: {
      height: 54,
      borderRadius: 999,
      backgroundColor: "#159326",
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "center",
      gap: 8,
    },
    primaryButtonText: { color: "#FFFFFF", fontSize: 16 * scale, fontWeight: "800" },
    dangerButton: {
      height: 50,
      borderRadius: 999,
      backgroundColor: "#B4402A",
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "center",
      gap: 8,
    },
    dangerButtonText: { color: "#FFFFFF", fontSize: 15 * scale, fontWeight: "800" },
    secondaryButton: {
      height: 50,
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
