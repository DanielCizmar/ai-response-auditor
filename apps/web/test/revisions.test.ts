import type { AuditClaim } from "@auditor/api-client";
import { describe, expect, it } from "vitest";

import { applyRevisionSafely, StaleRevisionError } from "@/lib/revisions";

const claim = {
  id: "claim-1",
  exact_text: "😀 claim",
  start_offset: 2,
  end_offset: 9,
} as AuditClaim;

describe("safe revisions", () => {
  it("replaces an exact Unicode code-point span without splitting emoji", () => {
    expect(
      applyRevisionSafely("A 😀 claim.", "A 😀 claim.", claim, "careful claim"),
    ).toBe("A careful claim.");
  });

  it("rejects a suggestion after any audited text change", () => {
    expect(() =>
      applyRevisionSafely(
        "A 😀 claim.",
        "A changed 😀 claim.",
        claim,
        "careful claim",
      ),
    ).toThrow(StaleRevisionError);
  });

  it("rejects a mismatched persisted exact span", () => {
    expect(() =>
      applyRevisionSafely(
        "A 😀 claim.",
        "A 😀 claim.",
        { ...claim, exact_text: "wrong" },
        "careful claim",
      ),
    ).toThrow(StaleRevisionError);
  });
});
