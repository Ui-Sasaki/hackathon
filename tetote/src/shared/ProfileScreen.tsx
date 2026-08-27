import { useEffect, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { usePathname, useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useAuth } from "../auth/AuthContext";
import { profileErrorKind, profileErrorMessage } from "../auth/profile-state";
import { useFontSize } from "../context/FontSizeContext";

export default function ProfileScreen() {
  const router = useRouter(); const pathname = usePathname(); const { scale } = useFontSize();
  const { profile, refreshProfile, updateProfile } = useAuth();
  const [displayName, setDisplayName] = useState(""); const [areaCode, setAreaCode] = useState("");
  const [loading, setLoading] = useState(true); const [saving, setSaving] = useState(false); const [notice, setNotice] = useState("");
  useEffect(() => { let active = true; refreshProfile().then((value) => { if (active) { setDisplayName(value.displayName); setAreaCode(value.areaCode ?? ""); } }).catch((error) => active && setNotice(profileErrorMessage(profileErrorKind(error)))).finally(() => active && setLoading(false)); return () => { active = false; }; }, [refreshProfile]);
  const save = async () => { if (saving) return; setSaving(true); setNotice(""); try { await updateProfile({ displayName: displayName.trim(), areaCode: areaCode.trim() }); setNotice("プロフィールを更新しました"); } catch (error) { setNotice(profileErrorMessage(profileErrorKind(error))); } finally { setSaving(false); } };
  if (loading) return <View style={styles.center}><ActivityIndicator /><Text>プロフィールを取得中です</Text></View>;
  const verificationLabel = profile?.verificationStatus === "approved" ? "本人確認済み" : profile?.verificationStatus === "pending" ? "本人確認の審査中" : "本人確認は未完了です";
  return <View style={styles.screen}><ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
    <Pressable onPress={() => router.push(pathname.startsWith("/help") ? "/help/settings" : "/helper/settings")} style={styles.settings}><Ionicons name="settings" size={34} color="#159326" /></Pressable>
    <View style={styles.avatar}><Ionicons name="person" size={48} color="#fff" /></View><Text style={styles.verification}>{verificationLabel}</Text>
    {!profile?.displayName && <Text style={styles.notice}>プロフィールが未設定です</Text>}
    <Field label="表示名" value={displayName} onChangeText={setDisplayName} scale={scale} /><Field label="概算地域" value={areaCode} onChangeText={setAreaCode} scale={scale} />
    <Text style={styles.unlinked}>性別・年代・大学名・興味・一言メッセージは現在API未連携です</Text>
    {!!notice && <Text accessibilityLiveRegion="polite" style={styles.notice}>{notice}</Text>}
    <Pressable disabled={saving} onPress={save} style={[styles.save, saving && styles.disabled]}>{saving ? <ActivityIndicator color="#fff" /> : <Text style={styles.saveText}>保存する</Text>}</Pressable>
  </ScrollView></View>;
}
function Field({ label, value, onChangeText, scale }: { label: string; value: string; onChangeText: (value: string) => void; scale: number }) { return <View style={styles.field}><Text style={[styles.label, { fontSize: 14 * scale }]}>{label}</Text><TextInput value={value} onChangeText={onChangeText} style={[styles.input, { fontSize: 14 * scale }]} /></View>; }
const styles = StyleSheet.create({ screen: { flex: 1, backgroundColor: "#FFF5E9" }, center: { flex: 1, alignItems: "center", justifyContent: "center", gap: 12, backgroundColor: "#FFF5E9" }, content: { width: "100%", maxWidth: 520, alignSelf: "center", padding: 28, paddingTop: 50, gap: 14 }, settings: { position: "absolute", right: 28, top: 32 }, avatar: { width: 112, height: 112, borderRadius: 56, backgroundColor: "#aaa", alignItems: "center", justifyContent: "center", alignSelf: "center" }, verification: { textAlign: "center", fontWeight: "800" }, field: { flexDirection: "row", alignItems: "center" }, label: { width: 92, fontWeight: "800" }, input: { flex: 1, height: 44, backgroundColor: "#fff", borderRadius: 22, paddingHorizontal: 16 }, unlinked: { color: "#666", lineHeight: 20 }, notice: { textAlign: "center", color: "#8A3B12", fontWeight: "700" }, save: { minHeight: 48, borderRadius: 24, backgroundColor: "#159326", alignItems: "center", justifyContent: "center", marginTop: 8 }, saveText: { color: "#fff", fontWeight: "800" }, disabled: { opacity: 0.55 } });
