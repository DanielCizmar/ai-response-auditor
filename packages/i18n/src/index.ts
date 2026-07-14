import en from "./en.json";
import sk from "./sk.json";

export const supportedLocales = ["en", "sk"] as const;
export type Locale = (typeof supportedLocales)[number];
export type MessageKey = keyof typeof en;
export type MessageValues = Record<string, string | number>;
export type PluralMessageKey = "editor.overLimit";

type Catalog = Record<MessageKey, string>;

export const catalogs: Record<Locale, Catalog> = { en, sk };

export function isLocale(value: unknown): value is Locale {
  return typeof value === "string" && supportedLocales.includes(value as Locale);
}

export function translate(
  locale: Locale,
  key: MessageKey,
  values: MessageValues = {},
): string {
  return Object.entries(values).reduce(
    (message, [name, value]) => message.replaceAll(`{${name}}`, String(value)),
    catalogs[locale][key],
  );
}

export function translatePlural(
  locale: Locale,
  key: PluralMessageKey,
  count: number,
  values: MessageValues = {},
): string {
  const category = new Intl.PluralRules(locale).select(count);
  const candidate = `${key}.${category}` as MessageKey;
  const fallback = `${key}.other` as MessageKey;
  return translate(locale, candidate in catalogs[locale] ? candidate : fallback, {
    ...values,
    count,
  });
}
