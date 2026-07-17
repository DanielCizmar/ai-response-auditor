import type { components } from "./schema";

export type AuditLanguage = components["schemas"]["AuditLanguage"];
export type AuditState = components["schemas"]["AuditState"];
export type AuditFinding = components["schemas"]["FindingResult"];
export type AuditClaim = components["schemas"]["ClaimResult"];
export type Audit = components["schemas"]["AuditResult"];

type ErrorEnvelope = components["schemas"]["ErrorEnvelope"];

export class ApiClientError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string,
    readonly details: Record<string, unknown> = {},
  ) {
    super(message);
    this.name = "ApiClientError";
  }
}

export async function createAudit(
  baseUrl: string,
  request: { text: string; language: AuditLanguage; idempotencyKey: string },
  signal?: AbortSignal,
): Promise<Audit> {
  const response = await fetch(`${baseUrl}/v1/audits`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": request.idempotencyKey,
    },
    body: JSON.stringify({ text: request.text, language: request.language }),
    signal,
  });
  if (!response.ok) {
    let envelope: Partial<ErrorEnvelope> = {};
    try {
      envelope = (await response.json()) as ErrorEnvelope;
    } catch {
      // The public error below remains content-free when a proxy returns non-JSON.
    }
    throw new ApiClientError(
      envelope.error?.message ?? "The local audit request failed.",
      response.status,
      envelope.error?.code ?? "REQUEST_FAILED",
      envelope.error?.details,
    );
  }
  return (await response.json()) as Audit;
}

export async function getAudit(
  baseUrl: string,
  auditId: string,
  signal?: AbortSignal,
): Promise<Audit> {
  const response = await fetch(`${baseUrl}/v1/audits/${auditId}`, {
    headers: { Accept: "application/json" },
    signal,
  });
  if (!response.ok) {
    throw new ApiClientError(
      "The saved audit could not be loaded.",
      response.status,
      response.status === 404 ? "AUDIT_NOT_FOUND" : "REQUEST_FAILED",
    );
  }
  return (await response.json()) as Audit;
}

export async function reAudit(
  baseUrl: string,
  auditId: string,
  request: { text: string; language: AuditLanguage; idempotencyKey: string },
  signal?: AbortSignal,
): Promise<Audit> {
  const response = await fetch(`${baseUrl}/v1/audits/${auditId}/re-audit`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "Idempotency-Key": request.idempotencyKey,
    },
    body: JSON.stringify({ text: request.text, language: request.language }),
    signal,
  });
  if (!response.ok) {
    let envelope: Partial<ErrorEnvelope> = {};
    try {
      envelope = (await response.json()) as ErrorEnvelope;
    } catch {
      // The public error below remains content-free when a proxy returns non-JSON.
    }
    throw new ApiClientError(
      envelope.error?.message ?? "The local re-audit request failed.",
      response.status,
      envelope.error?.code ?? "REQUEST_FAILED",
      envelope.error?.details,
    );
  }
  return (await response.json()) as Audit;
}
