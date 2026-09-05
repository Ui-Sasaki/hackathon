import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Image,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useFontSize } from "../context/FontSizeContext";
import {
  characterAssetKey,
  characterProgressErrorMessage,
  characterProgressLoadingState,
  evolutionLabel,
  getCharacterProgress,
  progressPercent,
  type CharacterAssetKey,
  type CharacterProgressState,
} from "../features/character/client";

// 段階ごとの画像。require はビルド時に解決されるため、動的なパスは使えない。
const characterImages: Record<CharacterAssetKey, number> = {
  c1: require("../../assets/onboarding_asset/c1.png"),
  c2: require("../../assets/onboarding_asset/c2.png"),
  c3: require("../../assets/onboarding_asset/c3.png"),
};

/**
 * キャラクター（貢献度）画面。
 * 支援回数・ポイント・進化までの残りは GET /character-progress から取得する。
 * 完了した支援だけが数えられ、規則はサーバー側（app/services/character.py）にある。
 */
export default function HelperCharacterScreen() {
  const { scale } = useFontSize();
  const styles = createStyles(scale);

  const [state, setState] = useState<CharacterProgressState>(
    characterProgressLoadingState(),
  );

  const load = useCallback(() => {
    setState(characterProgressLoadingState());
    void getCharacterProgress().then(setState);
  }, []);

  // 初回は初期状態が loading なので、取得だけを行う（effect 内で同期的に setState しない）。
  useEffect(() => {
    void getCharacterProgress().then(setState);
  }, []);

  const progress = state.progress;
  const percent = progressPercent(progress);

  return (
    <View style={styles.screen}>
      <View style={styles.container}>
        <View style={styles.characterArea}>
          <Image
            accessibilityLabel={`キャラクター 段階${progress?.stage ?? 1}`}
            source={characterImages[characterAssetKey(progress?.characterId)]}
            style={styles.characterImage}
            resizeMode="contain"
          />
        </View>

        <View style={styles.progressSection}>
          <Text style={styles.progressText}>
            {evolutionLabel(progress)}
          </Text>

          <View
            accessibilityRole="progressbar"
            accessibilityValue={{ min: 0, max: 100, now: percent }}
            style={styles.progressTrack}
          >
            <View
              style={[
                styles.progressFill,
                {
                  width: `${percent}%`,
                },
              ]}
            />
          </View>

          {state.status === "loading" && (
            <View style={styles.statusRow}>
              <ActivityIndicator size="small" color="#245C2D" />
              <Text style={styles.statusText}>貢献度を読み込んでいます...</Text>
            </View>
          )}

          {state.status === "error" && (
            <View style={styles.statusRow}>
              <Text style={styles.errorText}>
                {characterProgressErrorMessage(state.error)}
              </Text>
              <Pressable
                onPress={load}
                style={({ pressed }) => [styles.retryButton, pressed && styles.pressed]}
              >
                <Text style={styles.retryButtonText}>再読み込み</Text>
              </Pressable>
            </View>
          )}
        </View>

        <Text style={styles.meterTitle}>
          貢献度メーター
        </Text>

        <View style={styles.statsRow}>
          <View style={styles.statColumn}>
            <Text style={styles.statLabel}>
              お手伝い回数
            </Text>

            <View style={styles.statCircle}>
              <Text style={styles.statNumber}>
                {progress ? progress.helpCount : "-"}
              </Text>
            </View>
          </View>

          <View style={styles.statColumn}>
            <Text style={styles.statLabel}>
              獲得ポイント
            </Text>

            <View style={styles.statCircle}>
              <Text style={styles.statPoints}>
                {progress ? progress.currentPoints : "-"}
              </Text>
            </View>
          </View>
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
      paddingTop: 40,
      paddingBottom: 28,
      alignItems: "center",
      transform: [{ translateY: -30 }],
    },

    characterArea: {
      width: "100%",
      alignItems: "center",
      justifyContent: "center",
      marginTop: 50,
    },

    characterImage: {
      width: 230,
      height: 230,
    },

    progressSection: {
      width: "100%",
      alignItems: "center",
      marginTop: 52,
    },

    progressText: {
      color: "#111111",
      fontSize: 15 * scale,
      fontWeight: "800",
      marginBottom: 12,
    },

    progressTrack: {
      width: "92%",
      height: 22,
      borderRadius: 999,
      backgroundColor: "#FFFFFF",
      overflow: "hidden",
    },

    progressFill: {
      height: "100%",
      borderRadius: 999,
      backgroundColor: "#245C2D",
    },

    statusRow: {
      flexDirection: "row",
      alignItems: "center",
      flexWrap: "wrap",
      justifyContent: "center",
      gap: 8,
      marginTop: 10,
    },

    statusText: {
      color: "#777777",
      fontSize: 13 * scale,
    },

    errorText: {
      color: "#A52A2A",
      fontSize: 13 * scale,
      fontWeight: "700",
      textAlign: "center",
    },

    retryButton: {
      borderRadius: 999,
      backgroundColor: "#D9D9D9",
      paddingHorizontal: 14,
      paddingVertical: 6,
    },

    retryButtonText: {
      color: "#333333",
      fontSize: 12 * scale,
      fontWeight: "800",
    },

    pressed: {
      opacity: 0.72,
    },

    meterTitle: {
      color: "#111111",
      fontSize: 16 * scale,
      fontWeight: "800",
      marginTop: 34,
    },

    statsRow: {
      width: "100%",
      flexDirection: "row",
      justifyContent: "space-around",
      marginTop: 22,
    },

    statColumn: {
      alignItems: "center",
      flex: 1,
    },

    statLabel: {
      color: "#111111",
      fontSize: 15 * scale,
      fontWeight: "800",
      marginBottom: 18,
    },

    statCircle: {
      width: 116,
      height: 116,
      borderRadius: 58,
      backgroundColor: "#FFFFFF",
      alignItems: "center",
      justifyContent: "center",
    },

    statNumber: {
      color: "#245C2D",
      fontSize: 46 * scale,
      fontWeight: "900",
    },

    statPoints: {
      color: "#245C2D",
      fontSize: 38 * scale,
      fontWeight: "900",
    },
  });
