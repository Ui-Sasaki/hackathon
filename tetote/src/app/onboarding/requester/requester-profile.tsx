import { useEffect, useState } from "react";
import {
  View,
  Text,
  TextInput,
  StyleSheet,
  Pressable,
  useWindowDimensions,
  ScrollView,
  Image,
  Modal,
} from "react-native";
import { useRouter } from "expo-router";
import * as ImagePicker from "expo-image-picker";
import { useAuth } from "../../../auth/AuthContext";
import { profileErrorKind, profileErrorMessage } from "../../../auth/profile-state";

const prefectures = [
  "北海道",
  "青森県",
  "岩手県",
  "宮城県",
  "秋田県",
  "山形県",
  "福島県",
  "茨城県",
  "栃木県",
  "群馬県",
  "埼玉県",
  "千葉県",
  "東京都",
  "神奈川県",
  "新潟県",
  "富山県",
  "石川県",
  "福井県",
  "山梨県",
  "長野県",
  "岐阜県",
  "静岡県",
  "愛知県",
  "三重県",
  "滋賀県",
  "京都府",
  "大阪府",
  "兵庫県",
  "奈良県",
  "和歌山県",
  "鳥取県",
  "島根県",
  "岡山県",
  "広島県",
  "山口県",
  "徳島県",
  "香川県",
  "愛媛県",
  "高知県",
  "福岡県",
  "佐賀県",
  "長崎県",
  "熊本県",
  "大分県",
  "宮崎県",
  "鹿児島県",
  "沖縄県",
];

const ages = Array.from({ length: 91 }, (_, index) => index + 18);

export default function RequesterProfileScreen() {
  const router = useRouter();
  const { width } = useWindowDimensions();
  const isDesktop = width >= 768;
  const { refreshProfile, updateProfile } = useAuth();

  const [name, setName] = useState("");
  const [region, setRegion] = useState("");
  const [age, setAge] = useState("");
  const [notes, setNotes] = useState("");
  const [image, setImage] = useState<string | null>(null);

  const [regionOpen, setRegionOpen] = useState(false);
  const [ageOpen, setAgeOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState("");

  useEffect(() => {
    let active = true;
    refreshProfile()
      .then((profile) => {
        if (!active) return;
        setName(profile.displayName);
        setRegion(profile.region ?? "");
        setAge(profile.age?.toString() ?? "");
        setNotes(profile.notes ?? "");
      })
      .catch((error) => {
        if (active) setNotice(profileErrorMessage(profileErrorKind(error)));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, [refreshProfile]);

  const pickImage = async () => {
    const permission =
      await ImagePicker.requestMediaLibraryPermissionsAsync();

    if (!permission.granted) {
      return;
    }

    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      allowsEditing: false,
      quality: 0.8,
    });

    if (!result.canceled && result.assets.length > 0) {
      setImage(result.assets[0].uri);
    }
  };

  const isFormComplete =
    name.trim() !== "" &&
    region !== "" &&
    age !== "" &&
    image !== null;

  const handleBack = () => {
    router.replace("/onboarding/role");
  };

  const handleNext = async () => {
    if (!isFormComplete || saving) return;
    setSaving(true);
    setNotice("");
    try {
      await updateProfile({
        displayName: name.trim(),
        region,
        age,
        notes: notes.trim(),
      });
      router.push("/onboarding/requester/preferences");
    } catch (error) {
      setNotice(profileErrorMessage(profileErrorKind(error)));
    } finally {
      setSaving(false);
    }
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
        keyboardShouldPersistTaps="handled"
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
            <View
              style={[
                styles.progressDot,
                styles.progressActive,
              ]}
            />
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

          <Text style={styles.roleTitle}>
            手伝ってほしい
          </Text>
          {!!notice && <Text accessibilityLiveRegion="polite">{notice}</Text>}

          <View style={styles.form}>
            <View style={styles.iconRow}>
              <Text style={styles.label}>顔写真</Text>

              <Pressable
                onPress={pickImage}
                style={({ pressed }) => [
                  styles.profileIcon,
                  pressed && styles.pressed,
                ]}
              >
                {image ? (
                  <Image
                    source={{ uri: image }}
                    style={styles.profileImage}
                  />
                ) : (
                  <Text style={styles.plus}>＋</Text>
                )}
              </Pressable>
            </View>

            <View style={styles.inputRow}>
              <Text style={styles.label}>名前</Text>

              <TextInput
                value={name}
                onChangeText={setName}
                style={styles.input}
                placeholder="名前を入力"
                placeholderTextColor="#B8B8B8"
              />
            </View>

            <View style={styles.inputRow}>
              <Text style={styles.label}>地域</Text>

              <Pressable
                style={styles.customSelect}
                onPress={() => setRegionOpen(true)}
              >
                <Text
                  style={[
                    styles.selectText,
                    !region && styles.placeholderText,
                  ]}
                >
                  {region || "都道府県を選択"}
                </Text>

                <Text style={styles.arrow}>▼</Text>
              </Pressable>
            </View>

            <View style={styles.inputRow}>
              <Text style={styles.label}>年齢</Text>

              <Pressable
                style={styles.customSelect}
                onPress={() => setAgeOpen(true)}
              >
                <Text
                  style={[
                    styles.selectText,
                    !age && styles.placeholderText,
                  ]}
                >
                  {age ? `${age}歳` : "年齢を選択"}
                </Text>

                <Text style={styles.arrow}>▼</Text>
              </Pressable>
            </View>

            <View style={styles.notesSection}>
              <Text style={styles.notesLabel}>
                注意点（任意）
              </Text>

              <TextInput
                value={notes}
                onChangeText={setNotes}
                style={styles.notesInput}
                multiline
                textAlignVertical="top"
                placeholder="サポートする人に知っておいてほしいこと"
                placeholderTextColor="#999999"
              />
            </View>
          </View>

          <Pressable
            disabled={!isFormComplete || saving || loading}
            onPress={handleNext}
            style={({ pressed }) => [
              styles.button,
              !isFormComplete && styles.buttonDisabled,
              pressed &&
                isFormComplete &&
                styles.buttonPressed,
            ]}
          >
            <Text
              style={[
                styles.buttonText,
                !isFormComplete &&
                  styles.buttonTextDisabled,
              ]}
            >
              {saving ? "更新中..." : "次に進む"}
            </Text>
          </Pressable>
        </View>
      </ScrollView>

      <Modal
        visible={regionOpen}
        transparent
        animationType="fade"
        onRequestClose={() => setRegionOpen(false)}
      >
        <Pressable
          style={styles.modalOverlay}
          onPress={() => setRegionOpen(false)}
        >
          <Pressable
            style={styles.modalBox}
            onPress={() => {}}
          >
            <Text style={styles.modalTitle}>
              都道府県を選択
            </Text>

            <ScrollView
              showsVerticalScrollIndicator={false}
            >
              {prefectures.map((prefecture) => (
                <Pressable
                  key={prefecture}
                  style={styles.option}
                  onPress={() => {
                    setRegion(prefecture);
                    setRegionOpen(false);
                  }}
                >
                  <Text style={styles.optionText}>
                    {prefecture}
                  </Text>
                </Pressable>
              ))}
            </ScrollView>
          </Pressable>
        </Pressable>
      </Modal>

      <Modal
        visible={ageOpen}
        transparent
        animationType="fade"
        onRequestClose={() => setAgeOpen(false)}
      >
        <Pressable
          style={styles.modalOverlay}
          onPress={() => setAgeOpen(false)}
        >
          <Pressable
            style={styles.modalBox}
            onPress={() => {}}
          >
            <Text style={styles.modalTitle}>
              年齢を選択
            </Text>

            <ScrollView
              showsVerticalScrollIndicator={false}
            >
              {ages.map((item) => (
                <Pressable
                  key={item}
                  style={styles.option}
                  onPress={() => {
                    setAge(String(item));
                    setAgeOpen(false);
                  }}
                >
                  <Text style={styles.optionText}>
                    {item}歳
                  </Text>
                </Pressable>
              ))}
            </ScrollView>
          </Pressable>
        </Pressable>
      </Modal>
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
    paddingBottom: 50,
  },

  container: {
    width: "100%",
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
    marginBottom: 22,
  },

  form: {
    width: "100%",
  },

  iconRow: {
    minHeight: 100,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 12,
  },

  profileIcon: {
    width: 82,
    height: 82,
    borderRadius: 0,
    backgroundColor: "#D5D5D5",
    overflow: "hidden",
    alignItems: "center",
    justifyContent: "center",
  },

  profileImage: {
    width: 82,
    height: 82,
    resizeMode: "contain",
  },

  plus: {
    color: "#FFFFFF",
    fontSize: 30,
  },

  pressed: {
    opacity: 0.75,
  },

  inputRow: {
    width: "100%",
    flexDirection: "row",
    alignItems: "center",
    marginTop: 18,
    paddingHorizontal: 12,
  },

  label: {
    width: 70,
    color: "#245C2D",
    fontSize: 16,
    fontWeight: "700",
  },

  input: {
    flex: 1,
    height: 46,
    borderRadius: 23,
    backgroundColor: "#FFFFFF",
    paddingHorizontal: 16,
    fontSize: 15,
  },

  customSelect: {
    flex: 1,
    height: 46,
    borderRadius: 23,
    backgroundColor: "#FFFFFF",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingLeft: 16,
    paddingRight: 16,
  },

  selectText: {
    color: "#111111",
    fontSize: 15,
  },

  placeholderText: {
    color: "#B8B8B8",
  },

  arrow: {
    color: "#CFCFCF",
    fontSize: 12,
  },

  notesSection: {
    width: "100%",
    marginTop: 24,
  },

  notesLabel: {
    color: "#111111",
    fontSize: 16,
    fontWeight: "700",
    marginBottom: 8,
  },

  notesInput: {
    width: "100%",
    minHeight: 150,
    borderRadius: 18,
    backgroundColor: "#D5D5D5",
    padding: 16,
    fontSize: 15,
  },

  button: {
    width: "65%",
    maxWidth: 280,
    minWidth: 200,
    backgroundColor: "#245C2D",
    borderRadius: 999,
    paddingVertical: 15,
    alignItems: "center",
    marginTop: 28,
    marginBottom: 20,
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

  modalOverlay: {
    flex: 1,
    backgroundColor: "rgba(0, 0, 0, 0.25)",
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: 24,
  },

  modalBox: {
    width: "100%",
    maxWidth: 380,
    maxHeight: 500,
    backgroundColor: "#FFF5E9",
    borderRadius: 24,
    padding: 20,
  },

  modalTitle: {
    color: "#245C2D",
    fontSize: 20,
    fontWeight: "700",
    textAlign: "center",
    marginBottom: 15,
  },

  option: {
    paddingVertical: 13,
    paddingHorizontal: 15,
    borderBottomWidth: 1,
    borderBottomColor: "#E8DED1",
  },

  optionText: {
    color: "#222222",
    fontSize: 16,
  },
});
