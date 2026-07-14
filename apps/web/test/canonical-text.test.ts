import { Editor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { describe, expect, it } from "vitest";

import {
  codePointOffsetToUtf16Index,
  countUnicodeCharacters,
  getCanonicalText,
  sliceByCodePointOffsets,
} from "@/lib/canonical-text";

describe("canonical text", () => {
  it("round-trips paragraphs, hard breaks, diacritics, emoji, and combining marks", () => {
    const editor = new Editor({
      extensions: [StarterKit],
      content: {
        type: "doc",
        content: [
          {
            type: "paragraph",
            content: [
              { type: "text", text: "Prvý riadok 😀" },
              { type: "hardBreak" },
              { type: "text", text: "druhý e\u0301" },
            ],
          },
          { type: "paragraph", content: [{ type: "text", text: "Žiadna zmena." }] },
          {
            type: "bulletList",
            content: [
              {
                type: "listItem",
                content: [
                  { type: "paragraph", content: [{ type: "text", text: "bod jeden" }] },
                ],
              },
              {
                type: "listItem",
                content: [
                  { type: "paragraph", content: [{ type: "text", text: "bod dva" }] },
                ],
              },
            ],
          },
        ],
      },
    });

    expect(getCanonicalText(editor)).toBe(
      "Prvý riadok 😀\ndruhý e\u0301\nŽiadna zmena.\nbod jeden\nbod dva",
    );
    editor.destroy();
  });

  it("counts Unicode code points rather than UTF-16 code units", () => {
    expect(countUnicodeCharacters("A😀e\u0301")).toBe(4);
  });

  it("maps persisted code-point offsets without splitting emoji", () => {
    const source = "A😀e\u0301Z";

    expect(sliceByCodePointOffsets(source, 1, 4)).toBe("😀e\u0301");
    expect(codePointOffsetToUtf16Index(source, 2)).toBe(3);
    expect(() => sliceByCodePointOffsets(source, 0, 6)).toThrow(RangeError);
  });
});
