import {
  View,
  Text,
  StyleSheet,
  Pressable,
  useWindowDimensions,
} from "react-native";
import { useRouter } from "expo-router";

import HelpIcon from "../../../assets/onboarding_asset/help.svg";
import HelperIcon from "../../../assets/onboarding_asset/helper.svg";

export default function RoleScreen() {
  const router = useRouter();
  const { width } = useWindowDimensions();

  const isDesktop = width >= 768;

  const selectRequester = () => {
    router.push("/onboarding/requester/requester-profile");
  };

  const selectHelper = () => {
    router.push("/onboarding/helper/helper-profile");
  };

  return (
    <View style={styles.screen}>
      <View
        style={[
          styles.container,
          isDesktop && styles.desktopContainer,
        ]}
      >
        <View style={styles.progress}>
          <View style={[styles.progressDot, styles.progressActive]} />
          <View style={styles.progressLine} />
          <View style={styles.progressDot} />
          <View style={styles.progressLine} />
          <View style={styles.progressDot} />
          <View style={styles.progressLine} />
          <View style={styles.progressDot} />
        </View>

        <Text
          style={[
            styles.title,
            isDesktop && styles.titleDesktop,
          ]}
        >
          まずはプロフィールを作りましょう！
        </Text>

        <Text style={styles.question}>
          あなたはどちらですか？
        </Text>

        <View
          style={[
            styles.roles,
            isDesktop && styles.rolesDesktop,
          ]}
        >
          <Pressable
            onPress={selectRequester}
            style={({ pressed }) => [
              styles.roleOption,
              pressed && styles.rolePressed,
            ]}
          >
            <Text style={styles.roleLabel}>
              手伝ってほしい
            </Text>

            <View style={styles.iconWrapper}>
              <HelpIcon
                width={isDesktop ? 150 : 130}
                height={isDesktop ? 150 : 130}
              />
            </View>

            <Text style={styles.roleDescription}>
              困りごとを{"\n"}お願いしたい
            </Text>
          </Pressable>

          <Pressable
            onPress={selectHelper}
            style={({ pressed }) => [
              styles.roleOption,
              pressed && styles.rolePressed,
            ]}
          >
            <Text style={styles.roleLabel}>
              手伝いたい
            </Text>

            <View style={styles.iconWrapper}>
              <HelperIcon
                width={isDesktop ? 150 : 130}
                height={isDesktop ? 150 : 130}
              />
            </View>

            <Text style={styles.roleDescription}>
              誰かの困りごとを{"\n"}助けたい
            </Text>
          </Pressable>
        </View>

        <Text style={styles.hint}>
          あとから変更できます
        </Text>
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
    paddingHorizontal: 28,
    paddingTop: 50,
    alignItems: "center",
  },

  desktopContainer: {
    maxWidth: 620,
    paddingTop: 60,
  },

  progress: {
    flexDirection: "row",
    alignItems: "center",
    width: "75%",
    maxWidth: 320,
    marginBottom: 35,
  },

  progressDot: {
    width: 12,
    height: 12,
    borderRadius: 999,
    backgroundColor: "#D8DEE0",
  },

  progressActive: {
    backgroundColor: "#245C2D",
  },

  progressLine: {
    flex: 1,
    height: 2,
    backgroundColor: "#D8DEE0",
  },

  title: {
    color: "#245C2D",
    fontSize: 22,
    fontWeight: "700",
    textAlign: "center",
  },

  titleDesktop: {
    fontSize: 27,
  },

  question: {
    color: "#111111",
    fontSize: 18,
    fontWeight: "700",
    marginTop: 55,
    marginBottom: 40,
  },

  roles: {
    width: "100%",
    flexDirection: "row",
    justifyContent: "center",
    gap: 24,
  },

  rolesDesktop: {
    gap: 50,
  },

  roleOption: {
    flex: 1,
    maxWidth: 210,
    alignItems: "center",
    paddingVertical: 12,
    borderRadius: 24,
  },

  rolePressed: {
    opacity: 0.8,
    transform: [{ scale: 0.97 }],
  },

  roleLabel: {
    color: "#111111",
    fontSize: 17,
    fontWeight: "700",
    marginBottom: 18,
  },

  iconWrapper: {
    alignItems: "center",
    justifyContent: "center",
  },

  roleDescription: {
    marginTop: 18,
    color: "#245C2D",
    fontSize: 14,
    fontWeight: "600",
    lineHeight: 21,
    textAlign: "center",
  },

  hint: {
    position: "absolute",
    bottom: 45,
    color: "#7B7B7B",
    fontSize: 13,
  },
});