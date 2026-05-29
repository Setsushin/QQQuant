import { createContext, type ReactNode, useCallback, useContext, useState } from "react";

export type Lang = "en" | "zh";

const STORAGE_KEY = "qqquant.lang";

interface LangContextValue {
  lang: Lang;
  setLang: (l: Lang) => void;
}

// Default value is "en" so a component rendered without a provider (e.g. a bare
// unit test) still renders English — this is what keeps the per-view tests green.
const LangContext = createContext<LangContextValue>({ lang: "en", setLang: () => {} });

function initialLang(): Lang {
  try {
    return localStorage.getItem(STORAGE_KEY) === "zh" ? "zh" : "en";
  } catch {
    return "en";
  }
}

export function LangProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(initialLang);
  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    try {
      localStorage.setItem(STORAGE_KEY, l);
    } catch {
      // storage unavailable (private mode etc.) — keep the in-memory choice.
    }
  }, []);
  return <LangContext.Provider value={{ lang, setLang }}>{children}</LangContext.Provider>;
}

export function useLang(): LangContextValue {
  return useContext(LangContext);
}
