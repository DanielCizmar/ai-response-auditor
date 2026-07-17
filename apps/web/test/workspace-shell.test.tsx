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
  claims: Array<Record<string, unknown>> | null = null,
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
    claims:
      state === "failed"
        ? []
        : claims ?? [{ id: "claim-1" }],
    events: [],
  };
}

function connectedFetch(
  audit: ReturnType<typeof auditResponse> | Promise<never>,
) {
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

function reviewClaim(overrides: Record<string, unknown> = {}) {
  return {
    id: "01980abc-0000-7000-8000-000000000101",
    ordinal: 0,
    exact_text: "A careful claim.",
    normalized_text: "A careful claim.",
    start_offset: 0,
    end_offset: 16,
    atomicity: "atomic",
    verifiability: "externally_verifiable",
    primary_type: "causal",
    secondary_types: [],
    status: "overstated",
    extraction_confidence: 0.9,
    risk_score: 45,
    findings: [
      {
        id: "01980abc-0000-7000-8000-000000000201",
        finding_type: "causal_overstatement",
        source_kind: "model_assisted",
        severity: "high",
        details: { explanation: "The wording states causation more strongly than warranted." },
        rule_version: null,
        prompt_version: "overstatement-v1",
      },
    ],
    risk_components: [
      {
        id: "01980abc-0000-7000-8000-000000000301",
        component_type: "causal_absolute_overstatement",
        raw_value: { severity_level: 3 },
        points: 15,
        explanation_message_key: "risk.component.causal_absolute_overstatement",
        scoring_version: "mvp1-risk-v1",
      },
    ],
    suggested_revisions: [
      {
        id: "01980abc-0000-7000-8000-000000000401",
        replacement_text: "The evidence suggests a careful association.",
        rationale: "Qualifies the causal wording.",
        language: "en",
        model_version: "fake-instruction-v1",
        prompt_version: "revision-v1",
        validation_status: "valid",
      },
    ],
    ...overrides,
  };
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

  it("selects a persisted highlighted claim by click and keyboard and shows its review", async () => {
    vi.stubGlobal(
      "fetch",
      connectedFetch(auditResponse("succeeded", null, [reviewClaim()])),
    );
    const user = userEvent.setup();
    renderShell("A careful claim.");

    await screen.findByText("Local services ready");
    await user.click(screen.getByRole("button", { name: "Audit text" }));

    const mark = await screen.findByRole("button", {
      name: "Overstated claim. Review: A careful claim.",
    });
    expect(mark).toHaveAttribute(
      "data-audit-claim-id",
      "01980abc-0000-7000-8000-000000000101",
    );
    await user.click(mark);
    expect(screen.getByText("Causal", { selector: "dd" })).toBeInTheDocument();
    expect(screen.getByText("45 / 100")).toBeInTheDocument();
    expect(
      screen.getByText("The wording states causation more strongly than warranted."),
    ).toBeInTheDocument();
    expect(screen.getByText("The evidence suggests a careful association.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Close claim review" }));
    screen
      .getByRole("button", {
        name: "Overstated claim. Review: A careful claim.",
      })
      .focus();
    await user.keyboard("{Enter}");
    expect(screen.getByText("Causal", { selector: "dd" })).toBeInTheDocument();
  });

  it("exposes a chooser for overlapping persisted claims", async () => {
    const overlap = reviewClaim({
      id: "01980abc-0000-7000-8000-000000000102",
      ordinal: 1,
      exact_text: "careful claim",
      start_offset: 2,
      end_offset: 15,
      primary_type: "factual",
      status: "low_risk",
      risk_score: 10,
      findings: [],
      risk_components: [],
      suggested_revisions: [],
    });
    vi.stubGlobal(
      "fetch",
      connectedFetch(
        auditResponse("succeeded", null, [reviewClaim(), overlap]),
      ),
    );
    const user = userEvent.setup();
    renderShell("A careful claim.");

    await screen.findByText("Local services ready");
    await user.click(screen.getByRole("button", { name: "Audit text" }));
    await user.click(
      await screen.findByRole("button", {
        name: /2 overlapping claims\. Highest status:/i,
      }),
    );

    expect(
      screen.getByRole("group", { name: "2 overlapping claims" }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "careful claim" }));
    expect(screen.getByText("Factual", { selector: "dd" })).toBeInTheDocument();
  });

  it("maps persisted Unicode code-point offsets to the exact highlighted text", async () => {
    const text = "A 😀 claim.";
    const response = {
      ...auditResponse("succeeded", null, [
        reviewClaim({
          exact_text: "😀 claim",
          normalized_text: "😀 claim",
          start_offset: 2,
          end_offset: 9,
        }),
      ]),
      input_text: text,
    };
    vi.stubGlobal("fetch", connectedFetch(response));
    const user = userEvent.setup();
    renderShell(text);

    await screen.findByText("Local services ready");
    await user.click(screen.getByRole("button", { name: "Audit text" }));

    expect(
      await screen.findByRole("button", {
        name: "Overstated claim. Review: 😀 claim",
      }),
    ).toHaveTextContent("😀 claim");
  });

  it("applies an exact-span suggestion, marks the old audit stale, and re-audits edited text", async () => {
    const first = auditResponse("succeeded", null, [reviewClaim()]);
    const second = {
      ...auditResponse("succeeded", null, []),
      id: "01980abc-0000-7000-8000-000000000002",
      re_audit_of_id: first.id,
      input_text: "The evidence suggests a careful association.",
    };
    let auditCalls = 0;
    const fetchMock = vi.fn((input: string | URL | Request, _init?: RequestInit) => {
      void _init;
      if (String(input).endsWith("/v1/readiness")) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ status: "ready", dependencies: {} }),
        });
      }
      auditCalls += 1;
      return Promise.resolve({
        ok: true,
        status: 201,
        json: async () => (auditCalls === 1 ? first : second),
      });
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    renderShell("A careful claim.");

    await screen.findByText("Local services ready");
    await user.click(screen.getByRole("button", { name: "Audit text" }));
    await user.click(
      await screen.findByRole("button", {
        name: "Overstated claim. Review: A careful claim.",
      }),
    );
    await user.click(screen.getByRole("button", { name: "Apply suggestion" }));

    expect(
      screen.getByText(/Suggestion applied\. Re-audit the edited text/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/Highlights are stale until you re-audit/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Apply suggestion" })).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "Re-audit text" }));
    const reAuditCall = fetchMock.mock.calls.find(([input]) =>
      String(input).includes(`/${first.id}/re-audit`),
    );
    expect(reAuditCall).toBeDefined();
    expect(JSON.parse((reAuditCall?.[1] as RequestInit).body as string)).toEqual({
      text: "The evidence suggests a careful association.",
      language: "en",
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
