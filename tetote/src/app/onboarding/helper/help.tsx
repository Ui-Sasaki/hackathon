import { useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  Pressable,
  ScrollView,
  useWindowDimensions,
  Image,
} from "react-native";
import {
  useRouter,
  useLocalSearchParams,
} from "expo-router";

const categories = [
  "#力仕事",
  "#遊び",
  "#買い物",
  "#動物",
  "#デジタル",
  "#付き添い",
  "#日常生活",
  "#外出・移動",
];

export default function HelperHelpScreen() {
  const router = useRouter();
  const { profileImage } = useLocalSearchParams<{
  profileImage?: string;
}>();

  const { width } = useWindowDimensions();
  const isDesktop = width >= 768;

  const [selected, setSelected] = useState<string[]>([]);

  const toggleCategory = (category: string) => {
    setSelected((current) => {
      if (current.includes(category)) {
        return current.filter((item) => item !== category);
      }

      return [...current, category];
    });
  };

  const handleBack = () => {
    router.replace("/onboarding/helper/helper-profile");
  };

  const handleNext = () => {
    if (selected.length === 0) return;

    router.push("/onboarding/helper/character");
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
            手伝いたい
          </Text>

          <Text style={styles.helpTitle}>
            どんなことを手伝いたいですか？
          </Text>

          <Text style={styles.helpDescription}>
            選択することで
            {"\n"}
            あなたにあった依頼内容が出てきます
          </Text>

          <View style={styles.categoryBox}>
            <View style={styles.categoryWrap}>
              {categories.map((category) => {
                const isSelected =
                  selected.includes(category);

                return (
                  <Pressable
                    key={category}
                    onPress={() =>
                      toggleCategory(category)
                    }
                    style={({ pressed }) => [
                      styles.category,
                      isSelected &&
                        styles.categorySelected,
                      pressed &&
                        styles.categoryPressed,
                    ]}
                  >
                    <Text
                      style={[
                        styles.categoryText,
                        isSelected &&
                          styles.categoryTextSelected,
                      ]}
                    >
                      {category}
                    </Text>
                  </Pressable>
                );
              })}
            </View>
          </View>

          <Text style={styles.selectedTitle}>
            選択中
          </Text>

          <View style={styles.selectedArea}>
<View style={styles.avatarPlaceholder}>
  {profileImage && (
    <Image
      source={{ uri: profileImage }}
      style={styles.avatarImage}
    />
  )}
</View>
            <View style={styles.selectedBar}>
              {selected.length === 0 ? (
                <Text style={styles.emptyText}>
                  興味のある項目を選択してください
                </Text>
              ) : (
                <View style={styles.selectedWrap}>
  {selected.map((category) => (
    <View
      key={category}
      style={styles.selectedChip}
    >
      <Text style={styles.selectedChipText}>
        {category}
      </Text>

      <Pressable
        onPress={() => toggleCategory(category)}
        style={styles.removeButton}
      >
        <Text style={styles.removeText}>×</Text>
      </Pressable>
    </View>
  ))}
</View>
              )}
            </View>
          </View>

          <Pressable
            disabled={selected.length === 0}
            onPress={handleNext}
            style={({ pressed }) => [
              styles.button,
              selected.length === 0 &&
                styles.buttonDisabled,
              pressed &&
                selected.length > 0 &&
                styles.buttonPressed,
            ]}
          >
            <Text
              style={[
                styles.buttonText,
                selected.length === 0 &&
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
  },

  scrollView: {
    flex: 1,
    width: "100%",
  },

  scrollContent: {
    flexGrow: 1,
    alignItems: "center",
    paddingBottom: 40,
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
    backgroundColor: "#F2A329",
  },

  progressLine: {
    flex: 1,
    height: 2,
    backgroundColor: "#245C2D",
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
    marginTop: 30,
  },

  helpTitle: {
    color: "#111111",
    fontSize: 19,
    lineHeight: 27,
    fontWeight: "700",
    textAlign: "center",
    marginTop: 35,
  },

  helpDescription: {
    color: "#111111",
    fontSize: 14,
    lineHeight: 22,
    fontWeight: "600",
    textAlign: "center",
    marginTop: 10,
  },

  categoryBox: {
    width: "100%",
    backgroundColor: "#D5D5D5",
    borderRadius: 30,
    paddingHorizontal: 24,
    paddingVertical: 30,
    marginTop: 28,
  },

  categoryWrap: {
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "center",
    gap: 12,
  },

  category: {
    backgroundColor: "#FFFFFF",
    paddingHorizontal: 16,
    paddingVertical: 9,
    borderRadius: 999,
  },

  categorySelected: {
    backgroundColor: "#245C2D",
  },

  categoryPressed: {
    opacity: 0.75,
    transform: [{ scale: 0.97 }],
  },

  categoryText: {
    color: "#111111",
    fontSize: 15,
    fontWeight: "700",
  },

  categoryTextSelected: {
    color: "#FFFFFF",
  },

  selectedTitle: {
    width: "100%",
    color: "#245C2D",
    fontSize: 14,
    fontWeight: "700",
    marginTop: 26,
    marginBottom: 8,
  },

  selectedArea: {
    width: "100%",
    flexDirection: "row",
    alignItems: "center",
    gap: 14,
  },

  avatarPlaceholder: {
  width: 70,
  height: 70,
  borderRadius: 8,
  backgroundColor: "#D5D5D5",
  overflow: "hidden",
},

  avatarImage: {
  width: "100%",
  height: "100%",
  resizeMode: "cover",
},


  selectedBar: {
  flex: 1,
  minHeight: 70,
  borderRadius: 24,
  backgroundColor: "#D5D5D5",
  justifyContent: "center",
  paddingHorizontal: 12,
  paddingVertical: 12,
},

 selectedWrap: {
  width: "100%",
  flexDirection: "row",
  flexWrap: "wrap",
  alignItems: "center",
  gap: 8,
},

  selectedChip: {
    backgroundColor: "#245C2D",
    paddingLeft: 15,
    paddingRight: 8,
    paddingVertical: 8,
    borderRadius: 999,
    flexDirection: "row",
    alignItems: "center",
    gap: 7,
  },

  selectedChipText: {
    color: "#FFFFFF",
    fontSize: 14,
    fontWeight: "700",
  },

  removeButton: {
    width: 21,
    height: 21,
    borderRadius: 11,
    backgroundColor: "#FFFFFF",
    alignItems: "center",
    justifyContent: "center",
  },

  removeText: {
    color: "#245C2D",
    fontSize: 17,
    lineHeight: 18,
    fontWeight: "700",
  },

  emptyText: {
    color: "#999999",
    fontSize: 12,
    textAlign: "center",
  },

  button: {
    width: "65%",
    maxWidth: 280,
    minWidth: 200,
    backgroundColor: "#245C2D",
    borderRadius: 999,
    paddingVertical: 15,
    alignItems: "center",
    marginTop: 32,
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