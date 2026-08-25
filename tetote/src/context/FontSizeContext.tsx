import {
  createContext,
  ReactNode,
  useContext,
  useState,
} from "react";

export type FontSizeOption =
  | "small"
  | "medium"
  | "large";

type FontSizeContextType = {
  fontSize: FontSizeOption;
  setFontSize: (size: FontSizeOption) => void;
  scale: number;
};

const FontSizeContext =
  createContext<FontSizeContextType | null>(null);

export function FontSizeProvider({
  children,
}: {
  children: ReactNode;
}) {
  const [fontSize, setFontSize] =
    useState<FontSizeOption>("medium");

  const scale =
    fontSize === "small"
      ? 0.85
      : fontSize === "large"
      ? 1.2
      : 1;

  return (
    <FontSizeContext.Provider
      value={{
        fontSize,
        setFontSize,
        scale,
      }}
    >
      {children}
    </FontSizeContext.Provider>
  );
}

export function useFontSize() {
  const context = useContext(FontSizeContext);

  if (!context) {
    throw new Error(
      "useFontSize must be used inside FontSizeProvider"
    );
  }

  return context;
}