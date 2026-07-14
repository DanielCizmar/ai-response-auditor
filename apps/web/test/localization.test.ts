import { translatePlural } from "@auditor/i18n";
import { describe, expect, it } from "vitest";

describe("localization catalogs", () => {
  it("uses reviewed Slovak plural forms", () => {
    expect(translatePlural("sk", "editor.overLimit", 1)).toContain("1 znak.");
    expect(translatePlural("sk", "editor.overLimit", 3)).toContain("3 znaky.");
    expect(translatePlural("sk", "editor.overLimit", 8)).toContain("8 znakov.");
  });
});
