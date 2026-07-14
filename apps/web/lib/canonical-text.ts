import type { Editor } from "@tiptap/react";

/**
 * Return the immutable plain-text form used by future audits.
 *
 * TipTap block boundaries and explicit hard breaks both become LF. No Unicode
 * normalization is applied: exact user-entered code points remain intact.
 */
export function getCanonicalText(editor: Editor): string {
  const blocks: string[] = [];
  editor.state.doc.descendants((node) => {
    if (!node.isTextblock) return true;
    blocks.push(node.textBetween(0, node.content.size, "\n", "\n"));
    return false;
  });
  return blocks.join("\n");
}

export function countUnicodeCharacters(text: string): number {
  return Array.from(text).length;
}
