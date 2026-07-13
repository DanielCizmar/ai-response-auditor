"use client";

import { Button, cn } from "@auditor/ui";
import { useQuery } from "@tanstack/react-query";
import { Check, CircleAlert, LoaderCircle, RotateCw } from "lucide-react";

import { fetchReadiness } from "@/lib/readiness";

const states = {
  checking: {
    title: "Checking local services",
    detail: "Looking for the API and configured local models.",
    className: "border-evidence-needed/35 bg-evidence-needed/5",
  },
  ready: {
    title: "Local services ready",
    detail: "The private local workspace can accept an audit.",
    className: "border-supported/35 bg-supported/5",
  },
  setup: {
    title: "Local setup needs attention",
    detail: "The API is connected, but one or more required services are not ready.",
    className: "border-warning/40 bg-warning/6",
  },
  disconnected: {
    title: "Local API is disconnected",
    detail: "Start the local API, then retry the connection. Your text stays in this browser.",
    className: "border-high-risk/35 bg-high-risk/5",
  },
} as const;

export function ServiceReadiness() {
  const query = useQuery({ queryKey: ["readiness"], queryFn: fetchReadiness });
  const state = query.isPending
    ? "checking"
    : query.isError
      ? "disconnected"
      : query.data.status === "ready"
        ? "ready"
        : "setup";
  const copy = states[state];
  const Icon =
    state === "checking" ? LoaderCircle : state === "ready" ? Check : CircleAlert;

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
          className={cn("mt-0.5 size-4 shrink-0", state === "checking" && "animate-spin")}
        />
        <div>
          <p className="text-sm font-semibold text-ink">{copy.title}</p>
          <p className="mt-0.5 text-sm leading-5 text-evidence-needed">{copy.detail}</p>
        </div>
      </div>
      {(state === "disconnected" || state === "setup") && (
        <div className="flex shrink-0 items-center gap-2 pl-7 sm:pl-0">
          {state === "disconnected" && (
            <code className="hidden font-mono text-[0.68rem] text-evidence-needed lg:block">
              pnpm api:dev
            </code>
          )}
          <Button variant="outline" size="sm" onClick={() => query.refetch()}>
            <RotateCw aria-hidden="true" className="size-3.5" />
            Retry connection
          </Button>
        </div>
      )}
    </section>
  );
}
