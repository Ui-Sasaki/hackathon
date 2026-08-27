import { useEffect, useState } from "react";
import {
  View,
  Text,
  TextInput,
  StyleSheet,
  Pressable,
  ScrollView,
} from "react-native";
import {
  usePathname,
  useRouter,
} from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useAuth } from "../auth/AuthContext";
import { profileErrorKind, profileErrorMessage } from "../auth/profile-state";
import { useFontSize } from "../context/FontSizeContext";

export default function ProfileScreen() {
  const router = useRouter();
  const pathname = usePathname();

  const { scale } = useFontSize();
  const styles = createStyles(scale);
  const { profile, refreshProfile, updateProfile } = useAuth();

  const [username, setUsername] = useState("");
  const [gender, setGender] = useState("");
  const [age, setAge] = useState("");
  const [university, setUniversity] = useState("");
  const [interest, setInterest] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState("");

  useEffect(() => {
    let active = true;
    refreshProfile()
      .then((value) => {
        if (!active) return;
        setUsername(value.displayName);
        setGender(value.gender ?? "");
        setAge(value.age?.toString() ?? "");
        setUniversity(value.university ?? "");
        setInterest(value.interest ?? "");
        setMessage(value.message ?? "");
      })
      .catch((error) => {
        if (active) setNotice(profileErrorMessage(profileErrorKind(error)));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, [refreshProfile]);

  const saveProfile = async () => {
    if (saving || loading) return;
    setSaving(true);
    setNotice("");
    try {
      await updateProfile({
        displayName: username.trim(),
        gender: gender.trim(),
        age: age.trim() || null,
        university: university.trim() || null,
        interest: interest.trim(),
        message: message.trim(),
      });
      setNotice("プロフィールを更新しました");
    } catch (error) {
      setNotice(profileErrorMessage(profileErrorKind(error)));
    } finally {
      setSaving(false);
    }
  };

  const handleSettings = () => {
    if (pathname.startsWith("/help")) {
      router.push("/help/settings");
    } else {
      router.push("/helper/settings");
    }
  };

  return (
    <View style={styles.screen}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.container}>
          <Pressable
            onPress={handleSettings}
            style={({ pressed }) => [
              styles.settingsButton,
              pressed && styles.pressed,
            ]}
          >
            <Ionicons
              name="settings"
              size={36}
              color="#159326"
            />
          </Pressable>

          <View style={styles.profileCircle}>
            <Ionicons
              name="person"
              size={48}
              color="#FFFFFF"
            />
          </View>

          <View style={styles.verifiedRow}>
            <Ionicons
              name="checkmark-circle"
              size={20}
              color="#55A8D4"
            />

            <Text style={styles.verifiedText}>
              {profile?.verificationStatus === "approved"
                ? "本人確認済み"
                : profile?.verificationStatus === "pending"
                  ? "本人確認の審査中"
                  : "本人確認は未完了です"}
            </Text>
          </View>

          <View style={styles.photoRow}>
            <Text style={styles.photoLabel}>
              アイコンを変える
            </Text>

            <Pressable
              style={({ pressed }) => [
                styles.photoButton,
                pressed && styles.pressed,
              ]}
            >
              <Text style={styles.photoButtonText}>
                写真を変更
              </Text>
            </Pressable>

            <View style={styles.cameraCircle}>
              <Ionicons
                name="camera"
                size={28}
                color="#FFFFFF"
              />
            </View>
          </View>

          <View style={styles.form}>
            <ProfileField
              label="ユーザー名"
              value={username}
              onChangeText={setUsername}
              scale={scale}
            />

            <ProfileField
              label="性別"
              value={gender}
              onChangeText={setGender}
              scale={scale}
            />

            <ProfileField
              label="年代"
              value={age}
              onChangeText={setAge}
              scale={scale}
            />

            <ProfileField
              label="大学名"
              value={university}
              onChangeText={setUniversity}
              scale={scale}
            />

            <ProfileField
              label="興味"
              value={interest}
              onChangeText={setInterest}
              scale={scale}
            />
          </View>

          <View style={styles.messageSection}>
            <Text style={styles.messageLabel}>
              一言メッセージ
            </Text>

            <TextInput
              value={message}
              onChangeText={setMessage}
              multiline
              textAlignVertical="top"
              style={styles.messageInput}
            />
          </View>

          <View style={styles.statsRow}>
            <View style={styles.stat}>
              <Text style={styles.statTitle}>
                活動履歴
              </Text>

              <View style={styles.statCircle}>
                <Text style={styles.statNumber}>
                  0
                </Text>
              </View>
            </View>

            <View style={styles.stat}>
              <Text style={styles.statTitle}>
                達成回数
              </Text>

              <View style={styles.statCircle}>
                <Text style={styles.statNumber}>
                  0
                </Text>
              </View>
            </View>
          </View>

          {!!notice && (
            <Text accessibilityLiveRegion="polite" style={styles.notice}>
              {notice}
            </Text>
          )}

          <Pressable
            disabled={saving || loading}
            onPress={saveProfile}
            style={({ pressed }) => [
              styles.saveButton,
              (saving || loading) && styles.saveButtonDisabled,
              pressed && styles.pressed,
            ]}
          >
            <Text style={styles.saveButtonText}>
              {loading ? "取得中..." : saving ? "更新中..." : "保存する"}
            </Text>
          </Pressable>
        </View>
      </ScrollView>
    </View>
  );
}

function ProfileField({
  label,
  value,
  onChangeText,
  scale,
}: {
  label: string;
  value: string;
  onChangeText: (text: string) => void;
  scale: number;
}) {
  return (
    <View style={fieldStyles.fieldRow}>
      <Text
        style={[
          fieldStyles.fieldLabel,
          {
            fontSize: 14 * scale,
          },
        ]}
      >
        {label}
      </Text>

      <TextInput
        value={value}
        onChangeText={onChangeText}
        style={[
          fieldStyles.fieldInput,
          {
            fontSize: 14 * scale,
          },
        ]}
      />
    </View>
  );
}

const createStyles = (scale: number) =>
  StyleSheet.create({
    screen: {
      flex: 1,
      backgroundColor: "#FFF5E9",
    },

    scrollContent: {
      flexGrow: 1,
      alignItems: "center",
      paddingBottom: 40,
    },

    container: {
      width: "100%",
      maxWidth: 520,
      paddingHorizontal: 28,
      paddingTop: 42,
    },

    settingsButton: {
      position: "absolute",
      top: 40,
      right: 28,
      zIndex: 10,
      width: 48,
      height: 48,
      alignItems: "center",
      justifyContent: "center",
    },

    profileCircle: {
      width: 112,
      height: 112,
      borderRadius: 56,
      backgroundColor: "#D9D9D9",
      alignItems: "center",
      justifyContent: "center",
      alignSelf: "center",
      marginTop: 12,
    },

    verifiedRow: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "center",
      gap: 5,
      marginTop: 8,
    },

    verifiedText: {
      color: "#111111",
      fontSize: 13 * scale,
      fontWeight: "800",
    },

    photoRow: {
      width: "100%",
      flexDirection: "row",
      alignItems: "center",
      marginTop: 18,
    },

    photoLabel: {
      color: "#111111",
      fontSize: 14 * scale,
      fontWeight: "800",
      flex: 1,
    },

    photoButton: {
      backgroundColor: "#E5E5E5",
      borderRadius: 999,
      paddingHorizontal: 13,
      paddingVertical: 8,
      marginRight: 9,
    },

    photoButtonText: {
      color: "#111111",
      fontSize: 12 * scale,
      fontWeight: "700",
    },

    cameraCircle: {
      width: 54,
      height: 54,
      borderRadius: 27,
      backgroundColor: "#159326",
      alignItems: "center",
      justifyContent: "center",
    },

    form: {
      width: "100%",
      marginTop: 8,
      gap: 9,
    },

    messageSection: {
      width: "100%",
      marginTop: 20,
    },

    messageLabel: {
      color: "#111111",
      fontSize: 14 * scale,
      fontWeight: "800",
      marginBottom: 8,
    },

    messageInput: {
      width: "100%",
      height: 88,
      borderRadius: 15,
      backgroundColor: "#FFFFFF",
      paddingHorizontal: 15,
      paddingVertical: 12,
      color: "#111111",
      fontSize: 14 * scale,
    },

    statsRow: {
      width: "100%",
      flexDirection: "row",
      justifyContent: "space-around",
      marginTop: 28,
    },

    stat: {
      alignItems: "center",
    },

    statTitle: {
      color: "#111111",
      fontSize: 13 * scale,
      fontWeight: "800",
      marginBottom: 12,
    },

    statCircle: {
      width: 82,
      height: 82,
      borderRadius: 41,
      backgroundColor: "#D9D9D9",
      alignItems: "center",
      justifyContent: "center",
    },

    statNumber: {
      color: "#555555",
      fontSize: 23 * scale,
      fontWeight: "900",
    },

    pressed: {
      opacity: 0.7,
      transform: [{ scale: 0.97 }],
    },

    notice: {
      marginTop: 18,
      textAlign: "center",
      color: "#8A3B12",
      fontWeight: "700",
    },

    saveButton: {
      minHeight: 48,
      borderRadius: 24,
      backgroundColor: "#159326",
      alignItems: "center",
      justifyContent: "center",
      marginTop: 18,
    },

    saveButtonDisabled: {
      opacity: 0.55,
    },

    saveButtonText: {
      color: "#FFFFFF",
      fontSize: 15 * scale,
      fontWeight: "800",
    },
  });

const fieldStyles = StyleSheet.create({
  fieldRow: {
    width: "100%",
    flexDirection: "row",
    alignItems: "center",
  },

  fieldLabel: {
    width: 92,
    color: "#111111",
    fontWeight: "800",
  },

  fieldInput: {
    flex: 1,
    height: 39,
    backgroundColor: "#FFFFFF",
    borderRadius: 999,
    paddingHorizontal: 15,
    color: "#111111",
  },
});
