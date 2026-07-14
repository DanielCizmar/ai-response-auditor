"use client";

import type { Locale } from "@auditor/i18n";
import { Languages } from "lucide-react";

import { useLocale } from "@/lib/locale";

export function LocaleSelector() {
  const { locale, setLocale, t } = useLocale();

  return (
    <label className="flex items-center gap-2 border-l border-line pl-3 text-sm text-evidence-needed">
      <Languages aria-hidden="true" className="size-4" />
      <span className="sr-only">{t("locale.label")}</span>
      <select
        aria-label={t("locale.label")}
        className="cursor-pointer bg-transparent py-2 font-mono text-[0.68rem] font-medium uppercase tracking-[0.12em] text-ink outline-none focus-visible:ring-2 focus-visible:ring-mineral"
        onChange={(event) => setLocale(event.target.value as Locale)}
        value={locale}
      >
        <option value="en">EN</option>
        <option value="sk">SK</option>
      </select>
    </label>
  );
}
