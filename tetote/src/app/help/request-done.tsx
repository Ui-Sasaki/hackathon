import { useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";

import { useFontSize } from "../../context/FontSizeContext";
import { deleteRequest } from "../../api/request-deletion";

/**
 * 依頼を出した直後の画面。
 * 公開状態を伝え、間違えたときにその場で取り消せるようにする。
 * 取消は取り返しがつかないので、ボタンを2段階（押す→本当に取り消す）にしている。
 */

type DoneParams = {
  id?: string;
  title?: string;
  status?: string;
};

type CancelPhase = "idle" | "confirming" | "cancelling" | "cancelled" | "error";

function headline(status: string | undefined): { title: string; body: string } {
  switch (status) {
    case "published":
      return {
        title: "依頼を出しました",
        body: "支援者に公開されました。応募があるとトークに表示されます。",
      };
    case "pending_review":
      return {
        title: "依頼を受け付けました",
        body: "内容の確認が終わりしだい公開されます。しばらくお待ちください。",
      };
    default:
      return {
        title: "依頼を保存しました",
        body: "まだ公開されていません。しばらくしてからもう一度お試しください。",
      };
  }
}

export function cancelErrorMessage(status: string): string {
  switch (status) {
    case "forbidden":
      return "この依頼を取り消す権限がありません。";
    case "not_found":
      return "この依頼は見つかりませんでした。";
    case "conflict":
      return "この依頼はすでに完了か取消済みのため、取り消せません。";
    default:
      return "取り消せませんでした。通信環境を確認して、もう一度お試しください。";
  }
}

export default function RequestDoneScreen() {
  const router = useRouter();
  const { scale } = useFontSize();
  const styles = createStyles(scale);
  const { id, title, status } = useLocalSearchParams<DoneParams>();

  const [phase, setPhase] = useState<CancelPhase>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const goHome = () => router.replace("/help");

  const cancelRequest = async () => {
    if (!id) return;
    setPhase("cancelling");
    setErrorMessage(null);
    const result = await deleteRequest(id, []);
    if (result.status === "deleted") {
      setPhase("cancelled");
      return;
    }
    setErrorMessage(cancelErrorMessage(result.status));
    setPhase("error");
  };

  if (phase === "cancelled") {
    return (
      <View style={styles.screen}>
        <View style={styles.container}>
          <View style={styles.iconCircleMuted}>
            <Ionicons name="close" size={44} color="#FFFFFF" />
          </View>
          <Text style={styles.title}>依頼を取り消しました</Text>
          <Text style={styles.body}>
            この依頼は支援者に表示されなくなりました。
          </Text>
          <Pressable
            onPress={goHome}
            style={({ pressed }) => [styles.primaryButton, pressed && styles.pressed]}
          >
            <Text style={styles.primaryButtonText}>ホームへ戻る</Text>
          </Pressable>
        </View>
      </View>
    );
  }

  const text = headline(status);

  return (
    <View style={styles.screen}>
      <View style={styles.container}>
        <View style={styles.iconCircle}>
          <Ionicons name="checkmark" size={44} color="#FFFFFF" />
        </View>

        <Text style={styles.title}>{text.title}</Text>
        <Text style={styles.body}>{text.body}</Text>

        {title ? (
          <View style={styles.summaryBox}>
            <Text style={styles.summaryLabel}>依頼内容</Text>
            <Text style={styles.summaryText}>{title}</Text>
          </View>
        ) : null}

        <Pressable
          onPress={goHome}
          style={({ pressed }) => [styles.primaryButton, pressed && styles.pressed]}
        >
          <Text style={styles.primaryButtonText}>ホームへ戻る</Text>
        </Pressable>

        {id ? (
          <View style={styles.cancelArea}>
            {phase === "confirming" ? (
              <>
                <Text style={styles.confirmText}>
                  本当にこの依頼を取り消しますか？
                </Text>
                <View style={styles.confirmRow}>
                  <Pressable
                    onPress={() => void cancelRequest()}
                    style={({ pressed }) => [styles.dangerButton, pressed && styles.pressed]}
                  >
                    <Text style={styles.dangerButtonText}>はい、取り消す</Text>
                  </Pressable>
                  <Pressable
                    onPress={() => setPhase("idle")}
                    style={({ pressed }) => [styles.secondaryButton, pressed && styles.pressed]}
                  >
                    <Text style={styles.secondaryButtonText}>やめる</Text>
                  </Pressable>
                </View>
              </>
            ) : phase === "cancelling" ? (
              <View style={styles.cancellingRow}>
                <ActivityIndicator size="small" color="#B3261E" />
                <Text style={styles.cancellingText}>取り消しています...</Text>
              </View>
            ) : (
              <Pressable
                onPress={() => setPhase("confirming")}
                style={({ pressed }) => [styles.cancelLink, pressed && styles.pressed]}
              >
                <Ionicons name="trash-outline" size={18} color="#B3261E" />
                <Text style={styles.cancelLinkText}>この依頼を取り消す</Text>
              </Pressable>
            )}
            {errorMessage ? <Text style={styles.errorText}>{errorMessage}</Text> : null}
          </View>
        ) : null}
      </View>
    </View>
  );
}

const createStyles = (scale: number) =>
  StyleSheet.create({
    screen: {
      flex: 1,
      backgroundColor: "#FFF5E9",
      alignItems: "center",
    },

    container: {
      flex: 1,
      width: "100%",
      maxWidth: 520,
      paddingHorizontal: 28,
      paddingTop: 72,
      paddingBottom: 28,
      alignItems: "center",
    },

    iconCircle: {
      width: 92,
      height: 92,
      borderRadius: 46,
      backgroundColor: "#159326",
      alignItems: "center",
      justifyContent: "center",
    },

    iconCircleMuted: {
      width: 92,
      height: 92,
      borderRadius: 46,
      backgroundColor: "#9E9E9E",
      alignItems: "center",
      justifyContent: "center",
    },

    title: {
      marginTop: 26,
      textAlign: "center",
      color: "#245C2D",
      fontSize: 25 * scale,
      fontWeight: "800",
    },

    body: {
      marginTop: 12,
      textAlign: "center",
      color: "#555555",
      fontSize: 15 * scale,
      lineHeight: 23 * scale,
    },

    summaryBox: {
      width: "100%",
      marginTop: 28,
      backgroundColor: "#FFFFFF",
      borderRadius: 16,
      paddingHorizontal: 18,
      paddingVertical: 16,
    },

    summaryLabel: {
      color: "#888888",
      fontSize: 13 * scale,
      fontWeight: "700",
      marginBottom: 6,
    },

    summaryText: {
      color: "#111111",
      fontSize: 17 * scale,
      fontWeight: "700",
      lineHeight: 25 * scale,
    },

    primaryButton: {
      width: "100%",
      marginTop: 32,
      height: 58,
      borderRadius: 999,
      backgroundColor: "#159326",
      alignItems: "center",
      justifyContent: "center",
    },

    primaryButtonText: {
      color: "#FFFFFF",
      fontSize: 18 * scale,
      fontWeight: "800",
    },

    cancelArea: {
      width: "100%",
      marginTop: 30,
      alignItems: "center",
    },

    cancelLink: {
      flexDirection: "row",
      alignItems: "center",
      gap: 6,
      paddingVertical: 10,
      paddingHorizontal: 14,
    },

    cancelLinkText: {
      color: "#B3261E",
      fontSize: 15 * scale,
      fontWeight: "700",
      textDecorationLine: "underline",
    },

    confirmText: {
      color: "#111111",
      fontSize: 16 * scale,
      fontWeight: "800",
      marginBottom: 14,
    },

    confirmRow: {
      width: "100%",
      flexDirection: "row",
      gap: 12,
    },

    dangerButton: {
      flex: 1,
      height: 54,
      borderRadius: 999,
      backgroundColor: "#B3261E",
      alignItems: "center",
      justifyContent: "center",
    },

    dangerButtonText: {
      color: "#FFFFFF",
      fontSize: 16 * scale,
      fontWeight: "800",
    },

    secondaryButton: {
      flex: 1,
      height: 54,
      borderRadius: 999,
      backgroundColor: "#D9D9D9",
      alignItems: "center",
      justifyContent: "center",
    },

    secondaryButtonText: {
      color: "#111111",
      fontSize: 16 * scale,
      fontWeight: "800",
    },

    cancellingRow: {
      flexDirection: "row",
      alignItems: "center",
      gap: 10,
      paddingVertical: 10,
    },

    cancellingText: {
      color: "#B3261E",
      fontSize: 15 * scale,
      fontWeight: "700",
    },

    errorText: {
      marginTop: 12,
      textAlign: "center",
      color: "#B3261E",
      fontSize: 14 * scale,
      lineHeight: 21 * scale,
    },

    pressed: {
      opacity: 0.72,
    },
  });
