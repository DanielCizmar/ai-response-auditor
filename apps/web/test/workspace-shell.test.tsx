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
});
