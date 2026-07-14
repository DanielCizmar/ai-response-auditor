"use client";

import { Button, cn } from "@auditor/ui";
import { PanelRight, ShieldCheck } from "lucide-react";
import { useMemo, useState } from "react";
import type { Locale } from "@auditor/i18n";

import { countUnicodeCharacters } from "@/lib/canonical-text";
import { useLocale } from "@/lib/locale";

import { LocaleSelector } from "./locale-selector";
import { ServiceReadiness } from "./service-readiness";
import { TextEditor } from "./text-editor";

export const MAX_AUDIT_CHARACTERS = 10_000;

export function WorkspaceShell({ initialText = "" }: Readonly<{ initialText?: string }>) {
  const { t, tp } = useLocale();
  const [textLanguage, setTextLanguage] = useState<Locale>("en");
  const [canonicalText, setCanonicalText] = useState(initialText);
  const characterCount = useMemo(
    () => countUnicodeCharacters(canonicalText),
    [canonicalText],
  );
  const isEmpty = canonicalText.trim().length === 0;
  const isOverLimit = characterCount > MAX_AUDIT_CHARACTERS;
  const validationMessage = isEmpty
    ? t("editor.empty")
    : isOverLimit
      ? tp("editor.overLimit", characterCount - MAX_AUDIT_CHARACTERS)
      : t("editor.valid");

  return (
    <div className="min-h-screen px-3 py-3 sm:px-5 sm:py-5 lg:px-8">
      <a
        href="#workspace"
        className="sr-only z-50 rounded bg-ink px-3 py-2 text-paper focus:not-sr-only focus:fixed focus:left-4 focus:top-4"
      >
        {t("nav.skip")}
      </a>
      <div className="mx-auto max-w-[92rem] overflow-hidden border border-line bg-paper shadow-[0_18px_60px_rgb(23_35_43_/_0.08)]">
        <header className="flex min-h-16 items-center justify-between border-b border-line px-5 sm:px-8">
          <div className="flex items-baseline gap-3">
            <span className="font-prose text-2xl font-semibold tracking-[-0.025em] text-ink">
              {t("app.name")}
            </span>
            <span className="hidden text-[0.68rem] font-semibold uppercase tracking-[0.19em] text-evidence-needed sm:inline">
              {t("app.tagline")}
            </span>
          </div>
          <nav aria-label={t("nav.primary")} className="flex items-center gap-1 sm:gap-3">
            <a
              href="#workspace"
              aria-current="page"
              className="hidden rounded px-2 py-2 text-sm font-semibold text-ink outline-none hover:bg-canvas focus-visible:ring-2 focus-visible:ring-mineral sm:inline"
            >
              {t("nav.workspace")}
            </a>
            <LocaleSelector />
          </nav>
        </header>

        <ServiceReadiness />

        <main id="workspace" className="relative" tabIndex={-1}>
          <div className="grid min-h-[42rem] lg:grid-cols-[minmax(0,1fr)_23rem]">
            <section aria-labelledby="draft-title" className="min-w-0 px-5 py-7 sm:px-8 sm:py-10 lg:px-12">
              <div className="mx-auto max-w-4xl">
                <div className="mb-8 flex flex-col gap-4 border-b border-faint-line pb-6 sm:flex-row sm:items-end sm:justify-between">
                  <div>
                    <p className="font-mono text-[0.66rem] font-medium uppercase tracking-[0.18em] text-mineral">
                      {t("workspace.eyebrow")}
                    </p>
                    <h1 id="draft-title" className="mt-2 max-w-2xl font-prose text-3xl font-semibold leading-tight tracking-[-0.025em] text-ink sm:text-4xl">
                      {t("workspace.title")}
                    </h1>
                    <p className="mt-3 max-w-2xl text-base leading-6 text-evidence-needed">
                      {t("workspace.intro")}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 font-mono text-[0.66rem] uppercase tracking-[0.12em] text-evidence-needed">
                    <ShieldCheck aria-hidden="true" className="size-4 text-supported" />
                    {t("workspace.local")}
                  </div>
                </div>

                <div className="relative min-h-[24rem] border border-line bg-white px-6 py-6 shadow-[inset_0_1px_0_rgb(255_255_255),0_10px_30px_rgb(23_35_43_/_0.04)] sm:px-10 sm:py-8">
                  <div className="absolute left-0 top-8 h-14 w-[3px] bg-mineral" aria-hidden="true" />
                  <TextEditor
                    language={textLanguage}
                    onLanguageChange={setTextLanguage}
                    onTextChange={setCanonicalText}
                    value={canonicalText}
                  />
                </div>
              </div>
            </section>

            <aside aria-labelledby="review-title" className="relative border-t border-line bg-canvas/55 px-5 py-7 sm:px-8 lg:border-l lg:border-t-0 lg:px-7 lg:py-10">
              <div className="absolute -left-px top-0 hidden h-full w-px bg-mineral/45 lg:block" aria-hidden="true" />
              <div className="absolute -left-[5px] top-16 hidden size-[9px] rounded-full border-2 border-paper bg-mineral lg:block" aria-hidden="true" />
              <div className="flex items-center justify-between border-b border-line pb-4">
                <div>
                  <p className="font-mono text-[0.64rem] uppercase tracking-[0.16em] text-mineral">{t("review.eyebrow")}</p>
                  <h2 id="review-title" className="mt-1 font-prose text-xl font-semibold text-ink">{t("review.title")}</h2>
                </div>
                <PanelRight aria-hidden="true" className="size-5 text-evidence-needed" />
              </div>
              <div className="flex min-h-56 flex-col justify-center py-9 lg:min-h-[27rem]">
                <p className="text-sm font-semibold text-ink">{t("review.empty.title")}</p>
                <p className="mt-2 text-sm leading-6 text-evidence-needed">
                  {t("review.empty.detail")}
                </p>
                <div className="mt-6 border-l-2 border-dashed border-evidence-needed/45 pl-4">
                  <p className="font-mono text-[0.64rem] uppercase tracking-[0.13em] text-evidence-needed">{t("review.thread.inactive")}</p>
                  <p className="mt-1 text-xs leading-5 text-evidence-needed">{t("review.thread.path")}</p>
                </div>
              </div>
            </aside>
          </div>

          <footer className="flex flex-col gap-3 border-t border-line bg-paper px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-8">
            <div>
              <p className="font-mono text-xs text-evidence-needed">
                {t("editor.count", { count: characterCount, limit: MAX_AUDIT_CHARACTERS })} · {t("audit.notStarted")}
              </p>
              <p
                id="editor-validation"
                role={isEmpty || isOverLimit ? "alert" : "status"}
                className={cn(
                  "mt-1 text-xs",
                  isEmpty || isOverLimit ? "text-high-risk" : "text-supported",
                )}
              >
                {validationMessage}
              </p>
            </div>
            <div className="flex flex-col items-start gap-1 sm:items-end">
              <Button disabled>{t("audit.action")}</Button>
              <span className="max-w-sm text-left text-xs text-evidence-needed sm:text-right">
                {t("audit.unavailable")}
              </span>
            </div>
          </footer>
        </main>
      </div>
    </div>
  );
}
