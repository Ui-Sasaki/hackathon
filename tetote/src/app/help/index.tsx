import {
  View,
  Text,
  StyleSheet,
  Pressable,
  Image,
} from "react-native";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";

export default function HelpHomeScreen() {
  const router = useRouter();

  return (
    <View style={styles.screen}>
      <View style={styles.container}>
        <View style={styles.topRow}>
          <Pressable
            onPress={() => router.push("/help/profile")}
            style={({ pressed }) => [
              styles.settingsButton,
              pressed && styles.pressed,
            ]}
          >
            <Ionicons
              name="person-circle"
              size={38}
              color="#F2A329"
            />

            <Text style={styles.settingsText}>
              プロフィール
            </Text>
          </Pressable>

          <Pressable
            onPress={() => router.replace("/helper")}
            style={({ pressed }) => [
              styles.switchButton,
              pressed && styles.pressed,
            ]}
          >
            <Text style={styles.switchText}>
              手伝いたい側に切り替える
            </Text>

            <View style={styles.switchCircle}>
              <Ionicons
                name="sync-outline"
                size={23}
                color="#111111"
              />
            </View>
          </Pressable>
        </View>

        <View style={styles.mainContent}>
          <View style={styles.profileCircle}>
            <Ionicons
              name="person"
              size={50}
              color="#FFFFFF"
            />
          </View>

          <Pressable
            onPress={() => router.push("/help/request")}
            style={({ pressed }) => [
              styles.mainButton,
              pressed && styles.pressed,
            ]}
          >
            <Text style={styles.mainButtonText}>
              お手伝いをしてもらう
            </Text>
          </Pressable>

          <View style={styles.mascotArea}>
            <Image
              source={require(
                "../../../assets/onboarding_asset/c1.png"
              )}
              style={styles.mascot}
              resizeMode="contain"
            />
          </View>

          <Pressable
            onPress={() => router.push("/help/character")}
            style={({ pressed }) => [
              styles.characterButton,
              pressed && styles.pressed,
            ]}
          >
            <Text style={styles.characterButtonText}>
              キャラクターを見に行く
            </Text>
          </Pressable>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
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
    paddingTop: 26,
    paddingBottom: 12,
    alignItems: "center",
  },

  topRow: {
    width: "100%",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },

  settingsButton: {
    width: 72,
    alignItems: "center",
  },

  settingsText: {
    color: "#F2A329",
    fontSize: 12,
    fontWeight: "800",
    marginTop: 2,
  },

  switchButton: {
    height: 46,
    backgroundColor: "#245C2D",
    borderRadius: 999,
    paddingLeft: 16,
    paddingRight: 4,
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },

  switchText: {
    color: "#FFFFFF",
    fontSize: 12,
    fontWeight: "800",
  },

  switchCircle: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: "#FFFFFF",
    alignItems: "center",
    justifyContent: "center",
  },

  mainContent: {
    width: "100%",
    alignItems: "center",
    marginTop: 18,
  },

  profileCircle: {
    width: 136,
    height: 136,
    borderRadius: 68,
    backgroundColor: "#D9D9D9",
    alignItems: "center",
    justifyContent: "center",
  },

  mainButton: {
    width: "80%",
    height: 52,
    borderRadius: 999,
    backgroundColor: "#D9D9D9",
    alignItems: "center",
    justifyContent: "center",
    marginTop: 18,
  },

  mainButtonText: {
    color: "#111111",
    fontSize: 18,
    fontWeight: "900",
  },

mascotArea: {
  alignItems: "center",
  justifyContent: "center",
  marginTop: 20,
  marginBottom: 12,
},

  mascot: {
    width: 160,
    height: 160,
  },

  characterButton: {
    width: "84%",
    height: 52,
    borderRadius: 999,
    backgroundColor: "#D9D9D9",
    alignItems: "center",
    justifyContent: "center",
  },

  characterButtonText: {
    color: "#111111",
    fontSize: 18,
    fontWeight: "900",
  },

  pressed: {
    opacity: 0.75,
    transform: [{ scale: 0.98 }],
  },
});