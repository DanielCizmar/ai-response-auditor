import {
  createAudit as createAuditRequest,
  reAudit as reAuditRequest,
  type Audit,
  type AuditLanguage,
} from "@auditor/api-client";

import { API_BASE_URL } from "./readiness";

export class AuditRequestTimeout extends Error {
  constructor() {
    super("The browser stopped waiting for the local audit.");
    this.name = "AuditRequestTimeout";
  }
}

export async function runAudit(input: {
  text: string;
  language: AuditLanguage;
  idempotencyKey: string;
  sourceAuditId?: string;
}): Promise<Audit> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 190_000);
  try {
    return input.sourceAuditId
      ? await reAuditRequest(
          API_BASE_URL,
          input.sourceAuditId,
          input,
          controller.signal,
        )
      : await createAuditRequest(API_BASE_URL, input, controller.signal);
  } catch (error) {
    if (controller.signal.aborted) {
      throw new AuditRequestTimeout();
    }
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
}
