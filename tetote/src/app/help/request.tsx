import {
  View,
  Text,
  StyleSheet,
  Pressable,
} from "react-native";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useFontSize } from "../../context/FontSizeContext";

export default function HelpRequestScreen() {
  const router = useRouter();

  const { scale } = useFontSize();
  const styles = createStyles(scale);

  return (
    <View style={styles.screen}>
      <View style={styles.container}>
        <Pressable
          onPress={() => router.replace("/help")}
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

        <View style={styles.options}>
          <Pressable
            onPress={() =>
              router.push("/help/request-voice")
            }
            style={({ pressed }) => [
              styles.optionCard,
              pressed && styles.pressed,
            ]}
          >
            <Ionicons
              name="mic"
              size={42}
              color="#111111"
            />

            <Text style={styles.optionText}>
              音声で入力
            </Text>
          </Pressable>

          <Pressable
            onPress={() =>
              router.push("/help/request-manual")
            }
            style={({ pressed }) => [
              styles.optionCard,
              pressed && styles.pressed,
            ]}
          >
            <Ionicons
              name="hand-left"
              size={42}
              color="#111111"
            />

            <Text style={styles.optionText}>
              手で入力
            </Text>
          </Pressable>
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

    options: {
      width: "100%",
      flexDirection: "row",
      justifyContent: "space-between",
      gap: 18,
      marginTop: 115,
    },

    optionCard: {
      flex: 1,
      height: 310,
      borderRadius: 22,
      backgroundColor: "#D9D9D9",
      alignItems: "center",
      justifyContent: "center",
      gap: 28,
    },

    optionText: {
      color: "#111111",
      fontSize: 17 * scale,
      fontWeight: "800",
    },

    pressed: {
      opacity: 0.72,
      transform: [{ scale: 0.97 }],
    },
  });