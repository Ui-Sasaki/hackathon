import {
  View,
  Text,
  StyleSheet,
  Pressable,
  ScrollView,
  Animated,
  PanResponder,
  ActivityIndicator,
} from "react-native";
import { useState } from "react";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { useRequests } from "../../context/RequestsContext";
import { useFontSize } from "../../context/FontSizeContext";

const tagOptions = [
  "すべて",
  "#運動",
  "#力仕事",
  "#日常生活",
  "#デジタル",
  "#付き添い",
  "#買い物",
  "#動物",
  "#散歩",
  "#外出",
  "#パソコン",
];

export default function HomeScreen() {
  const router = useRouter();

  const { scale } = useFontSize();
const styles = createStyles(scale);


  const {
    requests,
    status,
    errorMessage,
    reload,
    dismissRequest,
    toggleSavedRequest,
    isRequestSaved,
  } = useRequests();

  const [selectedTags, setSelectedTags] =
    useState<string[]>([]);

  const [tagDropdownOpen, setTagDropdownOpen] =
    useState(false);

  // Animated.Value は描画をまたいで同じインスタンスを使う。useRef(...).current を
  // 描画中に読む形は React の lint（refs during render）に反するため、
  // useState の初期化関数で一度だけ作る。
  const [translateX] = useState(() => new Animated.Value(0));
  const [translateY] = useState(() => new Animated.Value(0));
  const [opacity] = useState(() => new Animated.Value(1));

  const toggleTag = (tag: string) => {
    if (tag === "すべて") {
      setSelectedTags([]);
      return;
    }

    setSelectedTags((current) =>
      current.includes(tag)
        ? current.filter(
            (item) => item !== tag
          )
        : [...current, tag]
    );
  };

  const filteredRequests =
    selectedTags.length === 0
      ? requests
      : requests.filter((request) =>
          selectedTags.some((tag) =>
            request.tags.includes(tag)
          )
        );

  const visibleRequests =
    filteredRequests.slice(0, 3);

  const resetCardPosition = () => {
    Animated.parallel([
      Animated.spring(translateX, {
        toValue: 0,
        friction: 5,
        tension: 70,
        useNativeDriver: false,
      }),

      Animated.spring(translateY, {
        toValue: 0,
        friction: 5,
        tension: 70,
        useNativeDriver: false,
      }),
    ]).start();
  };

  const dismissCard = (
    id: string,
    direction: "left" | "right" = "right"
  ) => {
    const targetX =
      direction === "right" ? 650 : -650;

    Animated.parallel([
      Animated.timing(translateX, {
        toValue: targetX,
        duration: 240,
        useNativeDriver: false,
      }),

      Animated.timing(opacity, {
        toValue: 0,
        duration: 200,
        useNativeDriver: false,
      }),
    ]).start(() => {
      dismissRequest(id);

      translateX.setValue(0);
      translateY.setValue(0);
      opacity.setValue(1);
    });
  };

  const panResponder = PanResponder.create({
    onStartShouldSetPanResponder: () => false,

    onMoveShouldSetPanResponder: (
      _,
      gestureState
    ) => {
      const horizontalMovement =
        Math.abs(gestureState.dx);

      const verticalMovement =
        Math.abs(gestureState.dy);

      return (
        horizontalMovement > 8 &&
        horizontalMovement > verticalMovement
      );
    },

    onPanResponderMove: (
      _,
      gestureState
    ) => {
      translateX.setValue(gestureState.dx);
      translateY.setValue(
        gestureState.dy * 0.15
      );
    },

    onPanResponderRelease: (
      _,
      gestureState
    ) => {
      const currentRequest =
        visibleRequests[0];

      if (!currentRequest) {
        translateX.setValue(0);
        translateY.setValue(0);
        return;
      }

      const swipeRight =
  gestureState.dx > 70 ||
  gestureState.vx > 0.45;

const swipeLeft =
  gestureState.dx < -70 ||
  gestureState.vx < -0.45;

      if (swipeRight) {
        dismissCard(
          currentRequest.id,
          "right"
        );
        return;
      }

      if (swipeLeft) {
        dismissCard(
          currentRequest.id,
          "left"
        );
        return;
      }

      resetCardPosition();
    },

    onPanResponderTerminate: () => {
      resetCardPosition();
    },
  });

  const cardRotation =
    translateX.interpolate({
      inputRange: [-300, 0, 300],
      outputRange: [
        "-8deg",
        "0deg",
        "8deg",
      ],
      extrapolate: "clamp",
    });

  return (
    <View style={styles.screen}>
      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={
          styles.scrollContent
        }
        showsVerticalScrollIndicator={false}
        nestedScrollEnabled
      >
        <View style={styles.topControls}>
          <View style={styles.filterBar}>
            <Pressable
              style={({ pressed }) => [
                styles.filterSection,
                pressed &&
                  styles.filterPressed,
              ]}
            >
              <Ionicons
                name="location"
                size={22}
                color="#7A7A7A"
              />

              <Ionicons
                name="chevron-down"
                size={18}
                color="#7A7A7A"
              />
            </Pressable>

            <View
              style={
                styles.tagDropdownWrapper
              }
            >
              <Pressable
                onPress={() =>
                  setTagDropdownOpen(
                    (current) => !current
                  )
                }
                style={({ pressed }) => [
                  styles.tagFilterSection,
                  pressed &&
                    styles.filterPressed,
                ]}
              >
                <Text
                  style={
                    styles.selectedTagText
                  }
                  numberOfLines={1}
                >
                  {selectedTags.length === 0
                    ? "#"
                    : `# ${selectedTags.length}`}
                </Text>

                <Ionicons
                  name={
                    tagDropdownOpen
                      ? "chevron-up"
                      : "chevron-down"
                  }
                  size={18}
                  color="#7A7A7A"
                />
              </Pressable>

              {tagDropdownOpen && (
                <View
                  style={
                    styles.tagDropdown
                  }
                >
                  <ScrollView
                    style={
                      styles.tagDropdownScroll
                    }
                    contentContainerStyle={
                      styles.tagDropdownScrollContent
                    }
                    showsVerticalScrollIndicator={
                      false
                    }
                    nestedScrollEnabled
                  >
                    <Pressable
                      onPress={() =>
                        toggleTag("すべて")
                      }
                      style={({
                        pressed,
                      }) => [
                        styles.tagDropdownItem,

                        selectedTags.length ===
                          0 &&
                          styles.tagDropdownItemSelected,

                        pressed &&
                          styles.filterPressed,
                      ]}
                    >
                      <Text
                        style={[
                          styles.tagDropdownText,

                          selectedTags.length ===
                            0 &&
                            styles.tagDropdownTextSelected,
                        ]}
                      >
                        すべて
                      </Text>

                      {selectedTags.length ===
                        0 && (
                        <Ionicons
                          name="checkmark"
                          size={18}
                          color="#245C2D"
                        />
                      )}
                    </Pressable>

                    {tagOptions
                      .filter(
                        (tag) =>
                          tag !== "すべて"
                      )
                      .map((tag) => {
                        const selected =
                          selectedTags.includes(
                            tag
                          );

                        return (
                          <Pressable
                            key={tag}
                            onPress={() =>
                              toggleTag(tag)
                            }
                            style={({
                              pressed,
                            }) => [
                              styles.tagDropdownItem,

                              selected &&
                                styles.tagDropdownItemSelected,

                              pressed &&
                                styles.filterPressed,
                            ]}
                          >
                            <Text
                              style={[
                                styles.tagDropdownText,

                                selected &&
                                  styles.tagDropdownTextSelected,
                              ]}
                            >
                              {tag}
                            </Text>

                            <View
                              style={[
                                styles.checkbox,

                                selected &&
                                  styles.checkboxSelected,
                              ]}
                            >
                              {selected && (
                                <Ionicons
                                  name="checkmark"
                                  size={14}
                                  color="#FFFFFF"
                                />
                              )}
                            </View>
                          </Pressable>
                        );
                      })}
                  </ScrollView>
                </View>
              )}
            </View>

            <Pressable
              style={({ pressed }) => [
                styles.filterSectionLast,
                pressed &&
                  styles.filterPressed,
              ]}
            >
              <View style={styles.levelRow}>
                <Ionicons
                  name="happy-outline"
                  size={20}
                  color="#2B7A35"
                />

                <Text style={styles.levelText}>
                  Lv ★
                </Text>
              </View>

              <Ionicons
                name="chevron-down"
                size={18}
                color="#7A7A7A"
              />
            </Pressable>
          </View>

          <Pressable
  onPress={() => router.replace("/help")}
  style={({ pressed }) => [
    styles.modeSwitch,
    pressed && styles.modeSwitchPressed,
  ]}
>
  <Text style={styles.modeSwitchText}>
    手伝ってもらう側に切り替える
  </Text>

  <View style={styles.switchCircle}>
    <Ionicons
      name="sync-outline"
      size={26}
      color="#111111"
    />
  </View>
</Pressable>
        </View>

        {status === "loading" ? (
          <View style={styles.emptyState}>
            <ActivityIndicator color="#245C2D" />
            <Text style={styles.emptyTitle}>
              依頼を読み込んでいます
            </Text>
          </View>
        ) : status === "error" ? (
          <View style={styles.emptyState}>
            <Text style={styles.emptyTitle}>
              {errorMessage ??
                "依頼を読み込めませんでした"}
            </Text>

            <Pressable
              onPress={reload}
              style={({ pressed }) => [
                styles.reloadButton,
                pressed && styles.pressed,
              ]}
            >
              <Ionicons
                name="refresh"
                size={18}
                color="#FFFFFF"
              />

              <Text
                style={styles.reloadButtonText}
              >
                もう一度読み込む
              </Text>
            </Pressable>
          </View>
        ) : requests.length === 0 ? (
          <View style={styles.emptyState}>
            <View
              style={
                styles.emptyIcon
              }
            >
              <Ionicons
                name="briefcase-outline"
                size={38}
                color="#245C2D"
              />
            </View>

            <Text
              style={
                styles.emptyTitle
              }
            >
              公開中の依頼はありません
            </Text>

            <Pressable
              onPress={reload}
              style={({ pressed }) => [
                styles.reloadButton,
                pressed && styles.pressed,
              ]}
            >
              <Ionicons
                name="refresh"
                size={18}
                color="#FFFFFF"
              />

              <Text
                style={styles.reloadButtonText}
              >
                読み込む
              </Text>
            </Pressable>
          </View>
        ) : visibleRequests.length > 0 ? (
          <View style={styles.stack}>
            {[...visibleRequests]
              .reverse()
              .map(
                (
                  request,
                  reverseIndex
                ) => {
                  const index =
                    visibleRequests.length -
                    1 -
                    reverseIndex;

                  const isTop =
                    index === 0;

                  const isSaved =
                    isRequestSaved(
                      request.id
                    );

                  return (
                    <Animated.View
                      key={request.id}
                      {...(isTop
                        ? panResponder.panHandlers
                        : {})}
                      style={[
                        styles.card,

                        index === 1 &&
                          styles.cardSecond,

                        index === 2 &&
                          styles.cardThird,

                        isTop && {
                          opacity,

                          transform: [
                            {
                              translateX,
                            },
                            {
                              translateY,
                            },
                            {
                              rotate:
                                cardRotation,
                            },
                          ],
                        },
                      ]}
                    >
                      {isTop ? (
                        <>
                          <View
                            style={
                              styles.cardTop
                            }
                          >
                            <View
                              style={
                                styles.distanceBadge
                              }
                            >
                              <Ionicons
                                name="location-outline"
                                size={15}
                                color="#245C2D"
                              />

                              <Text
                                style={
                                  styles.distanceText
                                }
                              >
                                {
                                  request.distance
                                }
                              </Text>
                            </View>

                            <Pressable
                              onPress={() =>
                                dismissCard(
                                  request.id,
                                  "right"
                                )
                              }
                              style={({
                                pressed,
                              }) => [
                                styles.closeButton,

                                pressed &&
                                  styles.pressed,
                              ]}
                            >
                              <Ionicons
                                name="close"
                                size={31}
                                color="#245C2D"
                              />
                            </Pressable>
                          </View>

                          <View
                            style={
                              styles.tags
                            }
                          >
                            {request.tags.map(
                              (tag) => (
                                <View
                                  key={tag}
                                  style={
                                    styles.tag
                                  }
                                >
                                  <Text
                                    style={
                                      styles.tagText
                                    }
                                  >
                                    {tag}
                                  </Text>
                                </View>
                              )
                            )}
                          </View>

                          <Text
                            style={
                              styles.cardTitle
                            }
                          >
                            {request.title}
                          </Text>

                          <View
                            style={
                              styles.personRow
                            }
                          >
                            <View
                              style={
                                styles.avatarPlaceholder
                              }
                            >
                              <Ionicons
                                name="person"
                                size={31}
                                color="#FFFFFF"
                              />
                            </View>

                            <View
                              style={
                                styles.personInfo
                              }
                            >
                              <Text
                                style={
                                  styles.personText
                                }
                              >
                                {
                                  request.location
                                }
                              </Text>

                              <Text
                                style={
                                  styles.personText
                                }
                              >
                                {request.meta}
                              </Text>
                            </View>
                          </View>

                          <View
                            style={
                              styles.actions
                            }
                          >
                            <Pressable
                              onPress={() =>
                                router.push({
                                  pathname: "/helper/request",
                                  params: {
                                    requestId: request.id,
                                    title: request.title,
                                    description: request.description,
                                  },
                                })
                              }
                              style={({
                                pressed,
                              }) => [
                                styles.detailsButton,

                                pressed &&
                                  styles.pressed,
                              ]}
                            >
                              <Text
                                style={
                                  styles.detailsText
                                }
                              >
                                詳細情報
                              </Text>
                            </Pressable>

                            <Pressable
                              onPress={() =>
                                router.push({
                                  pathname: "/helper/request",
                                  params: {
                                    requestId: request.id,
                                    title: request.title,
                                    description: request.description,
                                  },
                                })
                              }
                              style={({
                                pressed,
                              }) => [
                                styles.acceptButton,

                                pressed &&
                                  styles.pressed,
                              ]}
                            >
                              <Text
                                style={
                                  styles.acceptText
                                }
                              >
                                引き受ける
                              </Text>
                            </Pressable>
                          </View>

                          <View
                            style={
                              styles.bottomRow
                            }
                          >
                            <View>
                              <Text
                                style={
                                  styles.deadlineLabel
                                }
                              >
                                募集期限
                              </Text>

                              <Text
                                style={
                                  styles.deadlineText
                                }
                              >
                                {
                                  request.deadline
                                }
                              </Text>
                            </View>

                            <Pressable
                              onPress={() =>
                                toggleSavedRequest(
                                  request.id
                                )
                              }
                              style={({
                                pressed,
                              }) => [
                                styles.bookmarkButton,

                                pressed &&
                                  styles.pressed,
                              ]}
                            >
                              <Ionicons
                                name={
                                  isSaved
                                    ? "bookmark"
                                    : "bookmark-outline"
                                }
                                size={30}
                                color={
                                  isSaved
                                    ? "#F2A329"
                                    : "#8D8D8D"
                                }
                              />
                            </Pressable>
                          </View>
                        </>
                      ) : (
                        <View
                          style={
                            styles.backgroundCardContent
                          }
                        >
                          <Text
                            style={
                              styles.backgroundCardTitle
                            }
                            numberOfLines={
                              1
                            }
                          >
                            {request.title}
                          </Text>
                        </View>
                      )}
                    </Animated.View>
                  );
                }
              )}
          </View>
        ) : (
          <View style={styles.emptyState}>
            <View
              style={
                styles.emptyIcon
              }
            >
              <Ionicons
                name="search-outline"
                size={38}
                color="#245C2D"
              />
            </View>

            <Text
              style={
                styles.emptyTitle
              }
            >
              条件に合う依頼はありません
            </Text>

            <Text
              style={
                styles.emptyText
              }
            >
              別の条件を選んでみてください
            </Text>
          </View>
        )}

        <Pressable
          onPress={() =>
            router.push(
              "/helper/saved"
            )
          }
          style={({ pressed }) => [
            styles.savedListButton,

            pressed &&
              styles.savedListButtonPressed,
          ]}
        >
          <Text
            style={
              styles.savedListButtonText
            }
          >
            保存一覧を見る
          </Text>

          <Ionicons
            name="bookmark"
            size={24}
            color="#245C2D"
          />
        </Pressable>
      </ScrollView>
    </View>
  );
}

const createStyles = (scale: number) =>
  StyleSheet.create({
    screen: {
      flex: 1,
      backgroundColor: "#FFF5E9",
    },

    scrollView: {
      flex: 1,
      width: "100%",
    },

    scrollContent: {
      width: "100%",
      maxWidth: 520,
      alignSelf: "center",
      paddingHorizontal: 22,
      paddingTop: 36,
      paddingBottom: 10,
    },

    topControls: {
      width: "100%",
      marginBottom: 16,
      position: "relative",
      zIndex: 1000,
      elevation: 1000,
    },

    filterBar: {
      width: "100%",
      height: 48,
      flexDirection: "row",
      backgroundColor: "#FFFFFF",
      borderRadius: 24,
      zIndex: 1001,
      elevation: 1001,
    },

    filterSection: {
      flex: 1,
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      paddingHorizontal: 14,
      borderRightWidth: 1,
      borderRightColor: "#EFE8DF",
    },

    filterSectionLast: {
      flex: 1,
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      paddingHorizontal: 14,
    },

    tagDropdownWrapper: {
      flex: 1,
      position: "relative",
      zIndex: 2000,
      elevation: 2000,
    },

    tagFilterSection: {
      height: 48,
      width: "100%",
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      paddingHorizontal: 14,
      borderRightWidth: 1,
      borderRightColor: "#EFE8DF",
    },

    selectedTagText: {
      color: "#666666",
      fontSize: 17 * scale,
      fontWeight: "700",
      flexShrink: 1,
    },

    tagDropdown: {
      position: "absolute",
      top: 54,
      left: 0,
      width: 190,
      maxHeight: 260,
      backgroundColor: "#FFFFFF",
      borderRadius: 16,
      zIndex: 3000,
      elevation: 3000,
      overflow: "hidden",

      shadowColor: "#000000",
      shadowOpacity: 0.16,
      shadowRadius: 10,

      shadowOffset: {
        width: 0,
        height: 5,
      },
    },

    tagDropdownScroll: {
      maxHeight: 260,
    },

    tagDropdownScrollContent: {
      paddingVertical: 7,
    },

    tagDropdownItem: {
      minHeight: 44,
      paddingHorizontal: 15,
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
    },

    tagDropdownItemSelected: {
      backgroundColor: "#EEF5E9",
    },

    tagDropdownText: {
      color: "#444444",
      fontSize: 14 * scale,
      fontWeight: "600",
    },

    tagDropdownTextSelected: {
      color: "#245C2D",
      fontWeight: "800",
    },

    checkbox: {
      width: 21,
      height: 21,
      borderRadius: 6,
      borderWidth: 2,
      borderColor: "#B5B5B5",
      alignItems: "center",
      justifyContent: "center",
    },

    checkboxSelected: {
      backgroundColor: "#245C2D",
      borderColor: "#245C2D",
    },

    filterPressed: {
      opacity: 0.65,
    },

    levelRow: {
      flexDirection: "row",
      alignItems: "center",
      gap: 5,
    },

    levelText: {
      color: "#2B7A35",
      fontSize: 17 * scale,
      fontWeight: "800",
    },

    modeSwitch: {
      alignSelf: "flex-end",
      marginTop: 11,
      backgroundColor: "#F2A329",
      borderRadius: 999,
      paddingLeft: 18,
      paddingRight: 5,
      height: 50,
      flexDirection: "row",
      alignItems: "center",
      gap: 10,
    },

    modeSwitchPressed: {
      opacity: 0.82,
      transform: [
        {
          scale: 0.98,
        },
      ],
    },

    modeSwitchText: {
      color: "#FFFFFF",
      fontSize: 13 * scale,
      fontWeight: "800",
    },

    switchCircle: {
      width: 40,
      height: 40,
      borderRadius: 20,
      backgroundColor: "#FFFFFF",
      alignItems: "center",
      justifyContent: "center",
    },

    stack: {
      width: "100%",
      height: 450,
      position: "relative",
      zIndex: 1,
    },

    card: {
      position: "absolute",
      top: 0,
      left: 0,
      width: "100%",
      minHeight: 395,
      borderRadius: 26,
      backgroundColor: "#E6F2D9",
      padding: 18,
      zIndex: 3,

      shadowColor: "#000000",
      shadowOpacity: 0.16,
      shadowRadius: 10,

      shadowOffset: {
        width: 0,
        height: 7,
      },

      elevation: 6,
    },

    cardSecond: {
      top: 42,
      zIndex: 2,
      backgroundColor: "#FFE0C4",
      transform: [
        {
          scale: 0.96,
        },
      ],
    },

    cardThird: {
      top: 60,
      zIndex: 1,
      backgroundColor: "#D9D9D9",
      transform: [
        {
          scale: 0.92,
        },
      ],
    },

    cardTop: {
      flexDirection: "row",
      justifyContent: "space-between",
      alignItems: "center",
    },

    distanceBadge: {
      backgroundColor: "#FFFFFF",
      paddingHorizontal: 11,
      paddingVertical: 6,
      borderRadius: 999,
      flexDirection: "row",
      alignItems: "center",
      gap: 5,
    },

    distanceText: {
      color: "#245C2D",
      fontSize: 13 * scale,
      fontWeight: "700",
    },

    closeButton: {
      width: 46,
      height: 46,
      borderRadius: 23,
      backgroundColor: "#D5D5D5",
      alignItems: "center",
      justifyContent: "center",
    },

    tags: {
      flexDirection: "row",
      flexWrap: "wrap",
      gap: 8,
      marginTop: 12,
    },

    tag: {
      backgroundColor: "#CBE6B7",
      paddingHorizontal: 11,
      paddingVertical: 6,
      borderRadius: 999,
    },

    tagText: {
      color: "#245C2D",
      fontSize: 13 * scale,
      fontWeight: "700",
    },

    cardTitle: {
      color: "#111111",
      fontSize: 21 * scale,
      lineHeight: 28 * scale,
      fontWeight: "800",
      marginTop: 16,
    },

    personRow: {
      flexDirection: "row",
      alignItems: "center",
      marginTop: 20,
    },

    avatarPlaceholder: {
      width: 72,
      height: 72,
      borderRadius: 36,
      backgroundColor: "#D5D5D5",
      alignItems: "center",
      justifyContent: "center",
    },

    personInfo: {
      marginLeft: 20,
      gap: 7,
    },

    personText: {
      color: "#111111",
      fontSize: 15 * scale,
      fontWeight: "700",
    },

    actions: {
      flexDirection: "row",
      gap: 12,
      marginTop: 22,
    },

    detailsButton: {
      flex: 1,
      backgroundColor: "#68635B",
      paddingVertical: 12,
      borderRadius: 999,
      alignItems: "center",
    },

    detailsText: {
      color: "#FFFFFF",
      fontSize: 15 * scale,
      fontWeight: "800",
    },

    acceptButton: {
      flex: 1,
      backgroundColor: "#2D6534",
      paddingVertical: 12,
      borderRadius: 999,
      alignItems: "center",
    },

    acceptText: {
      color: "#FFFFFF",
      fontSize: 15 * scale,
      fontWeight: "800",
    },

    bottomRow: {
      flexDirection: "row",
      justifyContent: "space-between",
      alignItems: "center",
      marginTop: 20,
    },

    deadlineLabel: {
      color: "#888888",
      fontSize: 11 * scale,
      fontWeight: "600",
    },

    deadlineText: {
      color: "#555555",
      fontSize: 14 * scale,
      fontWeight: "700",
      marginTop: 2,
    },

    bookmarkButton: {
      width: 54,
      height: 54,
      borderRadius: 27,
      backgroundColor: "#FFF5E9",
      alignItems: "center",
      justifyContent: "center",
    },

    backgroundCardContent: {
      flex: 1,
      justifyContent: "flex-end",
      paddingBottom: 20,
    },

    backgroundCardTitle: {
      color: "#777777",
      fontSize: 18 * scale,
      fontWeight: "700",
    },

    savedListButton: {
      alignSelf: "flex-end",
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "center",
      gap: 10,
      backgroundColor: "#D9D9D9",
      paddingHorizontal: 18,
      height: 52,
      borderRadius: 999,
      marginTop: 4,
    },

    savedListButtonPressed: {
      opacity: 0.75,
      transform: [
        {
          scale: 0.97,
        },
      ],
    },

    savedListButtonText: {
      color: "#111111",
      fontSize: 15 * scale,
      fontWeight: "800",
    },

    pressed: {
      opacity: 0.75,
      transform: [
        {
          scale: 0.97,
        },
      ],
    },

    emptyState: {
      minHeight: 400,
      alignItems: "center",
      justifyContent: "center",
    },

    emptyIcon: {
      width: 80,
      height: 80,
      borderRadius: 40,
      backgroundColor: "#E1EED9",
      alignItems: "center",
      justifyContent: "center",
      marginBottom: 18,
    },

    reloadButton: {
      marginTop: 14,
      height: 44,
      paddingHorizontal: 22,
      borderRadius: 999,
      backgroundColor: "#159326",
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "center",
      gap: 6,
    },

    reloadButtonText: {
      color: "#FFFFFF",
      fontSize: 14 * scale,
      fontWeight: "800",
    },

    emptyTitle: {
      color: "#245C2D",
      fontSize: 18 * scale,
      fontWeight: "800",
    },

    emptyText: {
      color: "#777777",
      fontSize: 13 * scale,
      marginTop: 8,
    },
  });
