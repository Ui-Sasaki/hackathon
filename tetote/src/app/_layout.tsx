import { Stack } from "expo-router";
import { RequestsProvider } from "../context/RequestsContext";
import { ModeProvider } from "../context/ModeContext";
import { FontSizeProvider } from "../context/FontSizeContext";

export default function RootLayout() {
  return (
    <ModeProvider>
      <FontSizeProvider>
        <RequestsProvider>
          <Stack
            screenOptions={{
              headerShown: false,
            }}
          />
        </RequestsProvider>
      </FontSizeProvider>
    </ModeProvider>
  );
}