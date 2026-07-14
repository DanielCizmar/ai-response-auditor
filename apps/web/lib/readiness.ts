export type DependencyState = {
  state: string;
  ready: boolean;
  required: boolean;
  action?: string | null;
};

export type ReadinessResponse = {
  status: "ready" | "not_ready";
  dependencies: Record<string, DependencyState>;
};

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export async function fetchReadiness(): Promise<ReadinessResponse> {
  const response = await fetch(`${API_BASE_URL}/v1/readiness`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok && response.status !== 503) {
    throw new Error("The local API did not return a readiness response.");
  }
  return (await response.json()) as ReadinessResponse;
}
