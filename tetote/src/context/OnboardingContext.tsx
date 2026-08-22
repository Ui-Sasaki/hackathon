import {
  createContext,
  useContext,
  useState,
  ReactNode,
} from "react";

type HelperType = "student" | "worker" | null;

type OnboardingData = {
  role: "requester" | "helper" | null;

  name: string;
  region: string;
  age: string;
  notes: string;
  image: string | null;

  helperType: HelperType;

  university: string;
  faculty: string;
  schoolYear: string;

  occupation: string;
  industry: string;
  workplace: string;

  helpCategories: string[];

  character: number | null;
};

type OnboardingContextType = {
  data: OnboardingData;
  updateData: (values: Partial<OnboardingData>) => void;
  resetData: () => void;
};

const initialData: OnboardingData = {
  role: null,

  name: "",
  region: "",
  age: "",
  notes: "",
  image: null,

  helperType: null,

  university: "",
  faculty: "",
  schoolYear: "",

  occupation: "",
  industry: "",
  workplace: "",

  helpCategories: [],

  character: null,
};

const OnboardingContext =
  createContext<OnboardingContextType | null>(null);

export function OnboardingProvider({
  children,
}: {
  children: ReactNode;
}) {
  const [data, setData] =
    useState<OnboardingData>(initialData);

  const updateData = (
    values: Partial<OnboardingData>
  ) => {
    setData((current) => ({
      ...current,
      ...values,
    }));
  };

  const resetData = () => {
    setData(initialData);
  };

  return (
    <OnboardingContext.Provider
      value={{
        data,
        updateData,
        resetData,
      }}
    >
      {children}
    </OnboardingContext.Provider>
  );
}

export function useOnboarding() {
  const context = useContext(OnboardingContext);

  if (!context) {
    throw new Error(
      "useOnboarding must be used inside OnboardingProvider"
    );
  }

  return context;
}