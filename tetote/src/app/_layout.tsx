import { Stack } from "expo-router";
import { RequestsProvider } from "../context/RequestsContext";
import { ModeProvider } from "../context/ModeContext";

export default function RootLayout() {
  return (
    <ModeProvider>
      <RequestsProvider>
        <Stack
          screenOptions={{
            headerShown: false,
          }}
        />
      </RequestsProvider>
    </ModeProvider>
  );
}