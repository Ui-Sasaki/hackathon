import { Stack } from "expo-router";

export default function RequesterLayout() {
  return (
    <Stack
      screenOptions={{
        headerShown: false,
        animation: "slide_from_right",
        animationDuration: 250,
      }}
    />
  );
}