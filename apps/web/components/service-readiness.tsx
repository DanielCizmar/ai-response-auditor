"use client";

import { Button, cn } from "@auditor/ui";
import { useQuery } from "@tanstack/react-query";
import { Check, CircleAlert, LoaderCircle, RotateCw } from "lucide-react";

import { fetchReadiness } from "@/lib/readiness";
import { useLocale } from "@/lib/locale";

const states = {
  checking: {
    title: "readiness.checking.title",
    detail: "readiness.checking.detail",
    className: "border-evidence-needed/35 bg-evidence-needed/5",
  },
  ready: {
    title: "readiness.ready.title",
    detail: "readiness.ready.detail",
    className: "border-supported/35 bg-supported/5",
  },
  setup: {
    title: "readiness.setup.title",
    detail: "readiness.setup.detail",
    className: "border-warning/40 bg-warning/6",
  },
  modelMissing: {
    title: "readiness.modelMissing.title",
    detail: "readiness.modelMissing.detail",
    className: "border-warning/40 bg-warning/6",
  },
  modelLoading: {
    title: "readiness.modelLoading.title",
    detail: "readiness.modelLoading.detail",
    className: "border-evidence-needed/35 bg-evidence-needed/5",
  },
  disconnected: {
    title: "readiness.disconnected.title",
    detail: "readiness.disconnected.detail",
    className: "border-high-risk/35 bg-high-risk/5",
  },
} as const;

export function ServiceReadiness() {
  const { t } = useLocale();
  const query = useQuery({ queryKey: ["readiness"], queryFn: fetchReadiness });
  const ollamaState = query.data?.dependencies.ollama?.state;
  const state = query.isPending
    ? "checking"
    : query.isError
      ? "disconnected"
      : query.data.status === "ready"
        ? "ready"
        : ollamaState === "instruction_model_missing" ||
            ollamaState === "embedding_model_missing"
          ? "modelMissing"
          : ollamaState === "model_loading"
            ? "modelLoading"
            : "setup";
  const copy = states[state];
  const Icon =
    state === "checking" || state === "modelLoading"
      ? LoaderCircle
      : state === "ready"
        ? Check
        : CircleAlert;

  return (
    <section
      aria-atomic="true"
      aria-live={state === "disconnected" ? "assertive" : "polite"}
      className={cn(
        "flex flex-col gap-4 border-b px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-8",
        copy.className,
      )}
      data-state={state}
    >
      <div className="flex min-w-0 items-start gap-3">
        <Icon
          aria-hidden="true"
          className={cn(
            "mt-0.5 size-4 shrink-0",
            (state === "checking" || state === "modelLoading") && "animate-spin",
          )}
        />
        <div>
          <p className="text-sm font-semibold text-ink">{t(copy.title)}</p>
          <p className="mt-0.5 text-sm leading-5 text-evidence-needed">{t(copy.detail)}</p>
        </div>
      </div>
      {(state === "disconnected" ||
        state === "setup" ||
        state === "modelMissing" ||
        state === "modelLoading") && (
        <div className="flex shrink-0 items-center gap-2 pl-7 sm:pl-0">
          {state === "disconnected" && (
            <code className="hidden font-mono text-[0.68rem] text-evidence-needed lg:block">
              pnpm api:dev
            </code>
          )}
          {state === "modelMissing" && (
            <code className="break-all font-mono text-[0.68rem] text-evidence-needed">
              {query.data?.dependencies.ollama?.action ?? "pnpm ollama:setup"}
            </code>
          )}
          <Button variant="outline" size="sm" onClick={() => query.refetch()}>
            <RotateCw aria-hidden="true" className="size-3.5" />
            {t("readiness.retry")}
          </Button>
        </div>
      )}
    </section>
  );
}
