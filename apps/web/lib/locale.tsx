"use client";

import {
  isLocale,
  translate,
  translatePlural,
  type Locale,
  type MessageKey,
  type MessageValues,
  type PluralMessageKey,
} from "@auditor/i18n";
import { createContext, useCallback, useContext, useEffect, useMemo, useSyncExternalStore, type ReactNode } from "react";

const STORAGE_KEY = "auditor.interface-locale";

type LocaleContextValue = {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (key: MessageKey, values?: MessageValues) => string;
  tp: (key: PluralMessageKey, count: number, values?: MessageValues) => string;
};

const LocaleContext = createContext<LocaleContextValue | null>(null);

export function LocaleProvider({ children }: Readonly<{ children: ReactNode }>) {
  const locale = useSyncExternalStore<Locale>(
    subscribeToLocale,
    readStoredLocale,
    () => "en",
  );

  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  const setLocale = useCallback((nextLocale: Locale) => {
    window.localStorage.setItem(STORAGE_KEY, nextLocale);
    document.documentElement.lang = nextLocale;
    window.dispatchEvent(new Event("auditor-locale-change"));
  }, []);

  const value = useMemo<LocaleContextValue>(
    () => ({
      locale,
      setLocale,
      t: (key, values) => translate(locale, key, values),
      tp: (key, count, values) => translatePlural(locale, key, count, values),
    }),
    [locale, setLocale],
  );

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

function readStoredLocale(): Locale {
  const stored = window.localStorage.getItem(STORAGE_KEY);
  return isLocale(stored) ? stored : "en";
}

function subscribeToLocale(onStoreChange: () => void): () => void {
  window.addEventListener("storage", onStoreChange);
  window.addEventListener("auditor-locale-change", onStoreChange);
  return () => {
    window.removeEventListener("storage", onStoreChange);
    window.removeEventListener("auditor-locale-change", onStoreChange);
  };
}

export function useLocale(): LocaleContextValue {
  const value = useContext(LocaleContext);
  if (value === null) {
    throw new Error("useLocale must be used inside LocaleProvider");
  }
  return value;
}

export { STORAGE_KEY as LOCALE_STORAGE_KEY };
