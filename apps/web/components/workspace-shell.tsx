"use client";

import {
  ApiClientError,
  type Audit,
  type AuditClaim,
} from "@auditor/api-client";
import type { Locale, MessageKey } from "@auditor/i18n";
import { Button, cn } from "@auditor/ui";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  CircleAlert,
  LoaderCircle,
  PanelRight,
  ShieldCheck,
  X,
} from "lucide-react";
import { useMemo, useRef, useState, type ReactNode } from "react";

import { AuditRequestTimeout, runAudit } from "@/lib/audits";
import { countUnicodeCharacters } from "@/lib/canonical-text";
import { useLocale } from "@/lib/locale";
import { fetchReadiness } from "@/lib/readiness";
import { applyRevisionSafely, StaleRevisionError } from "@/lib/revisions";

import { LocaleSelector } from "./locale-selector";
import { ServiceReadiness } from "./service-readiness";
import { TextEditor } from "./text-editor";

export const MAX_AUDIT_CHARACTERS = 10_000;

type AuditRequest = Parameters<typeof runAudit>[0];

export function WorkspaceShell({ initialText = "" }: Readonly<{ initialText?: string }>) {
  const { t, tp } = useLocale();
  const [textLanguage, setTextLanguage] = useState<Locale>("en");
  const [canonicalText, setCanonicalText] = useState(initialText);
  const [selectedClaimIds, setSelectedClaimIds] = useState<string[]>([]);
  const [revisionNotice, setRevisionNotice] = useState<
    "applied" | "stale" | null
  >(null);
  const inspectorTitle = useRef<HTMLHeadingElement>(null);
  const idempotencyKey = useRef<string | null>(null);
  const lastRequest = useRef<AuditRequest | null>(null);
  const readiness = useQuery({ queryKey: ["readiness"], queryFn: fetchReadiness });
  const audit = useMutation({
    mutationFn: runAudit,
    onSuccess: () => {
      setSelectedClaimIds([]);
      setRevisionNotice(null);
    },
  });
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
  const reviewableAudit =
    audit.data?.state === "succeeded" ||
    audit.data?.state === "partially_succeeded"
      ? audit.data
      : undefined;
  const claims = reviewableAudit?.claims ?? [];
  const isStale = Boolean(reviewableAudit && canonicalText !== reviewableAudit.input_text);
  const selectedClaim =
    claims.find((claim) => claim.id === selectedClaimIds[0]) ?? null;

  function submitAudit() {
    const recovering = audit.error instanceof AuditRequestTimeout || savedPending;
    if (recovering && idempotencyKey.current && lastRequest.current) {
      audit.mutate(lastRequest.current);
      return;
    }
    idempotencyKey.current = globalThis.crypto.randomUUID();
    const request: AuditRequest = {
      text: canonicalText,
      language: textLanguage,
      idempotencyKey: idempotencyKey.current,
      ...(audit.data ? { sourceAuditId: audit.data.id } : {}),
    };
    lastRequest.current = request;
    audit.mutate(request);
  }

  function selectClaims(claimIds: string[]) {
    setSelectedClaimIds(claimIds);
    setRevisionNotice(null);
    window.requestAnimationFrame(() => inspectorTitle.current?.focus());
  }

  function closeInspector() {
    const selectedId = selectedClaimIds[0];
    setSelectedClaimIds([]);
    window.requestAnimationFrame(() => {
      document
        .querySelector<HTMLElement>(`[data-audit-claim-id="${selectedId}"]`)
        ?.focus();
    });
  }

  function selectAdjacentClaim(direction: -1 | 1) {
    if (claims.length === 0) return;
    const currentIndex = selectedClaim
      ? claims.findIndex((claim) => claim.id === selectedClaim.id)
      : direction > 0
        ? -1
        : 0;
    const nextIndex = (currentIndex + direction + claims.length) % claims.length;
    selectClaims([claims[nextIndex].id]);
  }

  function applySuggestion(claim: AuditClaim, replacementText: string) {
    if (!reviewableAudit) return;
    try {
      const nextText = applyRevisionSafely(
        reviewableAudit.input_text,
        canonicalText,
        claim,
        replacementText,
      );
      setCanonicalText(nextText);
      setRevisionNotice("applied");
    } catch (error) {
      if (error instanceof StaleRevisionError || error instanceof RangeError) {
        setRevisionNotice("stale");
        return;
      }
      throw error;
    }
  }

  const auditLabel = audit.isPending
    ? t("audit.pending.action")
    : savedPending
      ? t("audit.check")
      : retryable
        ? t("audit.retry")
        : audit.data
          ? t("audit.reaudit")
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

                {claims.length > 0 && (
                  <div className="mb-3 flex items-center justify-between gap-3">
                    <p className="font-mono text-[0.68rem] uppercase tracking-[0.12em] text-evidence-needed">
                      {t("claim.navigation.summary", { count: claims.length })}
                    </p>
                    <div className="flex gap-1" aria-label={t("claim.navigation.label")}>
                      <Button
                        aria-label={t("claim.navigation.previous")}
                        onClick={() => selectAdjacentClaim(-1)}
                        size="icon"
                        variant="quiet"
                      >
                        <ArrowLeft aria-hidden="true" className="size-4" />
                      </Button>
                      <Button
                        aria-label={t("claim.navigation.next")}
                        onClick={() => selectAdjacentClaim(1)}
                        size="icon"
                        variant="quiet"
                      >
                        <ArrowRight aria-hidden="true" className="size-4" />
                      </Button>
                    </div>
                  </div>
                )}

                <div className="relative min-h-[24rem] border border-line bg-white px-6 py-6 shadow-[inset_0_1px_0_rgb(255_255_255),0_10px_30px_rgb(23_35_43_/_0.04)] sm:px-10 sm:py-8">
                  <div className="absolute left-0 top-8 h-14 w-[3px] bg-mineral" aria-hidden="true" />
                  <TextEditor
                    activeClaimId={selectedClaim?.id ?? null}
                    auditId={reviewableAudit?.id ?? null}
                    claims={claims}
                    highlightsStale={isStale}
                    language={textLanguage}
                    onClaimSelect={selectClaims}
                    onLanguageChange={setTextLanguage}
                    onTextChange={setCanonicalText}
                    value={canonicalText}
                  />
                </div>
                {isStale && (
                  <p role="status" className="mt-3 border-l-2 border-warning pl-3 text-sm text-ink">
                    {t("claim.stale.editor")}
                  </p>
                )}
              </div>
            </section>

            <aside
              aria-labelledby="review-title"
              className={cn(
                "border-line bg-canvas px-5 py-7 sm:px-8 lg:relative lg:border-l lg:border-t-0 lg:bg-canvas/55 lg:px-7 lg:py-10 lg:shadow-none",
                selectedClaim
                  ? "fixed inset-x-3 bottom-3 z-30 max-h-[78vh] overflow-y-auto border shadow-[0_-18px_60px_rgb(23_35_43_/_0.22)] lg:static lg:max-h-none lg:overflow-visible lg:border-y-0 lg:border-r-0"
                  : "relative border-t",
              )}
            >
              <div className="absolute -left-px top-0 hidden h-full w-px bg-mineral/45 lg:block" aria-hidden="true" />
              <div className="absolute -left-[5px] top-16 hidden size-[9px] rounded-full border-2 border-paper bg-mineral lg:block" aria-hidden="true" />
              <div className="flex items-center justify-between border-b border-line pb-4">
                <div>
                  <p className="font-mono text-[0.64rem] uppercase tracking-[0.16em] text-mineral">{t("review.eyebrow")}</p>
                  <h2
                    id="review-title"
                    ref={inspectorTitle}
                    tabIndex={selectedClaim ? -1 : undefined}
                    className="mt-1 font-prose text-xl font-semibold text-ink outline-none focus-visible:ring-2 focus-visible:ring-mineral"
                  >
                    {t("review.title")}
                  </h2>
                </div>
                {selectedClaim ? (
                  <Button
                    aria-label={t("review.close")}
                    className="lg:hidden"
                    onClick={closeInspector}
                    size="icon"
                    variant="quiet"
                  >
                    <X aria-hidden="true" className="size-4" />
                  </Button>
                ) : (
                  <PanelRight aria-hidden="true" className="size-5 text-evidence-needed" />
                )}
              </div>
              {selectedClaim && reviewableAudit ? (
                <ClaimInspector
                  audit={reviewableAudit}
                  claim={selectedClaim}
                  overlappingClaims={claims.filter((claim) =>
                    selectedClaimIds.includes(claim.id),
                  )}
                  revisionNotice={revisionNotice}
                  stale={isStale}
                  onApply={applySuggestion}
                  onSelectClaim={(claim) => selectClaims([claim.id])}
                />
              ) : (
                <AuditState
                  audit={audit.data}
                  error={audit.error}
                  pending={audit.isPending || savedPending}
                />
              )}
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
                        : audit.data
                          ? t("audit.reaudit.detail")
                          : t("audit.available")}
              </span>
            </div>
          </footer>
        </main>
      </div>
    </div>
  );
}

function ClaimInspector({
  audit,
  claim,
  overlappingClaims,
  revisionNotice,
  stale,
  onApply,
  onSelectClaim,
}: Readonly<{
  audit: Audit;
  claim: AuditClaim;
  overlappingClaims: AuditClaim[];
  revisionNotice: "applied" | "stale" | null;
  stale: boolean;
  onApply: (claim: AuditClaim, replacementText: string) => void;
  onSelectClaim: (claim: AuditClaim) => void;
}>) {
  const { t } = useLocale();
  const suggestion = claim.suggested_revisions.find(
    (revision) => revision.validation_status === "valid",
  );

  return (
    <div className="py-5">
      <div className="border-l-2 border-mineral pl-4">
        <p className="font-mono text-[0.64rem] uppercase tracking-[0.13em] text-mineral">
          {t("claim.reference", {
            ordinal: claim.ordinal + 1,
            id: claim.id.slice(0, 8),
          })}
        </p>
        <blockquote className="mt-2 font-prose text-lg leading-7 text-ink">
          “{claim.exact_text}”
        </blockquote>
      </div>

      {overlappingClaims.length > 1 && (
        <fieldset className="mt-5 border border-line bg-paper p-3">
          <legend className="px-1 text-xs font-semibold text-ink">
            {t("claim.overlap.title", { count: overlappingClaims.length })}
          </legend>
          <div className="mt-1 grid gap-1">
            {overlappingClaims.map((overlap) => (
              <button
                aria-pressed={overlap.id === claim.id}
                className="rounded px-2 py-2 text-left text-xs text-ink outline-none hover:bg-canvas focus-visible:ring-2 focus-visible:ring-mineral"
                key={overlap.id}
                onClick={() => onSelectClaim(overlap)}
                type="button"
              >
                {overlap.exact_text}
              </button>
            ))}
          </div>
        </fieldset>
      )}

      {stale && (
        <div role="alert" className="mt-5 border-l-2 border-warning bg-paper px-3 py-2 text-sm text-ink">
          <p className="font-semibold">{t("claim.stale.title")}</p>
          <p className="mt-1 text-evidence-needed">{t("claim.stale.detail")}</p>
        </div>
      )}

      <dl className="mt-5 grid grid-cols-2 gap-x-4 gap-y-3 border-y border-line py-4">
        <InspectorDatum label={t("claim.status")} value={enumLabel(t, "status", claim.status)} />
        <InspectorDatum label={t("claim.type")} value={enumLabel(t, "type", claim.primary_type)} />
        <InspectorDatum
          label={t("claim.risk")}
          value={claim.risk_score === null ? t("claim.notAvailable") : `${claim.risk_score} / 100`}
          mono
        />
        <InspectorDatum
          label={t("claim.span")}
          value={`${claim.start_offset}–${claim.end_offset}`}
          mono
        />
      </dl>

      <InspectorSection title={t("claim.findings")}>
        {claim.findings.length > 0 ? (
          <ul className="grid gap-3">
            {claim.findings.map((finding) => (
              <li className="border-l-2 border-warning pl-3" key={finding.id}>
                <p className="text-sm font-semibold text-ink">
                  {enumLabel(t, "finding", finding.finding_type)}
                </p>
                <p className="mt-1 text-sm leading-5 text-evidence-needed">
                  {typeof finding.details.explanation === "string"
                    ? finding.details.explanation
                    : findingExplanation(t, finding.finding_type)}
                </p>
                <p className="mt-1 font-mono text-[0.62rem] uppercase tracking-[0.1em] text-evidence-needed">
                  {enumLabel(t, "source", finding.source_kind)} ·{" "}
                  {enumLabel(t, "severity", finding.severity)}
                </p>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-evidence-needed">{t("claim.findings.empty")}</p>
        )}
      </InspectorSection>

      <InspectorSection title={t("claim.scoreComponents")}>
        <ul className="grid gap-2">
          {claim.risk_components.map((component) => (
            <li className="flex items-start justify-between gap-3 text-sm" key={component.id}>
              <span className="text-evidence-needed">
                {enumLabel(t, "component", component.component_type)}
              </span>
              <span className="font-mono text-ink">+{component.points}</span>
            </li>
          ))}
        </ul>
      </InspectorSection>

      <InspectorSection title={t("claim.suggestion")}>
        {suggestion ? (
          <>
            <p className="border-l-2 border-supported bg-paper px-3 py-2 font-prose text-base leading-6 text-ink">
              {suggestion.replacement_text}
            </p>
            <p className="mt-2 text-sm leading-5 text-evidence-needed">
              {suggestion.rationale}
            </p>
            <Button
              className="mt-4"
              disabled={stale}
              onClick={() => onApply(claim, suggestion.replacement_text)}
            >
              {t("claim.suggestion.apply")}
            </Button>
          </>
        ) : (
          <p className="text-sm text-evidence-needed">{t("claim.suggestion.empty")}</p>
        )}
        {revisionNotice && (
          <p
            className={cn(
              "mt-3 text-sm",
              revisionNotice === "applied" ? "text-supported" : "text-high-risk",
            )}
            role={revisionNotice === "stale" ? "alert" : "status"}
          >
            {revisionNotice === "applied"
              ? t("claim.suggestion.applied")
              : t("claim.suggestion.stale")}
          </p>
        )}
      </InspectorSection>

      <p className="mt-6 font-mono text-[0.62rem] uppercase tracking-[0.11em] text-evidence-needed">
        {t("audit.reference", { id: audit.id.slice(0, 8) })}
      </p>
    </div>
  );
}

function InspectorSection({
  children,
  title,
}: Readonly<{ children: ReactNode; title: string }>) {
  return (
    <section className="mt-6">
      <h3 className="mb-3 text-xs font-semibold uppercase tracking-[0.1em] text-ink">
        {title}
      </h3>
      {children}
    </section>
  );
}

function InspectorDatum({
  label,
  mono = false,
  value,
}: Readonly<{ label: string; mono?: boolean; value: string }>) {
  return (
    <div>
      <dt className="text-xs text-evidence-needed">{label}</dt>
      <dd className={cn("mt-1 text-sm font-semibold text-ink", mono && "font-mono")}>
        {value}
      </dd>
    </div>
  );
}

function enumLabel(
  t: (key: MessageKey, values?: Record<string, string | number>) => string,
  group: "status" | "type" | "finding" | "source" | "severity" | "component",
  value: string | null,
): string {
  if (!value) return t("claim.notAvailable");
  const keys = enumMessageKeys[group];
  const key = keys[value];
  return key ? t(key) : value.replaceAll("_", " ");
}

const enumMessageKeys: Record<
  "status" | "type" | "finding" | "source" | "severity" | "component",
  Record<string, MessageKey>
> = {
  status: {
    low_risk: "claim.status.lowRisk",
    review_recommended: "claim.status.reviewRecommended",
    evidence_needed: "claim.status.evidenceNeeded",
    internally_inconsistent: "claim.status.internallyInconsistent",
    overstated: "claim.status.overstated",
    not_verifiable: "claim.status.notVerifiable",
  },
  type: {
    factual: "claim.type.factual",
    causal: "claim.type.causal",
    numerical: "claim.type.numerical",
    comparative: "claim.type.comparative",
    definitional: "claim.type.definitional",
    recommendation: "claim.type.recommendation",
    other: "claim.type.other",
  },
  finding: {
    numerical_inconsistency: "claim.finding.numericalInconsistency",
    causal_overstatement: "claim.finding.causalOverstatement",
    certainty_overstatement: "claim.finding.certaintyOverstatement",
    comparative_ambiguity: "claim.finding.comparativeAmbiguity",
    scope_ambiguity: "claim.finding.scopeAmbiguity",
  },
  source: {
    deterministic: "claim.source.deterministic",
    model_assisted: "claim.source.modelAssisted",
  },
  severity: {
    info: "claim.severity.info",
    low: "claim.severity.low",
    moderate: "claim.severity.moderate",
    high: "claim.severity.high",
    critical: "claim.severity.critical",
  },
  component: {
    evidence_need_verifiability: "claim.component.evidenceNeed",
    causal_absolute_overstatement: "claim.component.overstatement",
    internal_numerical_inconsistency: "claim.component.numerical",
    scope_ambiguity: "claim.component.scope",
    model_uncertainty: "claim.component.uncertainty",
    interacting_findings: "claim.component.interactions",
  },
};

function findingExplanation(
  t: (key: MessageKey) => string,
  findingType: string,
): string {
  const key = findingExplanationKeys[findingType];
  return t(key ?? "claim.finding.default");
}

const findingExplanationKeys: Record<string, MessageKey> = {
  numerical_inconsistency: "claim.finding.explanation.numericalInconsistency",
  causal_overstatement: "claim.finding.explanation.causalOverstatement",
  certainty_overstatement: "claim.finding.explanation.certaintyOverstatement",
  comparative_ambiguity: "claim.finding.explanation.comparativeAmbiguity",
  scope_ambiguity: "claim.finding.explanation.scopeAmbiguity",
};

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
