import { useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  Pressable,
  useWindowDimensions,
  Animated,
} from "react-native";
import { useRouter } from "expo-router";

import IllustrationOne from "../../../assets/onboarding_asset/1.svg";
import IllustrationTwo from "../../../assets/onboarding_asset/2.svg";
import IllustrationThree from "../../../assets/onboarding_asset/3.svg";

const slides = [
  {
    Illustration: IllustrationOne,
    text: "手伝ってほしいけど\n頼める人がいない\nそんな悩みありませんか？",
    footer: "（コミュニティ）問題解決",
  },
  {
    Illustration: IllustrationTwo,
    text: "ボランティア活動したいけど\n行動に移せない\nそんな悩みありませんか？",
    footer: "ボランティア活動の可視化",
  },
  {
    Illustration: IllustrationThree,
    text: "ほんのちょっとだけ\n助け合いしてみませんか？",
    footer: "",
  },
];

export default function IntroScreen() {
  const [page, setPage] = useState(0);
  const [isAnimating, setIsAnimating] = useState(false);

  const router = useRouter();
  const { width } = useWindowDimensions();
  const isDesktop = width >= 768;

  const currentSlide = slides[page];
  const Illustration = currentSlide.Illustration;

  // useRef(...).current を描画中に読まない（React の lint に合わせる）
  const [opacity] = useState(() => new Animated.Value(1));
  const [translateX] = useState(() => new Animated.Value(0));

  const handleNext = () => {
    if (isAnimating) return;

    if (page === slides.length - 1) {
      router.push("/onboarding/role");
      return;
    }

    setIsAnimating(true);

    Animated.parallel([
      Animated.timing(opacity, {
        toValue: 0,
        duration: 180,
        useNativeDriver: true,
      }),
      Animated.timing(translateX, {
        toValue: -35,
        duration: 180,
        useNativeDriver: true,
      }),
    ]).start(() => {
      setPage((prev) => prev + 1);
      translateX.setValue(35);

      Animated.parallel([
        Animated.timing(opacity, {
          toValue: 1,
          duration: 260,
          useNativeDriver: true,
        }),
        Animated.spring(translateX, {
          toValue: 0,
          friction: 8,
          tension: 65,
          useNativeDriver: true,
        }),
      ]).start(() => {
        setIsAnimating(false);
      });
    });
  };

  return (
    <View style={styles.screen}>
      <View
        style={[
          styles.container,
          isDesktop && styles.desktopContainer,
        ]}
      >
        <Animated.View
          style={[
            styles.animatedContent,
            {
              opacity,
              transform: [{ translateX }],
            },
          ]}
        >
          <View style={styles.illustrationWrapper}>
            <Illustration
              width={isDesktop ? 340 : 280}
              height={isDesktop ? 260 : 220}
            />
          </View>

          <Text
            style={[
              styles.mainText,
              isDesktop && styles.mainTextDesktop,
            ]}
          >
            {currentSlide.text}
          </Text>

          {!!currentSlide.footer && (
            <View style={styles.footer}>
              <Text style={styles.check}>✓</Text>
              <Text style={styles.footerText}>
                {currentSlide.footer}
              </Text>
            </View>
          )}
        </Animated.View>

        <View style={styles.bottomArea}>
          <View style={styles.dotsContainer}>
            {slides.map((_, index) => (
              <View
                key={index}
                style={[
                  styles.dot,
                  index === page
                    ? styles.activeDot
                    : styles.inactiveDot,
                ]}
              />
            ))}
          </View>

          <Pressable
            disabled={isAnimating}
            onPress={handleNext}
            style={({ pressed }) => [
              styles.button,
              pressed && !isAnimating && styles.buttonPressed,
              isAnimating && styles.buttonDisabled,
            ]}
          >
            <Text style={styles.buttonText}>
              {page === slides.length - 1 ? "開始する" : "次へ"}
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
    paddingHorizontal: 28,
    paddingTop: 80,
    paddingBottom: 44,
    alignItems: "center",
    justifyContent: "space-between",
  },

  desktopContainer: {
    maxWidth: 520,
    paddingTop: 70,
  },

  animatedContent: {
    width: "100%",
    alignItems: "center",
  },

  illustrationWrapper: {
    width: "100%",
    alignItems: "center",
    justifyContent: "center",
    minHeight: 260,
    marginBottom: 24,
  },

  mainText: {
    color: "#245C2D",
    fontSize: 28,
    lineHeight: 42,
    fontWeight: "700",
    textAlign: "center",
    letterSpacing: 0.5,
    marginTop: 8,
  },

  mainTextDesktop: {
    fontSize: 32,
    lineHeight: 48,
  },

  bottomArea: {
    width: "100%",
    alignItems: "center",
  },

  dotsContainer: {
    flexDirection: "row",
    gap: 14,
    marginBottom: 30,
  },

  dot: {
    width: 13,
    height: 13,
    borderRadius: 999,
  },

  activeDot: {
    backgroundColor: "#245C2D",
  },

  inactiveDot: {
    backgroundColor: "#F2A329",
  },

  button: {
    width: "100%",
    maxWidth: 340,
    backgroundColor: "#245C2D",
    paddingVertical: 17,
    borderRadius: 999,
    alignItems: "center",
    justifyContent: "center",
  },

  buttonPressed: {
    opacity: 0.82,
    transform: [{ scale: 0.98 }],
  },

  buttonDisabled: {
    opacity: 0.85,
  },

  buttonText: {
    color: "#FFFFFF",
    fontSize: 18,
    fontWeight: "700",
  },

  footer: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginTop: 26,
  },

  check: {
    color: "#245C2D",
    fontSize: 18,
    fontWeight: "800",
  },

  footerText: {
    color: "#245C2D",
    fontSize: 14,
    fontWeight: "600",
  },
});