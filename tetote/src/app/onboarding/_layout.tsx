import { Slot } from "expo-router";
import { OnboardingProvider } from "../../context/OnboardingContext";

export default function OnboardingLayout() {
  return (
    <OnboardingProvider>
      <Slot />
    </OnboardingProvider>
  );
}