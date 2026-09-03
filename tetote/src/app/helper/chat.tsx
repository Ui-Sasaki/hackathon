import TalkScreen from "../../shared/TalkScreen";
import { useLocalSearchParams } from "expo-router";

export default function HelperChat() {
  const { matchId } = useLocalSearchParams<{ matchId?: string }>();
  return <TalkScreen key={matchId} role="helper" matchId={matchId} />;
}
