import { useState } from "react";
import {
  View,
  Text,
  TextInput,
  StyleSheet,
  Pressable,
  ScrollView,
} from "react-native";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useFontSize } from "../../context/FontSizeContext";

const timeOptions = [
  "15分以内",
  "30分以内",
  "30分〜1時間",
  "1時間〜2時間",
  "2時間〜3時間",
  "半日",
  "1日",
];

export default function RequestManualScreen() {
  const router = useRouter();
  const { scale } = useFontSize();
  const styles = createStyles(scale);

  const [content, setContent] = useState("");
  const [location, setLocation] = useState("");
  const [time, setTime] = useState("");
  const [timeDropdownOpen, setTimeDropdownOpen] =
    useState(false);
  const [deadline, setDeadline] = useState("3日後");

  return (
    <View style={styles.screen}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.container}>
          <View style={styles.header}>
            <Pressable
              onPress={() =>
                router.replace("/help/request")
              }
              style={({ pressed }) => [
                styles.backButton,
                pressed && styles.pressed,
              ]}
            >
              <Ionicons
                name="arrow-back"
                size={21}
                color="#111111"
              />

              <Text style={styles.backText}>
                戻る
              </Text>
            </Pressable>

            <Text style={styles.title}>
              依頼入力
            </Text>

            <Ionicons
              name="hand-left"
              size={42}
              color="#191600"
            />
          </View>

          <View style={styles.formCard}>
            <Text style={styles.question}>
              1　何を依頼する？
            </Text>

            <TextInput
              value={content}
              onChangeText={setContent}
              placeholder="例：代わりに近所のスーパーに行ってほしい"
              placeholderTextColor="#888888"
              multiline
              style={styles.largeInput}
            />

            <Text style={styles.question}>
              2　場所は？
            </Text>

            <TextInput
              value={location}
              onChangeText={setLocation}
              placeholder="例：六本木ヒルズ前"
              placeholderTextColor="#888888"
              multiline
              style={styles.locationInput}
            />

            <Text style={styles.question}>
              3　必要な時間は？
            </Text>

            <View style={styles.timeSection}>
              <Pressable
                onPress={() =>
                  setTimeDropdownOpen(
                    (current) => !current
                  )
                }
                style={({ pressed }) => [
                  styles.timeSelect,
                  pressed && styles.pressed,
                ]}
              >
                <Text
                  style={[
                    styles.timeText,
                    !time &&
                      styles.timePlaceholder,
                  ]}
                >
                  {time || "選択してください"}
                </Text>

                <Ionicons
                  name={
                    timeDropdownOpen
                      ? "chevron-up"
                      : "chevron-down"
                  }
                  size={22}
                  color="#BDBDBD"
                />
              </Pressable>

              {timeDropdownOpen && (
                <View style={styles.timeDropdown}>
                  {timeOptions.map(
                    (option, index) => {
                      const selected =
                        time === option;

                      return (
                        <Pressable
                          key={option}
                          onPress={() => {
                            setTime(option);
                            setTimeDropdownOpen(
                              false
                            );
                          }}
                          style={({
                            pressed,
                          }) => [
                            styles.timeDropdownOption,
                            index !==
                              timeOptions.length -
                                1 &&
                              styles.timeDropdownBorder,
                            selected &&
                              styles.timeDropdownOptionSelected,
                            pressed &&
                              styles.dropdownPressed,
                          ]}
                        >
                          <Text
                            style={[
                              styles.timeDropdownText,
                              selected &&
                                styles.timeDropdownTextSelected,
                            ]}
                          >
                            {option}
                          </Text>

                          {selected && (
                            <Ionicons
                              name="checkmark"
                              size={19}
                              color="#D89B31"
                            />
                          )}
                        </Pressable>
                      );
                    }
                  )}
                </View>
              )}
            </View>

            <Text style={styles.deadlineQuestion}>
              4　いつまで依頼していたい？
            </Text>

            <View style={styles.deadlineOptions}>
              {[
                "24時間後",
                "3日後",
                "1週間後",
              ].map((item) => (
                <Pressable
                  key={item}
                  onPress={() =>
                    setDeadline(item)
                  }
                  style={({ pressed }) => [
                    styles.deadlineButton,
                    deadline === item &&
                      styles.deadlineButtonSelected,
                    pressed && styles.pressed,
                  ]}
                >
                  <Text
                    style={[
                      styles.deadlineButtonText,
                      deadline === item &&
                        styles.deadlineButtonTextSelected,
                    ]}
                  >
                    {item}
                  </Text>
                </Pressable>
              ))}
            </View>

            <Pressable
              onPress={() =>
                router.push({
                  pathname:
                    "/help/request-confirm",
                  params: {
                    content,
                    location,
                    time,
                    deadline,
                  },
                })
              }
              style={({ pressed }) => [
                styles.confirmButton,
                pressed && styles.pressed,
              ]}
            >
              <Text
                style={styles.confirmButtonText}
              >
                確認画面へ
              </Text>
            </Pressable>
          </View>
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
    },

    scrollContent: {
      flexGrow: 1,
      alignItems: "center",
      paddingBottom: 25,
    },

    container: {
      width: "100%",
      maxWidth: 520,
      paddingHorizontal: 28,
      paddingTop: 38,
    },

    header: {
      width: "100%",
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      marginBottom: 18,
    },

    backButton: {
      minHeight: 38,
      paddingHorizontal: 12,
      borderRadius: 999,
      backgroundColor: "#D9D9D9",
      flexDirection: "row",
      alignItems: "center",
      gap: 3,
    },

    backText: {
      color: "#111111",
      fontSize: 14 * scale,
      fontWeight: "800",
    },

    title: {
      color: "#111111",
      fontSize: 20 * scale,
      fontWeight: "900",
    },

    formCard: {
      width: "100%",
      borderWidth: 2,
      borderColor: "#F2A329",
      borderRadius: 28,
      paddingHorizontal: 22,
      paddingTop: 22,
      paddingBottom: 24,
    },

    question: {
      color: "#111111",
      fontSize: 16 * scale,
      fontWeight: "900",
      marginBottom: 8,
    },

    largeInput: {
      width: "100%",
      minHeight: 84,
      borderRadius: 20,
      backgroundColor: "#D9D9D9",
      paddingHorizontal: 15,
      paddingVertical: 13,
      color: "#111111",
      fontSize: 14 * scale,
      lineHeight: 21 * scale,
      fontWeight: "600",
      marginBottom: 20,
    },

    locationInput: {
      width: "100%",
      minHeight: 82,
      borderRadius: 20,
      backgroundColor: "#D9D9D9",
      paddingHorizontal: 15,
      paddingVertical: 13,
      color: "#111111",
      fontSize: 14 * scale,
      lineHeight: 21 * scale,
      fontWeight: "600",
      marginBottom: 20,
    },

    timeSection: {
      width: "100%",
      position: "relative",
      zIndex: 20,
    },

    timeSelect: {
      width: "100%",
      height: 46,
      borderRadius: 999,
      backgroundColor: "#FFFFFF",
      paddingHorizontal: 15,
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
    },

    timeText: {
      color: "#111111",
      fontSize: 14 * scale,
      fontWeight: "700",
    },

    timePlaceholder: {
      color: "#AAAAAA",
    },

    timeDropdown: {
      width: "100%",
      marginTop: 7,
      backgroundColor: "#FFFFFF",
      borderRadius: 18,
      overflow: "hidden",

      shadowColor: "#000000",
      shadowOpacity: 0.12,
      shadowRadius: 9,

      shadowOffset: {
        width: 0,
        height: 4,
      },

      elevation: 5,
    },

    timeDropdownOption: {
      minHeight: 44,
      paddingHorizontal: 16,
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
    },

    timeDropdownBorder: {
      borderBottomWidth: 1,
      borderBottomColor: "#EEEEEE",
    },

    timeDropdownOptionSelected: {
      backgroundColor: "#FFF3DD",
    },

    timeDropdownText: {
      color: "#333333",
      fontSize: 14 * scale,
      fontWeight: "700",
    },

    timeDropdownTextSelected: {
      color: "#D89B31",
      fontWeight: "900",
    },

    dropdownPressed: {
      opacity: 0.65,
    },

    deadlineQuestion: {
      color: "#111111",
      fontSize: 16 * scale,
      fontWeight: "900",
      marginTop: 58,
      marginBottom: 12,
    },

    deadlineOptions: {
      width: "100%",
      gap: 10,
    },

    deadlineButton: {
      width: "100%",
      height: 43,
      borderRadius: 999,
      backgroundColor: "#FFFFFF",
      alignItems: "center",
      justifyContent: "center",
    },

    deadlineButtonSelected: {
      backgroundColor: "#F7E6C7",
      borderWidth: 2,
      borderColor: "#D89B31",
    },

    deadlineButtonText: {
      color: "#111111",
      fontSize: 14 * scale,
      fontWeight: "800",
    },

    deadlineButtonTextSelected: {
      color: "#9A6519",
    },

    confirmButton: {
      width: "76%",
      height: 52,
      borderRadius: 999,
      backgroundColor: "#D89B31",
      alignItems: "center",
      justifyContent: "center",
      alignSelf: "center",
      marginTop: 16,
    },

    confirmButtonText: {
      color: "#FFFFFF",
      fontSize: 20 * scale,
      fontWeight: "500",
    },

    pressed: {
      opacity: 0.72,
      transform: [{ scale: 0.98 }],
    },
  });