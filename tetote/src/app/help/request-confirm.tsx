import { useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  Pressable,
  ScrollView,
  Modal,
} from "react-native";
import {
  useLocalSearchParams,
  useRouter,
} from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useFontSize } from "../../context/FontSizeContext";

export default function RequestConfirmScreen() {
  const router = useRouter();
  const { scale } = useFontSize();
  const styles = createStyles(scale);

  const [successVisible, setSuccessVisible] =
    useState(false);

  const {
    content,
    location,
    time,
    deadline,
  } = useLocalSearchParams<{
    content?: string;
    location?: string;
    time?: string;
    deadline?: string;
  }>();

  const handleSubmit = () => {
    setSuccessVisible(true);

    setTimeout(() => {
      setSuccessVisible(false);
      router.replace("/help");
    }, 2000);
  };

  return (
    <View style={styles.screen}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.container}>
          <View style={styles.header}>
            <Pressable
              onPress={() => router.back()}
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
              依頼確認
            </Text>

            <Ionicons
              name="hand-left"
              size={42}
              color="#191600"
            />
          </View>

          <View style={styles.confirmCard}>
            <Text style={styles.sectionTitle}>
              依頼内容
            </Text>

            <View style={styles.infoBox}>
              <Text style={styles.infoText}>
                {content || "未入力"}
              </Text>
            </View>

            <Text style={styles.sectionTitle}>
              場所
            </Text>

            <View style={styles.infoBox}>
              <Text style={styles.infoText}>
                {location || "未入力"}
              </Text>
            </View>

            <Text style={styles.sectionTitle}>
              必要な時間
            </Text>

            <View style={styles.smallInfoBox}>
              <Text style={styles.infoText}>
                {time || "未選択"}
              </Text>
            </View>

            <Text style={styles.sectionTitle}>
              依頼期限
            </Text>

            <View style={styles.smallInfoBox}>
              <Text style={styles.infoText}>
                {deadline || "未選択"}
              </Text>
            </View>

            <View style={styles.noticeBox}>
              <Ionicons
                name="information-circle-outline"
                size={22}
                color="#D89B31"
              />

              <Text style={styles.noticeText}>
                内容を確認して、問題がなければ依頼してください
              </Text>
            </View>

            <Pressable
              onPress={handleSubmit}
              style={({ pressed }) => [
                styles.submitButton,
                pressed && styles.pressed,
              ]}
            >
              <Text style={styles.submitButtonText}>
                依頼する
              </Text>
            </Pressable>

            <Pressable
              onPress={() => router.back()}
              style={({ pressed }) => [
                styles.editButton,
                pressed && styles.pressed,
              ]}
            >
              <Text style={styles.editButtonText}>
                内容を修正する
              </Text>
            </Pressable>
          </View>
        </View>
      </ScrollView>

      <Modal
        visible={successVisible}
        transparent
        animationType="fade"
        statusBarTranslucent
      >
        <View style={styles.modalOverlay}>
          <View style={styles.successModal}>
            <View style={styles.successIcon}>
              <Ionicons
                name="checkmark"
                size={40}
                color="#FFFFFF"
              />
            </View>

            <Text style={styles.successTitle}>
              依頼完了しました！
            </Text>

            <Text style={styles.successText}>
              応募が来るまでお待ちください
            </Text>
          </View>
        </View>
      </Modal>
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
      paddingBottom: 30,
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

    confirmCard: {
      width: "100%",
      borderWidth: 2,
      borderColor: "#F2A329",
      borderRadius: 28,
      paddingHorizontal: 22,
      paddingTop: 24,
      paddingBottom: 24,
    },

    sectionTitle: {
      color: "#111111",
      fontSize: 15 * scale,
      fontWeight: "900",
      marginBottom: 8,
    },

    infoBox: {
      width: "100%",
      minHeight: 74,
      borderRadius: 18,
      backgroundColor: "#FFFFFF",
      paddingHorizontal: 16,
      paddingVertical: 14,
      justifyContent: "center",
      marginBottom: 20,
    },

    smallInfoBox: {
      width: "100%",
      minHeight: 48,
      borderRadius: 999,
      backgroundColor: "#FFFFFF",
      paddingHorizontal: 16,
      justifyContent: "center",
      marginBottom: 20,
    },

    infoText: {
      color: "#333333",
      fontSize: 14 * scale,
      lineHeight: 21 * scale,
      fontWeight: "700",
    },

    noticeBox: {
      width: "100%",
      backgroundColor: "#FFF0D6",
      borderRadius: 16,
      paddingHorizontal: 14,
      paddingVertical: 12,
      flexDirection: "row",
      alignItems: "center",
      gap: 9,
      marginTop: 4,
    },

    noticeText: {
      flex: 1,
      color: "#8B651F",
      fontSize: 12 * scale,
      lineHeight: 18 * scale,
      fontWeight: "700",
    },

    submitButton: {
      width: "76%",
      height: 52,
      borderRadius: 999,
      backgroundColor: "#D89B31",
      alignItems: "center",
      justifyContent: "center",
      alignSelf: "center",
      marginTop: 24,
    },

    submitButtonText: {
      color: "#FFFFFF",
      fontSize: 20 * scale,
      fontWeight: "600",
    },

    editButton: {
      width: "76%",
      height: 48,
      borderRadius: 999,
      backgroundColor: "#D9D9D9",
      alignItems: "center",
      justifyContent: "center",
      alignSelf: "center",
      marginTop: 10,
    },

    editButtonText: {
      color: "#333333",
      fontSize: 14 * scale,
      fontWeight: "800",
    },

    modalOverlay: {
      flex: 1,
      backgroundColor: "rgba(0, 0, 0, 0.3)",
      alignItems: "center",
      justifyContent: "center",
      paddingHorizontal: 28,
    },

    successModal: {
      width: "100%",
      maxWidth: 360,
      backgroundColor: "#FFF5E9",
      borderRadius: 28,
      paddingHorizontal: 28,
      paddingVertical: 38,
      alignItems: "center",

      shadowColor: "#000000",
      shadowOpacity: 0.15,
      shadowRadius: 16,
      shadowOffset: {
        width: 0,
        height: 8,
      },

      elevation: 8,
    },

    successIcon: {
      width: 70,
      height: 70,
      borderRadius: 35,
      backgroundColor: "#D89B31",
      alignItems: "center",
      justifyContent: "center",
      marginBottom: 20,
    },

    successTitle: {
      color: "#D89B31",
      fontSize: 21 * scale,
      fontWeight: "900",
      textAlign: "center",
    },

    successText: {
      color: "#555555",
      fontSize: 14 * scale,
      fontWeight: "700",
      textAlign: "center",
      marginTop: 10,
    },

    pressed: {
      opacity: 0.72,
      transform: [{ scale: 0.98 }],
    },
  });