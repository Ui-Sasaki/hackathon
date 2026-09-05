import { useEffect, useState } from "react";
import { useLocalSearchParams, useRouter } from "expo-router";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import {
  applicationErrorMessage,
  createApplication,
  type Application,
  withdrawalErrorMessage,
  withdrawApplication,
} from "../../features/applications/client";
import {
  getRequest,
  requestListErrorMessage,
  type PublicRequest,
} from "../../features/requests/client";

function firstParam(value: string | string[] | undefined): string {
  return Array.isArray(value) ? value[0] ?? "" : value ?? "";
}

export default function ApplicationScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{
    requestId?: string | string[];
    title?: string | string[];
    description?: string | string[];
  }>();
  const requestId = firstParam(params.requestId);
  const fallbackTitle = firstParam(params.title);
  const fallbackDescription = firstParam(params.description);
  const [request, setRequest] = useState<PublicRequest | null>(null);
  const [requestLoading, setRequestLoading] = useState(requestId.length > 0);
  const [requestError, setRequestError] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [availableAt, setAvailableAt] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [application, setApplication] = useState<Application | null>(null);
  const [withdrawing, setWithdrawing] = useState(false);

  const canSubmit = requestId.length > 0 && message.trim().length > 0 && availableAt.length > 0;
  const title = request?.title ?? fallbackTitle;
  const description = request?.description ?? fallbackDescription;

  useEffect(() => {
    // requestId が無いときは初期状態（読み込みなし）のまま何もしない。
    if (!requestId) return;
    let active = true;
    // 読み込み開始の状態更新も同じ非同期の流れに乗せ、effect 本体で同期的に
    // setState しない（React の lint: set-state-in-effect）。
    void Promise.resolve()
      .then(() => {
        if (!active) return null;
        setRequestLoading(true);
        setRequestError(null);
        return getRequest(requestId);
      })
      .then((item) => {
        if (!active || !item) return;
        setRequest(item);
        setAvailableAt((current) => current || item.scheduledAt);
        setRequestLoading(false);
      })
      .catch((loadError: unknown) => {
        if (!active) return;
        setRequestError(requestListErrorMessage(loadError));
        setRequestLoading(false);
      });
    return () => {
      active = false;
    };
  }, [requestId]);

  const handleSubmit = async () => {
    if (!canSubmit || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const created = await createApplication(requestId, {
        message: message.trim(),
        availableAt,
      });
      setApplication(created);
    } catch (submitError) {
      setError(applicationErrorMessage(submitError));
    } finally {
      setSubmitting(false);
    }
  };

  const handleWithdraw = async () => {
    if (!application || application.status !== "applied" || withdrawing) return;
    setWithdrawing(true);
    setError(null);
    try {
      const withdrawn = await withdrawApplication(application.id);
      setApplication(withdrawn);
    } catch (withdrawError) {
      setError(withdrawalErrorMessage(withdrawError));
    } finally {
      setWithdrawing(false);
    }
  };

  return (
    <View style={styles.screen}>
      <ScrollView contentContainerStyle={styles.container}>
        <Pressable onPress={() => router.back()} style={styles.backButton}>
          <Text style={styles.backText}>戻る</Text>
        </Pressable>

        <Text style={styles.heading}>応募する</Text>
        {requestLoading ? (
          <View style={styles.loadingRow}>
            <ActivityIndicator color="#245C2D" />
            <Text style={styles.loadingText}>依頼詳細を読み込んでいます</Text>
          </View>
        ) : null}
        {requestError ? <Text style={styles.errorText}>{requestError}</Text> : null}
        <Text style={styles.requestTitle}>{title || "選択した依頼"}</Text>
        {description ? (
          <Text style={styles.requestDescription}>{description}</Text>
        ) : null}

        {application ? (
          <View style={styles.successPanel}>
            <Text style={styles.successTitle}>応募を受け付けました</Text>
            <Text style={styles.statusText}>応募状態: {application.status}</Text>
            <Text style={styles.referenceText}>依頼ID: {application.requestId}</Text>
            <Text style={styles.referenceText}>応募者ID: {application.helperId}</Text>
            {error && <Text style={styles.errorText}>{error}</Text>}
            {application.status === "applied" && (
              <Pressable
                accessibilityRole="button"
                disabled={withdrawing}
                onPress={() => void handleWithdraw()}
                style={[styles.withdrawButton, withdrawing && styles.disabledButton]}
              >
                {withdrawing ? (
                  <ActivityIndicator color="#A52A2A" />
                ) : (
                  <Text style={styles.withdrawText}>応募を取り下げる</Text>
                )}
              </Pressable>
            )}
          </View>
        ) : (
          <>
            <Text style={styles.label}>応募理由</Text>
            <TextInput
              accessibilityLabel="応募理由"
              multiline
              maxLength={1000}
              onChangeText={setMessage}
              placeholder="経験やお手伝いできる内容を入力してください"
              style={[styles.input, styles.messageInput]}
              value={message}
            />

            <Text style={styles.label}>対応可能日時</Text>
            <TextInput
              accessibilityLabel="対応可能日時"
              autoCapitalize="none"
              onChangeText={setAvailableAt}
              placeholder="例: 2026-09-01T10:00:00+09:00"
              style={styles.input}
              value={availableAt}
            />

            {error && <Text style={styles.errorText}>{error}</Text>}
            {!requestId && <Text style={styles.errorText}>応募する依頼を確認できませんでした。</Text>}

            <Pressable
              accessibilityRole="button"
              disabled={!canSubmit || submitting}
              onPress={() => void handleSubmit()}
              style={[styles.submitButton, (!canSubmit || submitting) && styles.disabledButton]}
            >
              {submitting ? (
                <ActivityIndicator color="#FFFFFF" />
              ) : (
                <Text style={styles.submitText}>応募を送信する</Text>
              )}
            </Pressable>
          </>
        )}
        <Pressable
          onPress={() =>
            router.push({
              pathname: "/helper/report",
              params: { targetType: "request", targetId: requestId, title },
            })
          }
          style={({ pressed }) => [styles.reportLink, pressed && styles.reportLinkPressed]}
        >
          <Text style={styles.reportLinkText}>この依頼を通報する・依頼者をブロックする</Text>
        </Pressable>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, alignItems: "center", backgroundColor: "#FFF5E9" },
  container: { width: "100%", maxWidth: 520, padding: 28 },
  backButton: { alignSelf: "flex-start", paddingHorizontal: 16, paddingVertical: 10 },
  backText: { color: "#245C2D", fontSize: 16, fontWeight: "700" },
  heading: { color: "#35410F", fontSize: 28, fontWeight: "900", marginTop: 20 },
  requestTitle: { color: "#2D3A2E", fontSize: 18, fontWeight: "700", marginTop: 12, marginBottom: 28 },
  requestDescription: {
    marginTop: 6,
    color: "#555555",
    fontSize: 14,
    lineHeight: 21,
  },
  loadingRow: { alignItems: "center", flexDirection: "row", gap: 8, marginTop: 14 },
  loadingText: { color: "#586259", fontSize: 13, fontWeight: "700" },
  label: { color: "#2D3A2E", fontSize: 16, fontWeight: "700", marginBottom: 8 },
  input: { backgroundColor: "#FFFFFF", borderColor: "#C8CEBD", borderRadius: 12, borderWidth: 1, fontSize: 16, marginBottom: 22, padding: 14 },
  messageInput: { minHeight: 120, textAlignVertical: "top" },
  errorText: { color: "#A52A2A", fontSize: 14, marginBottom: 16 },
  submitButton: { alignItems: "center", backgroundColor: "#245C2D", borderRadius: 14, minHeight: 52, justifyContent: "center" },
  disabledButton: { opacity: 0.45 },
  submitText: { color: "#FFFFFF", fontSize: 17, fontWeight: "800" },
  successPanel: { backgroundColor: "#FFFFFF", borderRadius: 16, padding: 22 },
  successTitle: { color: "#245C2D", fontSize: 20, fontWeight: "800", marginBottom: 14 },
  statusText: { color: "#2D3A2E", fontSize: 16, marginBottom: 12 },
  referenceText: { color: "#586259", fontSize: 13, marginTop: 5 },
  withdrawButton: { alignItems: "center", borderColor: "#A52A2A", borderRadius: 14, borderWidth: 1, justifyContent: "center", marginTop: 22, minHeight: 48 },
  withdrawText: { color: "#A52A2A", fontSize: 16, fontWeight: "800" },
  reportLink: { alignSelf: "center", marginTop: 26, paddingVertical: 8 },
  reportLinkPressed: { opacity: 0.6 },
  reportLinkText: { color: "#666666", fontSize: 13, textDecorationLine: "underline" },
});
