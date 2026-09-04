import React, { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { listChats, type ChatSummary } from "../features/messages/client";
import { requestListErrorMessage } from "../features/requests/client";

type ChatsListScreenProps = {
  role: "requester" | "helper";
};

export default function ChatsListScreen({
  role,
}: ChatsListScreenProps) {
  const router = useRouter();
  const [chats, setChats] = useState<ChatSummary[]>([]);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [errorMessage, setErrorMessage] = useState("");

  const load = useCallback(async () => {
    setStatus("loading");
    try {
      const response = await listChats();
      setChats(response.items);
      setStatus("ready");
    } catch (error) {
      setErrorMessage(requestListErrorMessage(error));
      setStatus("error");
    }
  }, []);

  useEffect(() => {
    let active = true;
    void listChats().then((response) => {
      if (!active) return;
      setChats(response.items);
      setStatus("ready");
    }).catch((error: unknown) => {
      if (!active) return;
      setErrorMessage(requestListErrorMessage(error));
      setStatus("error");
    });
    return () => { active = false; };
  }, []);

  const openChat = (matchId: string) => {
    if (role === "requester") {
      router.push({ pathname: "/help/chat", params: { matchId } });
    } else {
      router.push({ pathname: "/helper/chat", params: { matchId } });
    }
  };

  return (
    <View style={styles.page}>
      <View style={styles.container}>
        <View style={styles.header}>
          <Text style={styles.title}>チャット</Text>
        </View>

        <ScrollView
          style={styles.list}
          contentContainerStyle={styles.listContent}
        >
          {status === "loading" ? (
            <View style={styles.stateBox}><ActivityIndicator color="#4E8B62" /><Text>チャットを読み込んでいます...</Text></View>
          ) : status === "error" ? (
            <View style={styles.stateBox}>
              <Text style={styles.errorText}>{errorMessage}</Text>
              <TouchableOpacity onPress={() => void load()}><Text style={styles.retryText}>もう一度読み込む</Text></TouchableOpacity>
            </View>
          ) : chats.length === 0 ? (
            <View style={styles.stateBox}><Text>進行中または過去のチャットはありません。</Text></View>
          ) : chats.map((chat) => (
            <TouchableOpacity
              key={chat.matchId}
              style={styles.chatRow}
              onPress={() => openChat(chat.matchId)}
              activeOpacity={0.7}
            >
              <View style={styles.avatar}>
                <Ionicons
                  name="person"
                  size={24}
                  color="#AAAAAA"
                />
              </View>

              <View style={styles.chatContent}>
                <Text style={styles.name}>
                  {chat.counterpart.displayName}
                </Text>

                <Text
                  style={styles.preview}
                  numberOfLines={1}
                >
                  {chat.latestMessage?.body ?? chat.request.title}
                </Text>
              </View>

              {chat.unreadCount > 0 && (
                <View style={styles.unreadBadge}>
                  <Text style={styles.unreadText}>
                    {chat.unreadCount}
                  </Text>
                </View>
              )}
            </TouchableOpacity>
          ))}
        </ScrollView>
      </View>
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
    backgroundColor: "#FFF8ED",
  },

  header: {
    paddingTop: 55,
    paddingHorizontal: 24,
    paddingBottom: 16,
  },

  title: {
    fontSize: 22,
    fontWeight: "700",
    color: "#111111",
  },

  list: {
    flex: 1,
  },

  listContent: {
    paddingHorizontal: 18,
    paddingBottom: 24,
  },
  stateBox: { alignItems: "center", gap: 12, paddingVertical: 48 },
  errorText: { color: "#A23B32", textAlign: "center" },
  retryText: { color: "#245C2D", fontWeight: "700" },

  chatRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 12,
  },

  avatar: {
    width: 52,
    height: 52,
    borderRadius: 26,
    backgroundColor: "#DDDDDD",
    alignItems: "center",
    justifyContent: "center",
    marginRight: 14,
  },

  chatContent: {
    flex: 1,
    minWidth: 0,
  },

  name: {
    fontSize: 16,
    fontWeight: "700",
    color: "#111111",
    marginBottom: 4,
  },

  preview: {
    fontSize: 13,
    color: "#557157",
  },

  unreadBadge: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: "#F2A52B",
    alignItems: "center",
    justifyContent: "center",
    marginLeft: 10,
  },

  unreadText: {
    color: "#111111",
    fontSize: 16,
    fontWeight: "700",
  },
});
