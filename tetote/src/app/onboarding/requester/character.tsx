import { useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  Pressable,
  Image,
  ScrollView,
  useWindowDimensions,
} from "react-native";
import { useRouter } from "expo-router";

const characters = [
  {
    id: 1,
    image: require("../../../../assets/onboarding_asset/c1.png"),
    name: "犬-Dog-",
    type: "Caring type（寄り添う）",
    description: "そばに寄り添って、優しく見守ってくれるよ",
    growth: "成長すれば...\n大型犬に進化するかも？",
  },
  {
    id: 2,
    image: require("../../../../assets/onboarding_asset/c2.png"),
    name: "ウサギ-Rabbit-",
    type: "Cute type（一緒に成長する）",
    description: "おどおどしてるけど一生懸命な性格",
    growth: "成長すれば...\n一人前のうさぎになるかも？",
  },
  {
    id: 3,
    image: require("../../../../assets/onboarding_asset/c3.png"),
    name: "ウマ-Horse-",
    type: "Cool type（頼りになる）",
    description: "力強い性格であなたをサポートするよ",
    growth: "成長すれば...\nかっこいい頼りがいのある馬になるかも？",
  },
];

export default function CharacterScreen() {
  const router = useRouter();
  const { width } = useWindowDimensions();
  const isDesktop = width >= 768;

  const [selectedCharacter, setSelectedCharacter] =
    useState<number | null>(null);

  const handleBack = () => {
    router.back();
  };

  const handleNext = () => {
    if (selectedCharacter === null) return;

    router.push("/help");
  };

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

      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
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
            <View style={styles.progressDot} />
            <View style={styles.progressLine} />
            <View
              style={[
                styles.progressDot,
                styles.progressActive,
              ]}
            />
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

          <Text style={styles.characterTitle}>
            育成するキャラクターを選んでください！
          </Text>

          <View style={styles.characterList}>
            {characters.map((character) => {
              const selected =
                selectedCharacter === character.id;

              return (
                <Pressable
                  key={character.id}
                  onPress={() =>
                    setSelectedCharacter(character.id)
                  }
                  style={({ pressed }) => [
                    styles.characterCard,
                    selected && styles.characterCardSelected,
                    pressed && styles.characterCardPressed,
                  ]}
                >
                  <View style={styles.characterContent}>
                    <View style={styles.imageArea}>
                      <Image
                        source={character.image}
                        style={styles.characterImage}
                      />
                    </View>

                    <View style={styles.characterTextArea}>
                      <Text style={styles.characterName}>
                        {character.name}
                      </Text>

                      <Text style={styles.characterType}>
                        {character.type}
                      </Text>

                      <Text style={styles.characterDescription}>
                        {character.description}
                      </Text>

                      <Text style={styles.characterGrowth}>
                        {character.growth}
                      </Text>
                    </View>
                  </View>

                  {selected && (
                    <View style={styles.selectedBadge}>
                      <Text style={styles.selectedCheck}>
                        ✓
                      </Text>
                    </View>
                  )}
                </Pressable>
              );
            })}
          </View>

          <Pressable
            disabled={selectedCharacter === null}
            onPress={handleNext}
            style={({ pressed }) => [
              styles.button,
              selectedCharacter === null &&
                styles.buttonDisabled,
              pressed &&
                selectedCharacter !== null &&
                styles.buttonPressed,
            ]}
          >
            <Text
              style={[
                styles.buttonText,
                selectedCharacter === null &&
                  styles.buttonTextDisabled,
              ]}
            >
              次に進む
            </Text>
          </Pressable>
        </View>
      </ScrollView>
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

  scrollView: {
    flex: 1,
    width: "100%",
  },

  scrollContent: {
    flexGrow: 1,
    alignItems: "center",
    paddingBottom: 35,
  },

  container: {
    width: "100%",
    minHeight: "100%",
    paddingHorizontal: 28,
    paddingTop: 50,
    paddingBottom: 30,
    alignItems: "center",
  },

  desktopContainer: {
    maxWidth: 520,
    paddingTop: 55,
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

  characterTitle: {
    color: "#111111",
    fontSize: 17,
    lineHeight: 25,
    fontWeight: "700",
    textAlign: "center",
    marginTop: 35,
    marginBottom: 28,
  },

  characterList: {
    width: "100%",
    gap: 14,
  },

  characterCard: {
    width: "100%",
    minHeight: 145,
    borderRadius: 22,
    borderWidth: 2,
    borderColor: "transparent",
    backgroundColor: "#F8ECDC",
    justifyContent: "center",
    paddingHorizontal: 14,
    paddingVertical: 10,
    position: "relative",
  },

  characterCardSelected: {
    borderColor: "#245C2D",
    borderWidth: 3,
    backgroundColor: "#FFF5E9",
  },

  characterCardPressed: {
    opacity: 0.8,
    transform: [{ scale: 0.99 }],
  },

  characterContent: {
    width: "100%",
    flexDirection: "row",
    alignItems: "center",
  },

  imageArea: {
    width: 140,
    alignItems: "center",
    justifyContent: "center",
  },

  characterImage: {
    width: 115,
    height: 115,
    resizeMode: "contain",
  },

  characterTextArea: {
    flex: 1,
    paddingLeft: 4,
    paddingRight: 8,
  },

  characterName: {
    color: "#111111",
    fontSize: 18,
    fontWeight: "800",
    marginBottom: 2,
  },

  characterType: {
    color: "#111111",
    fontSize: 13,
    fontWeight: "700",
    marginBottom: 14,
  },

  characterDescription: {
    color: "#111111",
    fontSize: 12,
    lineHeight: 18,
    fontWeight: "600",
    marginBottom: 2,
  },

  characterGrowth: {
    color: "#111111",
    fontSize: 12,
    lineHeight: 18,
    fontWeight: "600",
  },

  selectedBadge: {
    position: "absolute",
    top: 10,
    right: 12,
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: "#245C2D",
    alignItems: "center",
    justifyContent: "center",
  },

  selectedCheck: {
    color: "#FFFFFF",
    fontSize: 17,
    fontWeight: "800",
  },

  button: {
    width: "65%",
    maxWidth: 280,
    minWidth: 200,
    backgroundColor: "#245C2D",
    borderRadius: 999,
    paddingVertical: 15,
    alignItems: "center",
    marginTop: 30,
  },

  buttonDisabled: {
    backgroundColor: "#BFC8BF",
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

  buttonTextDisabled: {
    color: "#F2F2F2",
  },
});