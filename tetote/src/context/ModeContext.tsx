import {
  createContext,
  ReactNode,
  useContext,
  useState,
} from "react";

type AppMode = "helper" | "requester";

type ModeContextType = {
  mode: AppMode;
  setMode: (mode: AppMode) => void;
  toggleMode: () => void;
};

const ModeContext =
  createContext<ModeContextType | null>(null);

export function ModeProvider({
  children,
}: {
  children: ReactNode;
}) {
  const [mode, setMode] =
    useState<AppMode>("helper");

  const toggleMode = () => {
    setMode((current) =>
      current === "helper"
        ? "requester"
        : "helper"
    );
  };

  return (
    <ModeContext.Provider
      value={{
        mode,
        setMode,
        toggleMode,
      }}
    >
      {children}
    </ModeContext.Provider>
  );
}

export function useMode() {
  const context = useContext(ModeContext);

  if (!context) {
    throw new Error(
      "useMode must be used inside ModeProvider"
    );
  }

  return context;
}