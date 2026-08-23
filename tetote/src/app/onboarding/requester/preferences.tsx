import { useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  Pressable,
  Switch,
  useWindowDimensions,
} from "react-native";
import { useRouter } from "expo-router";
import Slider from "@react-native-community/slider";
import {
  requestRecordingPermissionsAsync,
  getRecordingPermissionsAsync,
} from "expo-audio";

export default function PreferencesScreen() {
  const router = useRouter();
  const { width } = useWindowDimensions();
  const isDesktop = width >= 768;

  const [textSize, setTextSize] = useState(0.5);
  const [voiceInput, setVoiceInput] = useState(false);

  const handleVoiceInputChange = async (enabled: boolean) => {
    if (!enabled) {
      setVoiceInput(false);
      return;
    }

    const existingPermission =
      await getRecordingPermissionsAsync();

    if (existingPermission.granted) {
      setVoiceInput(true);
      return;
    }

    const permission =
      await requestRecordingPermissionsAsync();

    if (permission.granted) {
      setVoiceInput(true);
    } else {
      setVoiceInput(false);
    }
  };

  const handleBack = () => {
    router.back();
  };

  const handleNext = () => {
    router.push("/onboarding/requester/character");
  };

  const previewFontSize = 16 + textSize * 16;

  return (
    <View style={styles.screen}>
      <Pressable
        onPress={handleBack}
        style={({ pressed }) => [
          styles.backButton,
          pressed && styles.backButtonPressed,
        ]}
      >
        <Text style={styles.backButtonText}>‹</Text>
      </Pressable>

      <View
        style={[
          styles.container,
          isDesktop && styles.desktopContainer,
        ]}
      >
        <View style={styles.progress}>
          <View style={styles.progressDot} />
          <View style={styles.progressLine} />
          <View style={styles.progressDot} />
          <View style={styles.progressLine} />

          <View
            style={[
              styles.progressDot,
              styles.progressActive,
            ]}
          />

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

        <Text style={styles.roleTitle}>
          手伝ってほしい
        </Text>

        <View style={styles.content}>
          <Text style={styles.sectionTitle}>
            アプリ設定
          </Text>

          <Text style={styles.settingTitle}>
            文字の大きさ
          </Text>

          <View style={styles.sliderRow}>
            <Text style={styles.smallLabel}>
              小さい
            </Text>

            <Slider
              style={styles.slider}
              minimumValue={0}
              maximumValue={1}
              step={0.05}
              value={textSize}
              onValueChange={setTextSize}
              minimumTrackTintColor="#5A5A5A"
              maximumTrackTintColor="#D7D7D7"
              thumbTintColor="#5A5A5A"
            />

            <Text style={styles.largeLabel}>
              大きい
            </Text>
          </View>

          <View style={styles.previewArea}>
            <Text
              style={[
                styles.previewText,
                {
                  fontSize: previewFontSize,
                  lineHeight: previewFontSize * 1.35,
                },
              ]}
            >
              文字サイズのプレビュー
            </Text>
          </View>

          <Text style={styles.voiceTitle}>
            音声入力をオンにしますか？
          </Text>

          <Switch
            value={voiceInput}
            onValueChange={handleVoiceInputChange}
            trackColor={{
              false: "#D8DDE0",
              true: "#8CB78F",
            }}
            thumbColor="#FFFFFF"
            style={styles.switch}
          />

          <Text style={styles.voiceHint}>
            困りごとの入力などを音声で行えるようになります
          </Text>
        </View>

        <Pressable
          onPress={handleNext}
          style={({ pressed }) => [
            styles.button,
            pressed && styles.buttonPressed,
          ]}
        >
          <Text style={styles.buttonText}>
            次に進む
          </Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: "#FFF5E9",
  },

  backButton: {
    position: "absolute",
    top: 28,
    left: 24,
    width: 44,
    height: 44,
    borderRadius: 22,
    alignItems: "center",
    justifyContent: "center",
    zIndex: 50,
  },

  backButtonPressed: {
    opacity: 0.55,
  },

  backButtonText: {
    color: "#245C2D",
    fontSize: 42,
    lineHeight: 42,
    fontWeight: "400",
  },

  container: {
    flex: 1,
    width: "100%",
    paddingHorizontal: 28,
    paddingTop: 50,
    paddingBottom: 40,
    alignItems: "center",
  },

  desktopContainer: {
    maxWidth: 520,
    paddingTop: 55,
    alignSelf: "center",
  },

  progress: {
    flexDirection: "row",
    alignItems: "center",
    width: "72%",
    maxWidth: 300,
    marginBottom: 34,
  },

  progressDot: {
    width: 12,
    height: 12,
    borderRadius: 999,
    backgroundColor: "#D8DDE0",
  },

  progressActive: {
    backgroundColor: "#245C2D",
  },

  progressLine: {
    flex: 1,
    height: 2,
    backgroundColor: "#F2A329",
  },

  title: {
    color: "#245C2D",
    fontSize: 22,
    lineHeight: 30,
    fontWeight: "700",
    textAlign: "center",
  },

  titleDesktop: {
    fontSize: 27,
  },

  roleTitle: {
    color: "#111111",
    fontSize: 18,
    fontWeight: "700",
    marginTop: 35,
  },

  content: {
    width: "100%",
    marginTop: 35,
    alignItems: "center",
  },

  sectionTitle: {
    width: "100%",
    color: "#111111",
    fontSize: 18,
    fontWeight: "700",
    marginBottom: 30,
  },

  settingTitle: {
    color: "#111111",
    fontSize: 18,
    fontWeight: "700",
    marginBottom: 18,
  },

  sliderRow: {
    width: "100%",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
  },

  slider: {
    flex: 1,
    maxWidth: 230,
    height: 40,
    marginHorizontal: 10,
  },

  smallLabel: {
    color: "#111111",
    fontSize: 15,
    fontWeight: "700",
  },

  largeLabel: {
    color: "#111111",
    fontSize: 21,
    fontWeight: "700",
  },

  previewArea: {
    minHeight: 70,
    width: "100%",
    alignItems: "center",
    justifyContent: "center",
    marginTop: 12,
  },

  previewText: {
    color: "#245C2D",
    fontWeight: "700",
    textAlign: "center",
  },

  voiceTitle: {
    color: "#111111",
    fontSize: 18,
    fontWeight: "700",
    marginTop: 45,
    marginBottom: 24,
  },

  switch: {
    transform: [{ scale: 1.1 }],
  },

  voiceHint: {
    color: "#777777",
    fontSize: 12,
    textAlign: "center",
    marginTop: 14,
  },

  button: {
    width: "65%",
    maxWidth: 280,
    minWidth: 200,
    backgroundColor: "#245C2D",
    borderRadius: 999,
    paddingVertical: 15,
    alignItems: "center",
    marginTop: "auto",
  },

  buttonPressed: {
    opacity: 0.82,
    transform: [{ scale: 0.98 }],
  },

  buttonText: {
    color: "#FFFFFF",
    fontSize: 17,
    fontWeight: "700",
  },
});