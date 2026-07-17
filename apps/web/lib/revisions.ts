import type { AuditClaim } from "@auditor/api-client";

import {
  codePointOffsetToUtf16Index,
  sliceByCodePointOffsets,
} from "./canonical-text";

export class StaleRevisionError extends Error {
  constructor() {
    super("The audited text or claim span has changed.");
    this.name = "StaleRevisionError";
  }
}

export function applyRevisionSafely(
  auditedText: string,
  currentText: string,
  claim: AuditClaim,
  replacementText: string,
): string {
  if (
    currentText !== auditedText ||
    sliceByCodePointOffsets(
      auditedText,
      claim.start_offset,
      claim.end_offset,
    ) !== claim.exact_text
  ) {
    throw new StaleRevisionError();
  }
  const start = codePointOffsetToUtf16Index(currentText, claim.start_offset);
  const end = codePointOffsetToUtf16Index(currentText, claim.end_offset);
  return currentText.slice(0, start) + replacementText + currentText.slice(end);
}
