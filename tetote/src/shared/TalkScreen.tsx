import React, { useState } from "react";
import {
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

type Message = {
  id: number;
  sender: "requester" | "helper";
  text: string;
  time: string;
};

type TalkScreenProps = {
  role: "requester" | "helper";
};

export default function TalkScreen({ role }: TalkScreenProps) {
  const router = useRouter();

  const [messages, setMessages] = useState<Message[]>([
    {
      id: 1,
      sender: "requester",
      text: "応募ありがとうございます！明日の14時ごろでも大丈夫でしょうか？",
      time: "10:32",
    },
    {
      id: 2,
      sender: "helper",
      text: "はい、大丈夫です！どのあたりに伺えばいいですか？",
      time: "10:34",
    },
    {
      id: 3,
      sender: "requester",
      text: "赤坂駅の7番出口付近でお願いします！",
      time: "10:35",
    },
    {
      id: 4,
      sender: "helper",
      text: "了解です！荷物はどれくらいありますか？",
      time: "10:36",
    },
    {
      id: 5,
      sender: "requester",
      text: "段ボールが3箱です。15分くらいで終わると思います！",
      time: "10:37",
    },
  ]);

  const [input, setInput] = useState("");
  const [completed, setCompleted] = useState(false);

  const sendMessage = () => {
    const trimmed = input.trim();

    if (!trimmed) return;

    const now = new Date();

    const time = now.toLocaleTimeString("ja-JP", {
      hour: "2-digit",
      minute: "2-digit",
    });

    setMessages((previousMessages) => [
      ...previousMessages,
      {
        id: Date.now(),
        sender: role,
        text: trimmed,
        time,
      },
    ]);

    setInput("");
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
              <Text style={styles.matchText}>マッチング成立</Text>
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
          <Text style={styles.date}>8月29日</Text>

          {messages.map((message) => {
            const mine = message.sender === role;

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
                      {message.text}
                    </Text>
                  </View>

                  <Text style={styles.time}>
                    {message.time}
                  </Text>
                </View>
              </View>
            );
          })}
        </ScrollView>

        {completed ? (
          <View style={styles.completedContainer}>
            <Ionicons
              name="checkmark-circle"
              size={20}
              color="#4E8B62"
            />

            <Text style={styles.completedText}>
              この依頼は完了しました
            </Text>
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
                  !input.trim() && styles.sendButtonDisabled,
                ]}
                onPress={sendMessage}
                disabled={!input.trim()}
              >
                <Ionicons
                  name="send"
                  size={18}
                  color="#FFFFFF"
                />
              </TouchableOpacity>
            </View>

            <TouchableOpacity
              style={styles.completeButton}
              onPress={() => setCompleted(true)}
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

  completedContainer: {
    flexDirection: "row",
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