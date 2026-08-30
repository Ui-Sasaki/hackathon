import { useRef, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  Pressable,
  ScrollView,
  ActivityIndicator,
} from "react-native";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useFontSize } from "../../context/FontSizeContext";

type RequestData = {
  task: string | null;
  location: string | null;
  duration: string | null;
  deadline: string | null;
  notes: string | null;
};

type VoiceRequestResponse = {
  complete: boolean;
  question: string | null;
  request: RequestData;
};

type Message = {
  id: number;
  role: "ai" | "user";
  text: string;
};

declare global {
  interface Window {
    SpeechRecognition?: any;
    webkitSpeechRecognition?: any;
  }
}

export default function RequestVoiceScreen() {
  const router = useRouter();
  const { scale } = useFontSize();
  const styles = createStyles(scale);

  const [messages, setMessages] = useState<Message[]>([
    {
      id: 1,
      role: "ai",
      text: "どのようなお手伝いが必要ですか？",
    },
  ]);

  const [isListening, setIsListening] = useState(false);
  const [isThinking, setIsThinking] = useState(false);

  const [requestData, setRequestData] =
    useState<RequestData>({
      task: null,
      location: null,
      duration: null,
      deadline: null,
      notes: null,
    });

  const recognitionRef = useRef<any>(null);
  const scrollRef = useRef<ScrollView>(null);

  const mockBackend = async (
    text: string
  ): Promise<VoiceRequestResponse> => {
    await new Promise((resolve) =>
      setTimeout(resolve, 700)
    );

    if (!requestData.task) {
      return {
        complete: false,
        question: "どこでお願いしたいですか？",
        request: {
          ...requestData,
          task: text,
        },
      };
    }

    if (!requestData.location) {
      return {
        complete: false,
        question:
          "どのくらいの時間を予定していますか？",
        request: {
          ...requestData,
          location: text,
        },
      };
    }

    if (!requestData.duration) {
      return {
        complete: false,
        question:
          "いつまで依頼していたいですか？",
        request: {
          ...requestData,
          duration: text,
        },
      };
    }

    return {
      complete: true,
      question: null,
      request: {
        ...requestData,
        deadline: text,
      },
    };
  };

  const sendToBackend = async (text: string) => {
    setIsThinking(true);

    try {
      const data = await mockBackend(text);

      setRequestData(data.request);

      if (data.complete) {
        router.push({
          pathname: "/help/request-confirm",
          params: {
            task: data.request.task ?? "",
            location: data.request.location ?? "",
            duration: data.request.duration ?? "",
            deadline: data.request.deadline ?? "",
            notes: data.request.notes ?? "",
          },
        });

        return;
      }

      if (data.question) {
        setMessages((current) => [
          ...current,
          {
            id: Date.now(),
            role: "ai",
            text: data.question!,
          },
        ]);
      }
    } catch {
      setMessages((current) => [
        ...current,
        {
          id: Date.now(),
          role: "ai",
          text:
            "エラーが発生しました。もう一度お試しください。",
        },
      ]);
    } finally {
      setIsThinking(false);
    }
  };

  const startListening = () => {
    if (typeof window === "undefined") {
      return;
    }

    const SpeechRecognition =
      window.SpeechRecognition ||
      window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
      setMessages((current) => [
        ...current,
        {
          id: Date.now(),
          role: "ai",
          text:
            "このブラウザでは音声入力を利用できません。",
        },
      ]);

      return;
    }

    const recognition =
      new SpeechRecognition();

    recognition.lang = "ja-JP";
    recognition.interimResults = false;
    recognition.continuous = false;

    recognition.onstart = () => {
      setIsListening(true);
    };

    recognition.onend = () => {
      setIsListening(false);
    };

    recognition.onerror = () => {
      setIsListening(false);
    };

    recognition.onresult = (event: any) => {
      const transcript =
        event.results[
          event.results.length - 1
        ][0].transcript;

      setMessages((current) => [
        ...current,
        {
          id: Date.now(),
          role: "user",
          text: transcript,
        },
      ]);

      sendToBackend(transcript);
    };

    recognitionRef.current = recognition;

    recognition.start();
  };

  return (
    <View style={styles.screen}>
      <View style={styles.container}>
        <Pressable
          onPress={() => router.back()}
          style={({ pressed }) => [
            styles.backButton,
            pressed && styles.pressed,
          ]}
        >
          <Ionicons
            name="arrow-back"
            size={18}
            color="#111111"
          />

          <Text style={styles.backText}>
            戻る
          </Text>
        </Pressable>

        <Text style={styles.title}>
          音声で入力
        </Text>

        <Text style={styles.description}>
          AIと会話しながら依頼内容を作成します
        </Text>

        <ScrollView
          ref={scrollRef}
          style={styles.chat}
          contentContainerStyle={
            styles.chatContent
          }
          showsVerticalScrollIndicator={false}
          onContentSizeChange={() =>
            scrollRef.current?.scrollToEnd({
              animated: true,
            })
          }
        >
          {messages.map((message) => (
            <View
              key={message.id}
              style={[
                styles.messageRow,
                message.role === "user"
                  ? styles.userRow
                  : styles.aiRow,
              ]}
            >
              {message.role === "ai" && (
                <View style={styles.aiIcon}>
                  <Ionicons
                    name="sparkles"
                    size={18}
                    color="#FFFFFF"
                  />
                </View>
              )}

              <View
                style={[
                  styles.bubble,
                  message.role === "user"
                    ? styles.userBubble
                    : styles.aiBubble,
                ]}
              >
                <Text
                  style={[
                    styles.messageText,
                    message.role === "user" &&
                      styles.userMessageText,
                  ]}
                >
                  {message.text}
                </Text>
              </View>
            </View>
          ))}

          {isThinking && (
            <View style={styles.thinkingRow}>
              <ActivityIndicator
                size="small"
                color="#245C2D"
              />

              <Text
                style={styles.thinkingText}
              >
                AIが確認しています...
              </Text>
            </View>
          )}
        </ScrollView>

        <View style={styles.voiceArea}>
          <Text style={styles.voiceStatus}>
            {isListening
              ? "聞いています..."
              : isThinking
                ? "回答を確認しています..."
                : "マイクをタップして話してください"}
          </Text>

          <Pressable
            disabled={isThinking}
            onPress={startListening}
            style={({ pressed }) => [
              styles.micButton,
              isListening &&
                styles.micButtonListening,
              isThinking &&
                styles.micButtonDisabled,
              pressed && styles.pressed,
            ]}
          >
            <Ionicons
              name={
                isListening
                  ? "mic"
                  : "mic-outline"
              }
              size={44}
              color="#FFFFFF"
            />
          </Pressable>

          {isListening && (
            <View
              style={styles.listeningBadge}
            >
              <View
                style={styles.listeningDot}
              />

              <Text
                style={styles.listeningText}
              >
                音声を認識中
              </Text>
            </View>
          )}
        </View>
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

    chat: {
      flex: 1,
      marginTop: 30,
    },

    chatContent: {
      paddingBottom: 24,
    },

    messageRow: {
      width: "100%",
      flexDirection: "row",
      alignItems: "flex-end",
      marginBottom: 18,
    },

    aiRow: {
      justifyContent: "flex-start",
    },

    userRow: {
      justifyContent: "flex-end",
    },

    aiIcon: {
      width: 34,
      height: 34,
      borderRadius: 17,
      backgroundColor: "#F2A329",
      justifyContent: "center",
      alignItems: "center",
      marginRight: 8,
    },

    bubble: {
      maxWidth: "78%",
      paddingHorizontal: 16,
      paddingVertical: 13,
      borderRadius: 18,
    },

    aiBubble: {
      backgroundColor: "#FFFFFF",
      borderBottomLeftRadius: 5,
    },

    userBubble: {
      backgroundColor: "#245C2D",
      borderBottomRightRadius: 5,
    },

    messageText: {
      color: "#333333",
      fontSize: 15 * scale,
      lineHeight: 22 * scale,
    },

    userMessageText: {
      color: "#FFFFFF",
    },

    thinkingRow: {
      flexDirection: "row",
      alignItems: "center",
      gap: 9,
      marginLeft: 42,
    },

    thinkingText: {
      color: "#777777",
      fontSize: 13 * scale,
    },

    voiceArea: {
      alignItems: "center",
      paddingTop: 16,
    },

    voiceStatus: {
      color: "#666666",
      fontSize: 14 * scale,
      marginBottom: 14,
    },

    micButton: {
      width: 84,
      height: 84,
      borderRadius: 42,
      backgroundColor: "#159326",
      justifyContent: "center",
      alignItems: "center",
      shadowColor: "#000000",
      shadowOpacity: 0.15,
      shadowRadius: 8,
      shadowOffset: {
        width: 0,
        height: 4,
      },
      elevation: 5,
    },

    micButtonListening: {
      backgroundColor: "#F2A329",
    },

    micButtonDisabled: {
      opacity: 0.55,
    },

    listeningBadge: {
      flexDirection: "row",
      alignItems: "center",
      gap: 6,
      marginTop: 12,
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
    },

    pressed: {
      opacity: 0.72,
      transform: [{ scale: 0.97 }],
    },
  });