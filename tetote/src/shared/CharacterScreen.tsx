import {
  View,
  Text,
  StyleSheet,
  Image,
} from "react-native";
import { useFontSize } from "../context/FontSizeContext";

export default function HelperCharacterScreen() {
  const { scale } = useFontSize();
  const styles = createStyles(scale);

  const currentPoints = 250;
  const pointsUntilEvolution = 100;
  const helpCount = 4;

  return (
    <View style={styles.screen}>
      <View style={styles.container}>
        <View style={styles.characterArea}>
          <Image
            source={require(
              "../../assets/onboarding_asset/c1.jpg"
            )}
            style={styles.characterImage}
            resizeMode="contain"
          />
        </View>

        <View style={styles.progressSection}>
          <Text style={styles.progressText}>
            進化まであと{pointsUntilEvolution}pt
          </Text>

          <View style={styles.progressTrack}>
            <View
              style={[
                styles.progressFill,
                {
                  width: "35%",
                },
              ]}
            />
          </View>
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
                {helpCount}
              </Text>
            </View>
          </View>

          <View style={styles.statColumn}>
            <Text style={styles.statLabel}>
              獲得ポイント
            </Text>

            <View style={styles.statCircle}>
              <Text style={styles.statPoints}>
                {currentPoints}
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