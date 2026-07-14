"use client";

import { ApiClientError, type Audit } from "@auditor/api-client";
import type { Locale } from "@auditor/i18n";
import { Button, cn } from "@auditor/ui";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  CheckCircle2,
  CircleAlert,
  LoaderCircle,
  PanelRight,
  ShieldCheck,
} from "lucide-react";
import { useMemo, useRef, useState } from "react";

import { AuditRequestTimeout, runAudit } from "@/lib/audits";
import { countUnicodeCharacters } from "@/lib/canonical-text";
import { useLocale } from "@/lib/locale";
import { fetchReadiness } from "@/lib/readiness";

import { LocaleSelector } from "./locale-selector";
import { ServiceReadiness } from "./service-readiness";
import { TextEditor } from "./text-editor";

export const MAX_AUDIT_CHARACTERS = 10_000;

export function WorkspaceShell({ initialText = "" }: Readonly<{ initialText?: string }>) {
  const { t, tp } = useLocale();
  const [textLanguage, setTextLanguage] = useState<Locale>("en");
  const [canonicalText, setCanonicalText] = useState(initialText);
  const idempotencyKey = useRef<string | null>(null);
  const readiness = useQuery({ queryKey: ["readiness"], queryFn: fetchReadiness });
  const audit = useMutation({ mutationFn: runAudit });
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
  const servicesReady = readiness.data?.status === "ready";
  const savedPending = audit.data?.state === "queued" || audit.data?.state === "running";
  const retryable =
    audit.isError ||
    savedPending ||
    audit.data?.state === "failed" ||
    audit.data?.state === "partially_succeeded";
  const canAudit = !isEmpty && !isOverLimit && servicesReady && !audit.isPending;

  function submitAudit() {
    const reuseKey = audit.error instanceof AuditRequestTimeout || savedPending;
    if (!reuseKey || !idempotencyKey.current) {
      idempotencyKey.current = globalThis.crypto.randomUUID();
    }
    audit.mutate({
      text: canonicalText,
      language: textLanguage,
      idempotencyKey: idempotencyKey.current,
    });
  }

  const auditLabel = audit.isPending
    ? t("audit.pending.action")
    : savedPending
      ? t("audit.check")
      : retryable
        ? t("audit.retry")
        : t("audit.action");
  const auditStatus =
    audit.isPending || savedPending
      ? t("audit.pending.short")
      : audit.data?.state === "succeeded"
        ? t("audit.complete.short")
        : audit.data?.state === "partially_succeeded"
          ? t("audit.partial.short")
          : audit.data?.state === "failed" || audit.isError
            ? t("audit.failed.short")
            : t("audit.notStarted");

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
              <AuditState
                audit={audit.data}
                error={audit.error}
                pending={audit.isPending || savedPending}
              />
            </aside>
          </div>

          <footer className="flex flex-col gap-3 border-t border-line bg-paper px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-8">
            <div>
              <p className="font-mono text-xs text-evidence-needed">
                {t("editor.count", { count: characterCount, limit: MAX_AUDIT_CHARACTERS })} · {auditStatus}
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
              <Button disabled={!canAudit} onClick={submitAudit}>
                {audit.isPending && <LoaderCircle aria-hidden="true" className="size-4 animate-spin" />}
                {auditLabel}
              </Button>
              <span className="max-w-sm text-left text-xs text-evidence-needed sm:text-right">
                {!servicesReady
                  ? t("audit.servicesUnavailable")
                  : audit.isPending
                    ? t("audit.pending.detail")
                    : savedPending
                      ? t("audit.check.detail")
                      : retryable
                        ? t("audit.retry.detail")
                        : t("audit.available")}
              </span>
            </div>
          </footer>
        </main>
      </div>
    </div>
  );
}

function AuditState({
  audit,
  error,
  pending,
}: Readonly<{ audit?: Audit; error: Error | null; pending: boolean }>) {
  const { t } = useLocale();
  let title = t("review.empty.title");
  let detail = t("review.empty.detail");
  let Icon = PanelRight;
  let tone = "text-evidence-needed";

  if (pending) {
    title = t("audit.pending.title");
    detail = t("audit.pending.detail");
    Icon = LoaderCircle;
    tone = "text-mineral";
  } else if (audit?.state === "succeeded") {
    title = t("audit.complete.title");
    detail = t("audit.complete.detail", { count: audit.claims.length });
    Icon = CheckCircle2;
    tone = "text-supported";
  } else if (audit?.state === "partially_succeeded") {
    title = t("audit.partial.title");
    detail = t("audit.partial.detail", { count: audit.claims.length });
    Icon = CircleAlert;
    tone = "text-warning";
  } else if (audit?.state === "failed") {
    const timedOut = audit.safe_error_code === "MODEL_TIMEOUT";
    title = timedOut ? t("audit.timeout.title") : t("audit.failed.title");
    detail = timedOut ? t("audit.timeout.detail") : t("audit.failed.detail");
    Icon = CircleAlert;
    tone = "text-high-risk";
  } else if (error) {
    const missingModel = error instanceof ApiClientError && error.code === "MODEL_NOT_READY";
    const timedOut = error instanceof AuditRequestTimeout;
    title = missingModel
      ? t("audit.modelMissing.title")
      : timedOut
        ? t("audit.timeout.title")
        : t("audit.failed.title");
    detail = missingModel
      ? t("audit.modelMissing.detail")
      : timedOut
        ? t("audit.timeout.detail")
        : t("audit.failed.detail");
    Icon = CircleAlert;
    tone = "text-high-risk";
  }

  return (
    <div
      aria-live={error || audit?.state === "failed" ? "assertive" : "polite"}
      className="flex min-h-56 flex-col justify-center py-9 lg:min-h-[27rem]"
    >
      <Icon
        aria-hidden="true"
        className={cn("mb-4 size-5", tone, pending && "animate-spin")}
      />
      <p className="text-sm font-semibold text-ink">{title}</p>
      <p className="mt-2 text-sm leading-6 text-evidence-needed">{detail}</p>
      {audit && (
        <p className="mt-5 font-mono text-[0.64rem] uppercase tracking-[0.13em] text-evidence-needed">
          {t("audit.reference", { id: audit.id.slice(0, 8) })}
        </p>
      )}
      {!audit && !pending && !error && (
        <div className="mt-6 border-l-2 border-dashed border-evidence-needed/45 pl-4">
          <p className="font-mono text-[0.64rem] uppercase tracking-[0.13em] text-evidence-needed">
            {t("review.thread.inactive")}
          </p>
          <p className="mt-1 text-xs leading-5 text-evidence-needed">
            {t("review.thread.path")}
          </p>
        </div>
      )}
    </div>
  );
}
