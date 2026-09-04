import React, { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { useAuth } from "../auth/AuthContext";
import {
  mergeMessages,
  sendMessage as sendMessageToApi,
  startMessagePolling,
  type Message,
} from "../features/messages/client";
import {
  completeMatch,
  createReview,
  disputeMatch,
  getMatch,
  matchActionErrorMessage,
  type Match,
} from "../features/matches/client";
import {
  generateAchievement,
  publishAchievement,
  type Achievement,
} from "../features/achievements/client";

type TalkScreenProps = {
  role: "requester" | "helper";
  matchId?: string;
};

export default function TalkScreen({ role, matchId }: TalkScreenProps) {
  const router = useRouter();
  const { profile } = useAuth();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [match, setMatch] = useState<Match | null>(null);
  const [loading, setLoading] = useState(Boolean(matchId));
  const [pollKey, setPollKey] = useState(0);
  const [loadError, setLoadError] = useState(false);
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState(false);
  const [actionBusy, setActionBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [disputeReason, setDisputeReason] = useState("");
  const [reviewComment, setReviewComment] = useState("");
  const [reviewed, setReviewed] = useState(false);
  const [achievement, setAchievement] = useState<Achievement | null>(null);

  useEffect(() => {
    if (!matchId) return;
    return startMessagePolling({
      matchId,
      onMessages: (incoming) => {
        setMessages(mergeMessages([], incoming));
        setLoading(false);
        setLoadError(false);
      },
      onError: () => {
        setLoading(false);
        setLoadError(true);
      },
    });
  }, [matchId, pollKey]);

  useEffect(() => {
    if (!matchId) return;
    let active = true;
    void getMatch(matchId).then((state) => {
      if (!active) return;
      if (state.status === "ready") setMatch(state.match);
      else setActionError(matchActionErrorMessage(state.error));
    });
    return () => { active = false; };
  }, [matchId]);

  const sendMessage = useCallback(async () => {
    const trimmed = input.trim();
    if (!trimmed || !matchId || sending) return;
    setSending(true);
    setSendError(false);
    try {
      const sent = await sendMessageToApi(matchId, trimmed);
      setMessages((current) => mergeMessages(current, [sent]));
      setInput("");
    } catch {
      setSendError(true);
    } finally {
      setSending(false);
    }
  }, [input, matchId, sending]);

  const runMatchAction = async (action: () => Promise<Match>) => {
    if (actionBusy) return;
    setActionBusy(true);
    setActionError(null);
    try { setMatch(await action()); }
    catch (error) { setActionError(matchActionErrorMessage(error)); }
    finally { setActionBusy(false); }
  };

  const submitReview = async () => {
    if (!matchId || !reviewComment.trim() || actionBusy) return;
    setActionBusy(true);
    setActionError(null);
    try {
      await createReview(matchId, {
        onTime: true, polite: true, safetyAware: true, communicative: true,
        comment: reviewComment,
      });
      setReviewed(true);
    } catch (error) { setActionError(matchActionErrorMessage(error)); }
    finally { setActionBusy(false); }
  };

  const createAchievement = async () => {
    if (!matchId || actionBusy) return;
    setActionBusy(true);
    setActionError(null);
    try { setAchievement(await generateAchievement(matchId)); }
    catch (error) { setActionError(matchActionErrorMessage(error)); }
    finally { setActionBusy(false); }
  };

  const approveAchievement = async () => {
    if (!achievement || actionBusy) return;
    setActionBusy(true);
    try { setAchievement(await publishAchievement(achievement.id, "members")); }
    catch (error) { setActionError(matchActionErrorMessage(error)); }
    finally { setActionBusy(false); }
  };

  return (
    <View style={styles.page}>
      <KeyboardAvoidingView
        style={styles.container}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        <View style={styles.header}>
         <TouchableOpacity
  style={styles.headerButton}
  onPress={() => {
    if (role === "requester") {
      router.replace("/help/chats");
    } else {
      router.replace("/helper/chats");
    }
  }}
>
  <Ionicons name="chevron-back" size={26} color="#222222" />
</TouchableOpacity>

          <View style={styles.headerCenter}>
            <Text style={styles.name}>山田さん</Text>

            <View style={styles.matchRow}>
              <Ionicons
                name="checkmark-circle"
                size={14}
                color="#4E8B62"
              />
              <Text style={styles.matchText}>{match?.status ?? "マッチング成立"}</Text>
            </View>
          </View>

          <TouchableOpacity style={styles.headerButton}>
            <Ionicons
              name="ellipsis-horizontal"
              size={24}
              color="#222222"
            />
          </TouchableOpacity>
        </View>

        <View style={styles.requestContainer}>
          <View style={styles.requestCard}>
            <View style={styles.requestIcon}>
              <Text style={styles.requestEmoji}>📦</Text>
            </View>

            <View style={styles.requestContent}>
              <Text style={styles.requestTitle}>
                重い荷物を運んでほしい
              </Text>

              <Text style={styles.requestInfo}>
                8/30 14:00 ・ 約15分
              </Text>

              <View style={styles.locationRow}>
                <Ionicons
                  name="location-outline"
                  size={15}
                  color="#777777"
                />
                <Text style={styles.requestInfo}>赤坂駅周辺</Text>
              </View>

              <TouchableOpacity>
                <Text style={styles.detailsText}>
                  依頼詳細を見る →
                </Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>

        <ScrollView
          style={styles.messages}
          contentContainerStyle={styles.messagesContent}
          keyboardShouldPersistTaps="handled"
        >
          {!matchId ? (
            <View style={styles.statusContainer}>
              <Text style={styles.errorText}>チャットを開くためのマッチ情報がありません。</Text>
            </View>
          ) : loading && messages.length === 0 ? (
            <View style={styles.statusContainer}>
              <ActivityIndicator color="#4E8B62" />
              <Text style={styles.statusText}>メッセージを取得しています...</Text>
            </View>
          ) : loadError && messages.length === 0 ? (
            <View style={styles.statusContainer}>
              <Text style={styles.errorText}>メッセージを取得できませんでした。</Text>
              <TouchableOpacity
                onPress={() => {
                  setLoading(true);
                  setLoadError(false);
                  setPollKey((key) => key + 1);
                }}
              >
                <Text style={styles.retryText}>再試行</Text>
              </TouchableOpacity>
            </View>
          ) : messages.length === 0 ? (
            <Text style={styles.date}>まだメッセージはありません</Text>
          ) : null}

          {loadError && messages.length > 0 ? (
            <Text style={styles.syncErrorText}>
              最新メッセージを取得できません。自動的に再試行します。
            </Text>
          ) : null}

          {messages.map((message) => {
            const mine = message.senderId === profile?.id;

            return (
              <View
                key={message.id}
                style={[
                  styles.messageRow,
                  mine
                    ? styles.myMessageRow
                    : styles.otherMessageRow,
                ]}
              >
                <View
                  style={[
                    styles.messageGroup,
                    mine
                      ? styles.myMessageGroup
                      : styles.otherMessageGroup,
                  ]}
                >
                  <View
                    style={[
                      styles.bubble,
                      mine
                        ? styles.myBubble
                        : styles.otherBubble,
                    ]}
                  >
                    <Text
                      style={[
                        styles.messageText,
                        mine
                          ? styles.myMessageText
                          : styles.otherMessageText,
                      ]}
                    >
                      {message.body}
                    </Text>
                  </View>

                  <Text style={styles.time}>
                    {new Date(message.sentAt).toLocaleTimeString("ja-JP", {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </Text>
                </View>
              </View>
            );
          })}
        </ScrollView>

        {match?.status === "completed" ? (
          <View style={styles.completedContainer}>
            <Ionicons
              name="checkmark-circle"
              size={20}
              color="#4E8B62"
            />

            <Text style={styles.completedText}>
              この依頼は完了しました
            </Text>
            {!reviewed ? (
              <>
                <TextInput
                  accessibilityLabel="感謝コメント"
                  value={reviewComment}
                  onChangeText={setReviewComment}
                  placeholder="感謝コメントを入力"
                  style={styles.actionInput}
                  multiline
                />
                <TouchableOpacity
                  disabled={!reviewComment.trim() || actionBusy}
                  onPress={() => void submitReview()}
                  style={[styles.completeButton, (!reviewComment.trim() || actionBusy) && styles.sendButtonDisabled]}
                >
                  <Text style={styles.completeButtonText}>評価と感謝を送る</Text>
                </TouchableOpacity>
              </>
            ) : <Text style={styles.completedText}>レビューを送信しました</Text>}
            {role === "helper" && !achievement ? (
              <TouchableOpacity disabled={actionBusy} onPress={() => void createAchievement()} style={styles.completeButton}>
                <Text style={styles.completeButtonText}>AI実績を作成する</Text>
              </TouchableOpacity>
            ) : null}
            {achievement ? (
              <View style={styles.achievementBox}>
                <Text style={styles.completedText}>{achievement.generatedText}</Text>
                {achievement.status !== "approved" ? (
                  <TouchableOpacity disabled={actionBusy} onPress={() => void approveAchievement()} style={styles.completeButton}>
                    <Text style={styles.completeButtonText}>確認してプロフィールに公開</Text>
                  </TouchableOpacity>
                ) : <Text style={styles.completedText}>プロフィールに公開しました</Text>}
              </View>
            ) : null}
          </View>
        ) : (
          <View style={styles.bottomContainer}>
            <View style={styles.inputRow}>
              <TouchableOpacity style={styles.addButton}>
                <Ionicons
                  name="add"
                  size={25}
                  color="#555555"
                />
              </TouchableOpacity>

              <TextInput
                style={styles.input}
                value={input}
                onChangeText={setInput}
                placeholder="メッセージを入力..."
                placeholderTextColor="#999999"
                multiline
                returnKeyType="send"
                onSubmitEditing={sendMessage}
              />

              <TouchableOpacity
                style={[
                  styles.sendButton,
                  (!input.trim() || !matchId || sending) && styles.sendButtonDisabled,
                ]}
                onPress={sendMessage}
                disabled={!input.trim() || !matchId || sending}
              >
                {sending ? (
                  <ActivityIndicator size="small" color="#FFFFFF" />
                ) : (
                  <Ionicons name="send" size={18} color="#FFFFFF" />
                )}
              </TouchableOpacity>
            </View>
            {sendError ? (
              <Text style={styles.sendErrorText}>送信できませんでした。もう一度お試しください。</Text>
            ) : null}

            <TextInput
              accessibilityLabel="キャンセル申告理由"
              value={disputeReason}
              onChangeText={setDisputeReason}
              placeholder="問題がある場合は理由を10文字以上で入力"
              style={styles.actionInput}
            />
            <TouchableOpacity
              disabled={!matchId || disputeReason.trim().length < 10 || actionBusy}
              onPress={() => matchId && void runMatchAction(() => disputeMatch(matchId, disputeReason))}
              style={[styles.disputeButton, (!matchId || disputeReason.trim().length < 10 || actionBusy) && styles.sendButtonDisabled]}
            >
              <Text style={styles.disputeButtonText}>キャンセル・問題を申告する</Text>
            </TouchableOpacity>
            {actionError ? <Text style={styles.sendErrorText}>{actionError}</Text> : null}

            <TouchableOpacity
              style={styles.completeButton}
              disabled={!matchId || actionBusy || match?.status === "disputed"}
              onPress={() => matchId && void runMatchAction(() => completeMatch(matchId, role))}
            >
              <Ionicons
                name="checkmark-circle-outline"
                size={20}
                color="#4E8B62"
              />

              <Text style={styles.completeButtonText}>
                依頼を完了する
              </Text>
            </TouchableOpacity>
          </View>
        )}
      </KeyboardAvoidingView>
    </View>
  );
}

const styles = StyleSheet.create({
  page: {
    flex: 1,
    backgroundColor: "#F5F5F5",
    alignItems: "center",
  },

  container: {
    flex: 1,
    width: "100%",
    maxWidth: 520,
    backgroundColor: "#FFFFFF",
  },

  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 16,
    paddingTop: Platform.OS === "ios" ? 58 : 20,
    paddingBottom: 14,
    borderBottomWidth: 1,
    borderBottomColor: "#EEEEEE",
    backgroundColor: "#FFFFFF",
  },

  headerButton: {
    width: 42,
    height: 42,
    alignItems: "center",
    justifyContent: "center",
  },

  headerCenter: {
    alignItems: "center",
  },

  name: {
    fontSize: 16,
    fontWeight: "600",
    color: "#222222",
  },

  matchRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    marginTop: 3,
  },

  matchText: {
    fontSize: 11,
    color: "#4E8B62",
    fontWeight: "500",
  },

  requestContainer: {
    paddingHorizontal: 16,
    paddingTop: 14,
  },

  requestCard: {
    flexDirection: "row",
    backgroundColor: "#F8F8F5",
    borderRadius: 18,
    padding: 15,
    borderWidth: 1,
    borderColor: "#EBEBE6",
  },

  requestIcon: {
    width: 46,
    height: 46,
    borderRadius: 14,
    backgroundColor: "#FFFFFF",
    alignItems: "center",
    justifyContent: "center",
    marginRight: 12,
  },

  requestEmoji: {
    fontSize: 22,
  },

  requestContent: {
    flex: 1,
  },

  requestTitle: {
    fontSize: 15,
    fontWeight: "600",
    color: "#222222",
    marginBottom: 5,
  },

  requestInfo: {
    fontSize: 13,
    color: "#777777",
  },

  locationRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 3,
    marginTop: 4,
  },

  detailsText: {
    fontSize: 13,
    fontWeight: "600",
    color: "#4E8B62",
    marginTop: 9,
  },

  messages: {
    flex: 1,
  },

  messagesContent: {
    paddingHorizontal: 16,
    paddingTop: 20,
    paddingBottom: 20,
  },

  date: {
    textAlign: "center",
    fontSize: 11,
    color: "#AAAAAA",
    marginBottom: 20,
  },

  statusContainer: {
    alignItems: "center",
    gap: 10,
    paddingVertical: 28,
  },

  statusText: {
    color: "#777777",
    fontSize: 13,
  },

  errorText: {
    color: "#A23B32",
    fontSize: 13,
    textAlign: "center",
  },

  retryText: {
    color: "#4E8B62",
    fontSize: 14,
    fontWeight: "600",
  },

  syncErrorText: {
    color: "#A23B32",
    fontSize: 12,
    marginBottom: 12,
    textAlign: "center",
  },

  messageRow: {
    width: "100%",
    marginBottom: 13,
  },

  myMessageRow: {
    alignItems: "flex-end",
  },

  otherMessageRow: {
    alignItems: "flex-start",
  },

  messageGroup: {
    maxWidth: "78%",
  },

  myMessageGroup: {
    alignItems: "flex-end",
  },

  otherMessageGroup: {
    alignItems: "flex-start",
  },

  bubble: {
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 18,
  },

  myBubble: {
    backgroundColor: "#4E8B62",
    borderBottomRightRadius: 5,
  },

  otherBubble: {
    backgroundColor: "#F0F0ED",
    borderBottomLeftRadius: 5,
  },

  messageText: {
    fontSize: 14,
    lineHeight: 20,
  },

  myMessageText: {
    color: "#FFFFFF",
  },

  otherMessageText: {
    color: "#222222",
  },

  time: {
    fontSize: 10,
    color: "#AAAAAA",
    marginTop: 4,
    marginHorizontal: 4,
  },

  bottomContainer: {
    borderTopWidth: 1,
    borderTopColor: "#EEEEEE",
    paddingHorizontal: 14,
    paddingTop: 12,
    paddingBottom: Platform.OS === "ios" ? 28 : 14,
    backgroundColor: "#FFFFFF",
  },

  inputRow: {
    flexDirection: "row",
    alignItems: "flex-end",
    gap: 8,
  },

  addButton: {
    width: 42,
    height: 42,
    borderRadius: 21,
    backgroundColor: "#F1F1EE",
    alignItems: "center",
    justifyContent: "center",
  },

  input: {
    flex: 1,
    minHeight: 42,
    maxHeight: 100,
    backgroundColor: "#F1F1EE",
    borderRadius: 21,
    paddingHorizontal: 16,
    paddingVertical: 10,
    fontSize: 16,
    color: "#222222",
  },

  sendButton: {
    width: 42,
    height: 42,
    borderRadius: 21,
    backgroundColor: "#4E8B62",
    alignItems: "center",
    justifyContent: "center",
  },

  sendButtonDisabled: {
    backgroundColor: "#CCCCCC",
  },

  sendErrorText: {
    color: "#A23B32",
    fontSize: 12,
    marginLeft: 50,
    marginTop: 6,
  },

  completeButton: {
    height: 46,
    borderRadius: 13,
    borderWidth: 1,
    borderColor: "#4E8B62",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 7,
    marginTop: 12,
  },

  completeButtonText: {
    color: "#4E8B62",
    fontSize: 14,
    fontWeight: "600",
  },

  actionInput: {
    minHeight: 42,
    marginTop: 10,
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderWidth: 1,
    borderColor: "#D8D8D2",
    borderRadius: 12,
    backgroundColor: "#FAFAF7",
  },

  disputeButton: {
    minHeight: 42,
    marginTop: 8,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 12,
    backgroundColor: "#A23B32",
  },

  disputeButtonText: {
    color: "#FFFFFF",
    fontSize: 13,
    fontWeight: "600",
  },

  achievementBox: {
    width: "100%",
    marginTop: 10,
    padding: 12,
    borderRadius: 10,
    backgroundColor: "#FFFFFF",
  },

  completedContainer: {
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    gap: 7,
    marginHorizontal: 16,
    marginBottom: Platform.OS === "ios" ? 28 : 14,
    paddingVertical: 14,
    borderRadius: 13,
    backgroundColor: "#EEF6F0",
  },

  completedText: {
    color: "#4E8B62",
    fontSize: 14,
    fontWeight: "600",
  },
});
