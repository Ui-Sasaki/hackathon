import TalkScreen from "../../shared/TalkScreen";
import { useLocalSearchParams } from "expo-router";

export default function HelpChat() {
  const { matchId } = useLocalSearchParams<{ matchId?: string }>();
  return <TalkScreen key={matchId} role="requester" matchId={matchId} />;
}
