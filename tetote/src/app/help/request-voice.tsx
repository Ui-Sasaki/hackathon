import { useEffect, useMemo, useReducer, useRef, useState } from "react";
import {
  View,
  Text,
  TextInput,
  StyleSheet,
  Pressable,
  ScrollView,
  ActivityIndicator,
} from "react-native";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useFontSize } from "../../context/FontSizeContext";
import { describeMasked, maskPersonalInfo } from "../../voice/masking";
import {
  RecognitionController,
  webSpeechAdapter,
} from "../../voice/recognition";
import {
  initialVoiceState,
  submissionOf,
  voiceReducer,
  VOICE_ERROR_MESSAGES,
} from "../../voice/session";
import {
  appendAnswer,
  MAX_QUESTION_ROUNDS,
  nextConversationStep,
} from "../../voice/conversation";

export default function RequestVoiceScreen() {
  const router = useRouter();
  const { scale } = useFontSize();
  const styles = createStyles(scale);

  const [state, dispatch] = useReducer(voiceReducer, initialVoiceState);
  const controllerRef = useRef<RecognitionController | null>(null);
  // AIとの会話ループ。確認済みテキストの累積と、いま提示中の質問を持つ。
  const [baseText, setBaseText] = useState("");
  const [question, setQuestion] = useState<string | null>(null);
  const [questionRound, setQuestionRound] = useState(0);
  const [checking, setChecking] = useState(false);

  // 非対応ブラウザでは録音を始めさせず、最初から手入力へ促す。
  useEffect(() => {
    if (!webSpeechAdapter.isSupported()) {
      dispatch({ type: "fail", reason: "unsupported" });
    }
  }, []);

  // 画面を離れるときは録音を破棄する。音声を残さないための後始末。
  useEffect(() => {
    return () => {
      controllerRef.current?.abort();
      controllerRef.current = null;
    };
  }, []);

  const startRecording = () => {
    controllerRef.current?.abort();
    dispatch({ type: "start" });

    controllerRef.current = webSpeechAdapter.start({
      onTranscript: (text) => {
        controllerRef.current = null;
        dispatch({ type: "transcribed", text });
      },
      onError: (reason) => {
        controllerRef.current = null;
        dispatch({ type: "fail", reason });
      },
    });
  };

  const stopRecording = () => {
    dispatch({ type: "stop" });
    controllerRef.current?.stop();
  };

  const cancelRecording = () => {
    controllerRef.current?.abort();
    controllerRef.current = null;
    dispatch({ type: "cancel" });
  };

  const switchToManualInput = () => {
    controllerRef.current?.abort();
    controllerRef.current = null;
    router.replace("/help/request-manual");
  };

  // 確認画面へ進んだ後に戻ってきても、同じ内容を編集できる状態で見せる。
  const isReviewing =
    state.status === "review" || state.status === "confirmed";
  const draft = isReviewing ? state.draft : "";

  // 送信前に何を伏せるかを、確認画面へ進む前に利用者へ見せる。
  const maskNotice = useMemo(() => {
    if (!isReviewing) {
      return null;
    }

    return describeMasked(maskPersonalInfo(draft).masked);
  }, [draft, isReviewing]);

  const proceedToConfirm = (content: string) => {
    router.push({
      pathname: "/help/request-confirm",
      params: { content },
    });
  };

  // 確認を押したときにだけ先へ進む。渡すのは必ずマスク済みテキスト。
  // 不足情報があればAIの追加質問を1問だけ受け取り、答えを継ぎ足して繰り返す。
  const confirmDraft = async () => {
    if (checking) {
      return;
    }

    const next = voiceReducer(state, { type: "confirm" });
    dispatch({ type: "confirm" });

    const submission = submissionOf(next);

    if (!submission) {
      return;
    }

    const combined = appendAnswer(baseText, submission.text);
    setChecking(true);

    try {
      const step = await nextConversationStep(combined, questionRound);

      if (step.type === "question") {
        setBaseText(combined);
        setQuestion(step.question);
        setQuestionRound((current) => current + 1);
        // 回答を録音できるよう、録音前の状態へ戻す。
        dispatch({ type: "cancel" });
        return;
      }

      proceedToConfirm(combined);
    } finally {
      setChecking(false);
    }
  };

  return (
    <View style={styles.screen}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.container}>
          <Pressable
            onPress={() => router.replace("/help/request")}
            style={({ pressed }) => [
              styles.backButton,
              pressed && styles.pressed,
            ]}
          >
            <Ionicons name="arrow-back" size={18} color="#111111" />

            <Text style={styles.backText}>戻る</Text>
          </Pressable>

          <Text style={styles.title}>音声で入力</Text>

          <Text style={styles.description}>
            話した内容を文字にします。確認してから依頼へ進みます
          </Text>

          {state.status === "idle" && question && (
            <View style={styles.card}>
              <View style={styles.cardHeader}>
                <Ionicons name="sparkles" size={22} color="#F2A329" />

                <Text style={styles.cardTitle}>AIからの質問</Text>
              </View>

              <Text style={styles.questionText}>{question}</Text>

              <Text style={styles.cardText}>
                マイクで答えると、これまでの内容に追加されます。（{questionRound}/{MAX_QUESTION_ROUNDS}回目）
              </Text>

              <Pressable
                onPress={startRecording}
                style={({ pressed }) => [
                  styles.primaryButton,
                  pressed && styles.pressed,
                ]}
              >
                <Ionicons name="mic" size={20} color="#FFFFFF" />

                <Text style={styles.primaryButtonText}>マイクで答える</Text>
              </Pressable>

              <Pressable
                onPress={() => proceedToConfirm(baseText)}
                style={({ pressed }) => [
                  styles.secondaryButton,
                  pressed && styles.pressed,
                ]}
              >
                <Text style={styles.secondaryButtonText}>
                  答えずにこのまま進む
                </Text>
              </Pressable>
            </View>
          )}

          {state.status === "idle" && !question && (
            <View style={styles.card}>
              <View style={styles.cardHeader}>
                <Ionicons name="mic-outline" size={22} color="#245C2D" />

                <Text style={styles.cardTitle}>マイクの利用について</Text>
              </View>

              <Text style={styles.cardText}>
                依頼したい内容を聞き取って文字にするためだけにマイクを使います。
              </Text>

              <Text style={styles.cardText}>
                音声はこのアプリに保存しません。文字にした内容は、あなたが確認して「進む」を押すまで送信されません。
              </Text>

              <Text style={styles.cardText}>
                電話番号やメールアドレス、詳しい住所は、送信前に自動で伏せます。
              </Text>

              <Pressable
                onPress={startRecording}
                style={({ pressed }) => [
                  styles.primaryButton,
                  pressed && styles.pressed,
                ]}
              >
                <Ionicons name="mic" size={20} color="#FFFFFF" />

                <Text style={styles.primaryButtonText}>
                  マイクを許可して録音を始める
                </Text>
              </Pressable>
            </View>
          )}

          {state.status === "listening" && (
            <View style={styles.card}>
              <View style={styles.listeningBadge}>
                <View style={styles.listeningDot} />

                <Text style={styles.listeningText}>録音中</Text>
              </View>

              <Text style={styles.cardText}>
                依頼したい内容を話してください。話し終わったら「録音を止める」を押します。
              </Text>

              <View style={styles.micCircle}>
                <Ionicons name="mic" size={44} color="#FFFFFF" />
              </View>

              <Pressable
                onPress={stopRecording}
                style={({ pressed }) => [
                  styles.primaryButton,
                  pressed && styles.pressed,
                ]}
              >
                <Ionicons name="stop" size={20} color="#FFFFFF" />

                <Text style={styles.primaryButtonText}>録音を止める</Text>
              </Pressable>

              <Pressable
                onPress={cancelRecording}
                style={({ pressed }) => [
                  styles.secondaryButton,
                  pressed && styles.pressed,
                ]}
              >
                <Text style={styles.secondaryButtonText}>録音を取り消す</Text>
              </Pressable>
            </View>
          )}

          {state.status === "transcribing" && (
            <View style={styles.card}>
              <ActivityIndicator size="small" color="#245C2D" />

              <Text style={styles.cardText}>文字にしています...</Text>
            </View>
          )}

          {isReviewing && (
            <View style={styles.card}>
              <View style={styles.cardHeader}>
                <Ionicons
                  name="document-text-outline"
                  size={22}
                  color="#245C2D"
                />

                <Text style={styles.cardTitle}>聞き取った内容</Text>
              </View>

              {question && (
                <Text style={styles.questionText}>{question}</Text>
              )}

              <Text style={styles.cardText}>
                違うところがあれば、そのまま直せます。
              </Text>

              <TextInput
                value={draft}
                onChangeText={(text) => dispatch({ type: "edit", text })}
                multiline
                placeholder="聞き取った内容がここに表示されます"
                placeholderTextColor="#888888"
                style={styles.transcriptInput}
              />

              {maskNotice && (
                <View style={styles.maskNotice}>
                  <Ionicons name="lock-closed" size={16} color="#245C2D" />

                  <Text style={styles.maskNoticeText}>{maskNotice}</Text>
                </View>
              )}

              <Pressable
                onPress={() => void confirmDraft()}
                disabled={checking}
                style={({ pressed }) => [
                  styles.primaryButton,
                  checking && styles.disabledButton,
                  pressed && styles.pressed,
                ]}
              >
                {checking ? (
                  <ActivityIndicator size="small" color="#FFFFFF" />
                ) : (
                  <Ionicons name="arrow-forward" size={20} color="#FFFFFF" />
                )}

                <Text style={styles.primaryButtonText}>
                  {checking ? "AIが確認しています..." : "この内容で確認へ進む"}
                </Text>
              </Pressable>

              <Pressable
                onPress={startRecording}
                style={({ pressed }) => [
                  styles.secondaryButton,
                  pressed && styles.pressed,
                ]}
              >
                <Text style={styles.secondaryButtonText}>録音し直す</Text>
              </Pressable>

              <Pressable
                onPress={cancelRecording}
                style={({ pressed }) => [
                  styles.secondaryButton,
                  pressed && styles.pressed,
                ]}
              >
                <Text style={styles.secondaryButtonText}>取り消す</Text>
              </Pressable>
            </View>
          )}

          {state.status === "error" && (
            <View style={[styles.card, styles.errorCard]}>
              <View style={styles.cardHeader}>
                <Ionicons name="alert-circle" size={22} color="#B4402A" />

                <Text style={[styles.cardTitle, styles.errorTitle]}>
                  音声入力を使えませんでした
                </Text>
              </View>

              <Text style={styles.cardText}>
                {VOICE_ERROR_MESSAGES[state.reason]}
              </Text>

              {state.reason !== "unsupported" && (
                <Pressable
                  onPress={startRecording}
                  style={({ pressed }) => [
                    styles.primaryButton,
                    pressed && styles.pressed,
                  ]}
                >
                  <Ionicons name="refresh" size={20} color="#FFFFFF" />

                  <Text style={styles.primaryButtonText}>
                    もう一度録音する
                  </Text>
                </Pressable>
              )}

              <Pressable
                onPress={switchToManualInput}
                style={({ pressed }) => [
                  styles.secondaryButton,
                  pressed && styles.pressed,
                ]}
              >
                <Text style={styles.secondaryButtonText}>
                  手で入力へ切り替える
                </Text>
              </Pressable>
            </View>
          )}

          {state.status !== "error" && (
            <Pressable
              onPress={switchToManualInput}
              style={({ pressed }) => [
                styles.fallbackLink,
                pressed && styles.pressed,
              ]}
            >
              <Ionicons name="hand-left-outline" size={18} color="#245C2D" />

              <Text style={styles.fallbackLinkText}>
                うまく話せないときは手で入力
              </Text>
            </Pressable>
          )}
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
      alignItems: "center",
    },

    scrollContent: {
      flexGrow: 1,
      alignItems: "center",
    },

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

    backText: {
      color: "#111111",
      fontSize: 15 * scale,
      fontWeight: "800",
    },

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
      marginTop: 26,
      width: "100%",
      borderRadius: 22,
      backgroundColor: "#FFFFFF",
      paddingHorizontal: 22,
      paddingVertical: 24,
      gap: 14,
      alignItems: "center",
    },

    errorCard: {
      backgroundColor: "#FDEDE9",
    },

    cardHeader: {
      flexDirection: "row",
      alignItems: "center",
      gap: 8,
      alignSelf: "flex-start",
    },

    cardTitle: {
      color: "#245C2D",
      fontSize: 17 * scale,
      fontWeight: "800",
    },

    errorTitle: {
      color: "#B4402A",
    },

    cardText: {
      alignSelf: "flex-start",
      color: "#444444",
      fontSize: 14 * scale,
      lineHeight: 21 * scale,
    },

    transcriptInput: {
      width: "100%",
      minHeight: 132,
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

    questionText: {
      alignSelf: "flex-start",
      color: "#245C2D",
      fontSize: 15 * scale,
      lineHeight: 22 * scale,
      fontWeight: "700",
      backgroundColor: "#F1F7F1",
      borderRadius: 12,
      paddingHorizontal: 14,
      paddingVertical: 10,
    },

    disabledButton: {
      opacity: 0.6,
    },

    maskNotice: {
      alignSelf: "flex-start",
      flexDirection: "row",
      alignItems: "center",
      gap: 6,
    },

    maskNoticeText: {
      color: "#245C2D",
      fontSize: 13 * scale,
      fontWeight: "700",
    },

    micCircle: {
      width: 84,
      height: 84,
      borderRadius: 42,
      backgroundColor: "#F2A329",
      justifyContent: "center",
      alignItems: "center",
    },

    listeningBadge: {
      alignSelf: "flex-start",
      flexDirection: "row",
      alignItems: "center",
      gap: 6,
    },

    listeningDot: {
      width: 8,
      height: 8,
      borderRadius: 4,
      backgroundColor: "#F2A329",
    },

    listeningText: {
      color: "#666666",
      fontSize: 13 * scale,
      fontWeight: "700",
    },

    primaryButton: {
      width: "100%",
      height: 54,
      borderRadius: 999,
      backgroundColor: "#159326",
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "center",
      gap: 8,
    },

    primaryButtonText: {
      color: "#FFFFFF",
      fontSize: 16 * scale,
      fontWeight: "800",
    },

    secondaryButton: {
      width: "100%",
      height: 48,
      borderRadius: 999,
      backgroundColor: "#D9D9D9",
      alignItems: "center",
      justifyContent: "center",
    },

    secondaryButtonText: {
      color: "#111111",
      fontSize: 15 * scale,
      fontWeight: "800",
    },

    fallbackLink: {
      marginTop: 22,
      alignSelf: "center",
      flexDirection: "row",
      alignItems: "center",
      gap: 6,
    },

    fallbackLinkText: {
      color: "#245C2D",
      fontSize: 14 * scale,
      fontWeight: "700",
      textDecorationLine: "underline",
    },

    pressed: {
      opacity: 0.72,
      transform: [{ scale: 0.97 }],
    },
  });
