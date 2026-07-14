import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { WorkspaceShell } from "@/components/workspace-shell";
import { LocaleProvider, LOCALE_STORAGE_KEY } from "@/lib/locale";

function renderShell(initialText = "") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <LocaleProvider>
      <QueryClientProvider client={queryClient}>
        <WorkspaceShell initialText={initialText} />
      </QueryClientProvider>
    </LocaleProvider>,
  );
}

function auditResponse(
  state: "succeeded" | "partially_succeeded" | "failed",
  safeErrorCode: string | null = null,
) {
  const now = "2026-07-14T12:00:00Z";
  return {
    id: "01980abc-0000-7000-8000-000000000001",
    re_audit_of_id: null,
    source_type: "pasted_text",
    language: "en",
    input_text: "A careful claim.",
    state,
    pipeline_version: "mvp1-audit-pipeline-v1",
    model_manifest: {},
    scoring_version: "mvp1-risk-v1",
    normalization_version: "unicode-code-points-v1",
    started_at: now,
    completed_at: now,
    safe_error_code: safeErrorCode,
    created_at: now,
    claims: state === "failed" ? [] : [{ id: "claim-1" }],
    events: [],
  };
}

function connectedFetch(audit: ReturnType<typeof auditResponse> | Promise<never>) {
  return vi.fn((input: string | URL | Request, _init?: RequestInit) => {
    void _init;
    if (String(input).endsWith("/v1/readiness")) {
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () => ({
          status: "ready",
          dependencies: { ollama: { state: "ready", ready: true, required: true } },
        }),
      });
    }
    if (audit instanceof Promise) return audit;
    return Promise.resolve({
      ok: true,
      status: 201,
      json: async () => audit,
    });
  });
}

beforeEach(() => {
  window.localStorage.clear();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("WorkspaceShell", () => {
  it("renders the document-first bilingual editor and bounded audit action", async () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => undefined)));

    renderShell("A careful claim with Slovak text: dôkaz.");

    expect(screen.getByRole("heading", { name: /review the claim/i })).toBeInTheDocument();
    expect(screen.getByRole("complementary", { name: /claim review/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Audit text" })).toBeDisabled();
    expect(screen.getByText("Checking local services")).toBeInTheDocument();

    expect(await screen.findByRole("textbox", { name: "Text to audit" })).toBeInTheDocument();
    expect(screen.getByLabelText("Text language")).toHaveValue("en");
    expect(screen.getByText("40 / 10000 characters · No audit started")).toBeInTheDocument();
    expect(screen.getByText("Text is ready for audit.")).toBeInTheDocument();
  });

  it("blocks an empty draft", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => undefined)));

    renderShell();

    expect(screen.getByText("Add text before starting an audit.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Audit text" })).toBeDisabled();
  });

  it("blocks text over the configured Unicode character limit", async () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => undefined)));

    renderShell("x".repeat(10_001));

    expect(await screen.findByText("10001 / 10000 characters · No audit started")).toBeInTheDocument();
    expect(screen.getByText("Shorten the text by 1 character to continue.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Audit text" })).toBeDisabled();
  });

  it("switches navigation and system copy to Slovak and stores the preference", async () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => undefined)));
    const user = userEvent.setup();

    renderShell();
    await user.selectOptions(screen.getByLabelText("Interface language"), "sk");

    expect(screen.getByRole("heading", { name: /skontrolujte tvrdenie/i })).toBeInTheDocument();
    expect(screen.getByText("Kontrolujú sa lokálne služby")).toBeInTheDocument();
    expect(window.localStorage.getItem(LOCALE_STORAGE_KEY)).toBe("sk");
    expect(document.documentElement.lang).toBe("sk");
  });

  it("renders a concrete, retryable disconnected state", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new TypeError("offline"));
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderShell();

    expect(await screen.findByText("Local API is disconnected")).toBeInTheDocument();
    const retry = screen.getByRole("button", { name: /retry connection/i });
    await user.click(retry);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("announces a ready local workspace", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ status: "ready", dependencies: {} }),
      }),
    );

    renderShell();

    expect(await screen.findByText("Local services ready")).toBeInTheDocument();
  });

  it("submits a bounded audit and reports a completed local result", async () => {
    const fetchMock = connectedFetch(auditResponse("succeeded"));
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    renderShell("A careful claim.");

    await screen.findByText("Local services ready");
    await user.click(screen.getByRole("button", { name: "Audit text" }));

    expect(await screen.findByText("Audit complete", { selector: "p" })).toBeInTheDocument();
    expect(screen.getByText(/immutable audit contains 1 claims/i)).toBeInTheDocument();
    const request = fetchMock.mock.calls.find(([input]) =>
      String(input).endsWith("/v1/audits"),
    );
    expect(request?.[1]).toMatchObject({ method: "POST" });
    expect((request?.[1] as RequestInit).headers).toMatchObject({
      "Idempotency-Key": expect.any(String),
    });
  });

  it("keeps the action pending while the local model is working", async () => {
    vi.stubGlobal("fetch", connectedFetch(new Promise(() => undefined)));
    const user = userEvent.setup();
    renderShell("A careful claim.");

    await screen.findByText("Local services ready");
    await user.click(screen.getByRole("button", { name: "Audit text" }));

    expect(screen.getByRole("button", { name: "Auditing text" })).toBeDisabled();
    expect(screen.getByText("Reviewing the text locally")).toBeInTheDocument();
  });

  it("preserves usable partial results and offers a retry", async () => {
    vi.stubGlobal(
      "fetch",
      connectedFetch(auditResponse("partially_succeeded", "PARTIAL_MODEL_TIMEOUT")),
    );
    const user = userEvent.setup();
    renderShell("A careful claim.");

    await screen.findByText("Local services ready");
    await user.click(screen.getByRole("button", { name: "Audit text" }));

    expect(await screen.findByText("Usable results with a partial failure")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry audit" })).toBeEnabled();
  });

  it("shows a concrete setup state when the instruction model is missing", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 503,
        json: async () => ({
          status: "not_ready",
          dependencies: {
            ollama: {
              state: "instruction_model_missing",
              ready: false,
              required: true,
              action: "corepack pnpm ollama:setup",
            },
          },
        }),
      }),
    );
    renderShell("A careful claim.");

    expect(await screen.findByText("Local model is missing")).toBeInTheDocument();
    expect(screen.getByText("corepack pnpm ollama:setup")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Audit text" })).toBeDisabled();
  });

  it("renders a retryable model-timeout result without a low-risk claim", async () => {
    vi.stubGlobal(
      "fetch",
      connectedFetch(auditResponse("failed", "MODEL_TIMEOUT")),
    );
    const user = userEvent.setup();
    renderShell("A careful claim.");

    await screen.findByText("Local services ready");
    await user.click(screen.getByRole("button", { name: "Audit text" }));

    expect(await screen.findByText("The local model timed out")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry audit" })).toBeEnabled();
  });
});
