import React from "react";
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";

type ChatsListScreenProps = {
  role: "requester" | "helper";
};

const chats = [
  {
    id: 1,
    initials: "T.O",
    preview: "あなたの依頼を引き受けました！...",
    unread: 1,
  },
  {
    id: 2,
    initials: "T.S",
    preview: "依頼が完了しました...",
    unread: 0,
  },
  {
    id: 3,
    initials: "M.K",
    preview: "明日の14時で大丈夫です！",
    unread: 0,
  },
];

export default function ChatsListScreen({
  role,
}: ChatsListScreenProps) {
  const router = useRouter();

  const openChat = () => {
    if (role === "requester") {
      router.push("/help/chat");
    } else {
      router.push("/helper/chat");
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
          {chats.map((chat) => (
            <TouchableOpacity
              key={chat.id}
              style={styles.chatRow}
              onPress={openChat}
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
                  {chat.initials}
                </Text>

                <Text
                  style={styles.preview}
                  numberOfLines={1}
                >
                  {chat.preview}
                </Text>
              </View>

              {chat.unread > 0 && (
                <View style={styles.unreadBadge}>
                  <Text style={styles.unreadText}>
                    {chat.unread}
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