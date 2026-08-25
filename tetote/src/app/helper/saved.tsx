import {
  View,
  Text,
  StyleSheet,
  Pressable,
  ScrollView,
  Image,
} from "react-native";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useRequests } from "../../context/RequestsContext";

export default function SavedScreen() {
  const router = useRouter();

  const {
    savedRequests,
    removeSavedRequest,
  } = useRequests();

  return (
    <View style={styles.screen}>
      <View style={styles.container}>
        <View style={styles.header}>
          <Pressable
            onPress={() => router.back()}
            style={({ pressed }) => [
              styles.backButton,
              pressed && styles.pressed,
            ]}
          >
            <Ionicons
              name="arrow-back"
              size={21}
              color="#111111"
            />

            <Text style={styles.backText}>
              戻る
            </Text>
          </Pressable>

          <Text style={styles.headerTitle}>
            依頼保存一覧
          </Text>

          <View style={styles.headerSpacer} />
        </View>

        {savedRequests.length === 0 ? (
          <View style={styles.emptyContainer}>
            <Image
              source={require("../../../assets/onboarding_asset/c1.jpg")}
              style={styles.mascot}
              resizeMode="contain"
            />

            <Text style={styles.emptyText}>
              保存した依頼はありません！
            </Text>
          </View>
        ) : (
          <ScrollView
            showsVerticalScrollIndicator={false}
            contentContainerStyle={styles.list}
          >
            {savedRequests.map((request) => (
              <View
                key={request.id}
                style={styles.card}
              >
                <Pressable
                  onPress={() =>
                    removeSavedRequest(request.id)
                  }
                  style={({ pressed }) => [
                    styles.closeButton,
                    pressed && styles.pressed,
                  ]}
                >
                  <Ionicons
                    name="close"
                    size={25}
                    color="#2C7A3A"
                  />
                </Pressable>

                <Text style={styles.cardTitle}>
                  {request.title}
                </Text>

                <View style={styles.cardBottom}>
                  <View style={styles.personInfo}>
                    <Text style={styles.personText}>
                      {request.location}
                    </Text>

                    <Text style={styles.personText}>
                      {request.gender} {request.age}
                    </Text>
                  </View>

                  <View style={styles.actionArea}>
                    <View style={styles.remainingBadge}>
                      <Text style={styles.remainingText}>
                        あと3日
                      </Text>
                    </View>

                    <Pressable
                      style={({ pressed }) => [
                        styles.acceptButton,
                        pressed && styles.pressed,
                      ]}
                    >
                      <Text style={styles.acceptText}>
                        引き受ける
                      </Text>
                    </Pressable>
                  </View>
                </View>
              </View>
            ))}
          </ScrollView>
        )}
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
    paddingTop: 34,
  },

  header: {
    width: "100%",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 28,
  },

  backButton: {
    minWidth: 74,
    height: 36,
    borderRadius: 999,
    backgroundColor: "#D9D9D9",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 10,
  },

  backText: {
    color: "#111111",
    fontSize: 15,
    fontWeight: "800",
    marginLeft: 1,
  },

  headerTitle: {
    color: "#35410F",
    fontSize: 20,
    fontWeight: "900",
  },

  headerSpacer: {
    width: 74,
  },

  list: {
    paddingBottom: 30,
    gap: 20,
  },

  card: {
    width: "100%",
    minHeight: 175,
    borderRadius: 24,
    backgroundColor: "#D9D9D9",
    paddingHorizontal: 20,
    paddingTop: 20,
    paddingBottom: 18,

    shadowColor: "#000000",
    shadowOpacity: 0.16,
    shadowRadius: 8,
    shadowOffset: {
      width: 0,
      height: 5,
    },
    elevation: 5,
  },

  closeButton: {
    position: "absolute",
    top: 12,
    right: 12,
    width: 36,
    height: 36,
    alignItems: "center",
    justifyContent: "center",
    zIndex: 2,
  },

  cardTitle: {
    color: "#111111",
    fontSize: 20,
    fontWeight: "900",
    paddingRight: 45,
  },

  cardBottom: {
    flexDirection: "row",
    alignItems: "flex-end",
    justifyContent: "space-between",
    marginTop: 28,
  },

  personInfo: {
    gap: 5,
  },

  personText: {
    color: "#111111",
    fontSize: 14,
    fontWeight: "800",
  },

  actionArea: {
    width: "58%",
    alignItems: "stretch",
  },

  remainingBadge: {
    alignSelf: "flex-end",
    width: 130,
    height: 31,
    borderRadius: 999,
    backgroundColor: "#D69A32",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 8,
  },

  remainingText: {
    color: "#FFFFFF",
    fontSize: 13,
    fontWeight: "800",
  },

  acceptButton: {
    width: "100%",
    height: 48,
    borderRadius: 999,
    backgroundColor: "#2D6534",
    alignItems: "center",
    justifyContent: "center",
  },

  acceptText: {
    color: "#FFFFFF",
    fontSize: 17,
    fontWeight: "900",
  },

  emptyContainer: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingBottom: 100,
  },

  mascot: {
    width: 180,
    height: 180,
  },

  emptyText: {
    color: "#111111",
    fontSize: 15,
    fontWeight: "800",
    marginTop: 20,
  },

  pressed: {
    opacity: 0.7,
    transform: [{ scale: 0.97 }],
  },
});