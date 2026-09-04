import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { useRouter } from "expo-router";
import { useAuth } from "../../auth/AuthContext";
import { deleteRequest } from "../../api/request-deletion";
import { updateRequest } from "../../api/request-update";
import { listPublicRequests, requestListErrorMessage, type PublicRequest } from "../../features/requests/client";
import { listApplicants, selectApplicant, selectionErrorMessage, type Applicant } from "../../features/applications/client";

export default function MyRequestsScreen() {
  const router = useRouter();
  const { profile } = useAuth();
  const [items, setItems] = useState<PublicRequest[]>([]);
  const [selected, setSelected] = useState<PublicRequest | null>(null);
  const [applicants, setApplicants] = useState<Applicant[]>([]);
  const [title, setTitle] = useState("");
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    setStatus("loading"); setMessage("");
    try {
      const page = await listPublicRequests();
      setItems(page.items.filter((item) => item.requesterId === profile?.id));
      setStatus("ready");
    } catch (error) { setMessage(requestListErrorMessage(error)); setStatus("error"); }
  }, [profile?.id]);

  useEffect(() => {
    if (!profile?.id) return;
    let active = true;
    void listPublicRequests().then((page) => {
      if (!active) return;
      setItems(page.items.filter((item) => item.requesterId === profile.id));
      setStatus("ready");
    }).catch((error: unknown) => {
      if (!active) return;
      setMessage(requestListErrorMessage(error));
      setStatus("error");
    });
    return () => { active = false; };
  }, [profile?.id]);

  const open = async (request: PublicRequest) => {
    setSelected(request); setTitle(request.title); setMessage("");
    const state = await listApplicants(request.id);
    if (state.status === "ready") setApplicants(state.items);
    else if (state.status === "empty") setApplicants([]);
    else setMessage("応募者一覧を取得できませんでした。");
  };

  const save = async () => {
    if (!selected || !title.trim()) return;
    const result = await updateRequest(selected.id, { title: title.trim(), expectedVersion: selected.version ?? 1 });
    if (result.status === "updated") { setSelected(result.request); setItems((all) => all.map((x) => x.id === result.request.id ? result.request : x)); setMessage("更新しました。"); }
    else if (result.status === "conflict") { setMessage("別の端末で更新されています。最新情報を確認してください。"); if (result.latestRequest) setSelected(result.latestRequest); }
    else setMessage("依頼を更新できませんでした。");
  };

  const cancel = async () => {
    if (!selected) return;
    const result = await deleteRequest(selected.id, items as never[]);
    if (result.status === "deleted") { setItems((all) => all.filter((x) => x.id !== selected.id)); setSelected(null); setMessage("依頼を取り消しました。"); }
    else setMessage("この依頼は現在取り消せません。");
  };

  const choose = async (applicant: Applicant) => {
    if (!selected) return;
    try {
      const match = await selectApplicant(applicant.id, selected.version ?? 1);
      router.push({ pathname: "/help/chat", params: { matchId: match.id } });
    } catch (error) { setMessage(selectionErrorMessage(error)); }
  };

  return <View style={styles.screen}><ScrollView contentContainerStyle={styles.container}>
    <Pressable onPress={() => router.back()}><Text style={styles.link}>戻る</Text></Pressable>
    <Text style={styles.heading}>自分の依頼</Text>
    {status === "loading" ? <ActivityIndicator color="#245C2D" /> : null}
    {status === "error" ? <Pressable onPress={() => void load()}><Text style={styles.link}>{message} 再試行</Text></Pressable> : null}
    {!selected && status === "ready" && items.length === 0 ? <Text>公開中の依頼はありません。</Text> : null}
    {!selected ? items.map((item) => <Pressable key={item.id} onPress={() => void open(item)} style={styles.card}>
      <Text style={styles.title}>{item.title}</Text><Text>{item.areaLabel}・{item.status}</Text>
    </Pressable>) : <View style={styles.card}>
      <Pressable onPress={() => setSelected(null)}><Text style={styles.link}>一覧へ</Text></Pressable>
      <TextInput accessibilityLabel="依頼タイトル" value={title} onChangeText={setTitle} style={styles.input} />
      <Text>{selected.description}</Text><Text>{selected.areaLabel}・version {selected.version ?? 1}</Text>
      <Pressable onPress={() => void save()} style={styles.primary}><Text style={styles.primaryText}>更新する</Text></Pressable>
      <Pressable onPress={() => void cancel()} style={styles.danger}><Text style={styles.primaryText}>依頼を取り消す</Text></Pressable>
      <Text style={styles.subheading}>応募者</Text>
      {applicants.length === 0 ? <Text>応募者はまだいません。</Text> : applicants.map((applicant) => <View key={applicant.id} style={styles.applicant}>
        <Text style={styles.title}>{applicant.helper.displayName}</Text>
        <Text>{applicant.message}</Text><Text>実績 {applicant.helper.achievementCount}件</Text>
        <Pressable onPress={() => void choose(applicant)} style={styles.primary}><Text style={styles.primaryText}>この人にお願いする</Text></Pressable>
      </View>)}
    </View>}
    {message && status !== "error" ? <Text style={styles.message}>{message}</Text> : null}
  </ScrollView></View>;
}

const styles = StyleSheet.create({
  screen: { flex: 1, alignItems: "center", backgroundColor: "#FFF5E9" },
  container: { width: "100%", maxWidth: 520, padding: 28, gap: 14 },
  heading: { fontSize: 28, fontWeight: "900", color: "#35410F" },
  subheading: { fontSize: 20, fontWeight: "800", marginTop: 18 },
  card: { padding: 18, borderRadius: 14, backgroundColor: "#FFFFFF", gap: 10 },
  applicant: { paddingTop: 14, borderTopWidth: 1, borderTopColor: "#DDDDDD", gap: 6 },
  title: { fontSize: 17, fontWeight: "700" },
  input: { borderWidth: 1, borderColor: "#C8CEBD", borderRadius: 10, padding: 12, fontSize: 16 },
  primary: { alignItems: "center", padding: 12, borderRadius: 10, backgroundColor: "#245C2D" },
  danger: { alignItems: "center", padding: 12, borderRadius: 10, backgroundColor: "#A23B32" },
  primaryText: { color: "#FFFFFF", fontWeight: "700" },
  link: { color: "#245C2D", fontWeight: "700", paddingVertical: 8 },
  message: { color: "#A23B32" },
});
