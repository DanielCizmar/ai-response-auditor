import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { WorkspaceShell } from "@/components/workspace-shell";

function renderShell() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <WorkspaceShell />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("WorkspaceShell", () => {
  it("renders the document-first shell and disabled audit action", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => undefined)));

    renderShell();

    expect(screen.getByRole("heading", { name: /review the claim/i })).toBeInTheDocument();
    expect(screen.getByRole("complementary", { name: /claim review/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Audit text" })).toBeDisabled();
    expect(screen.getByText("Checking local services")).toBeInTheDocument();
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
