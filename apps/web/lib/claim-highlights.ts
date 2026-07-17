import type { AuditClaim } from "@auditor/api-client";
import { Extension, type Editor } from "@tiptap/core";
import type { Node as ProseMirrorNode } from "@tiptap/pm/model";
import { Plugin, PluginKey } from "@tiptap/pm/state";
import { Decoration, DecorationSet } from "@tiptap/pm/view";

import { codePointOffsetToUtf16Index } from "./canonical-text";

type HighlightState = {
  claims: AuditClaim[];
  auditId: string | null;
  activeClaimId: string | null;
  stale: boolean;
  decorations: DecorationSet;
};

export type ClaimHighlightUpdate = Omit<HighlightState, "decorations">;

const claimHighlightKey = new PluginKey<HighlightState>("claimHighlights");

const riskOrder: Record<NonNullable<AuditClaim["status"]>, number> = {
  low_risk: 0,
  not_verifiable: 1,
  evidence_needed: 2,
  review_recommended: 3,
  overstated: 4,
  internally_inconsistent: 5,
};

export function createClaimHighlights(options: {
  getLabel: (claim: AuditClaim, overlapCount: number) => string;
}) {
  return Extension.create({
    name: "claimHighlights",
    addProseMirrorPlugins() {
      return [
        new Plugin<HighlightState>({
          key: claimHighlightKey,
          state: {
            init: (_, state) => ({
              claims: [],
              auditId: null,
              activeClaimId: null,
              stale: false,
              decorations: DecorationSet.create(state.doc, []),
            }),
            apply(transaction, previous) {
              const update = transaction.getMeta(claimHighlightKey) as
                | ClaimHighlightUpdate
                | undefined;
              const next = update ? { ...previous, ...update } : previous;
              if (!update && !transaction.docChanged) return previous;
              return {
                ...next,
                decorations: buildDecorations(transaction.doc, next, options.getLabel),
              };
            },
          },
          props: {
            decorations(state) {
              return claimHighlightKey.getState(state)?.decorations ?? null;
            },
          },
        }),
      ];
    },
  });
}

export function updateClaimHighlights(
  editor: Editor,
  update: ClaimHighlightUpdate,
) {
  editor.view.dispatch(editor.state.tr.setMeta(claimHighlightKey, update));
}

function buildDecorations(
  doc: ProseMirrorNode,
  state: Omit<HighlightState, "decorations">,
  getLabel: (claim: AuditClaim, overlapCount: number) => string,
): DecorationSet {
  const validClaims = state.claims.filter(
    (claim) =>
      claim.start_offset >= 0 &&
      claim.end_offset > claim.start_offset &&
      claim.status !== null,
  );
  const boundaries = Array.from(
    new Set(validClaims.flatMap((claim) => [claim.start_offset, claim.end_offset])),
  ).sort((left, right) => left - right);
  const textPieces = mapCanonicalTextPieces(doc);
  const decorations: Decoration[] = [];

  for (let index = 0; index < boundaries.length - 1; index += 1) {
    const start = boundaries[index];
    const end = boundaries[index + 1];
    const claims = validClaims.filter(
      (claim) => claim.start_offset <= start && claim.end_offset >= end,
    );
    if (claims.length === 0) continue;
    const primary = [...claims].sort(
      (left, right) => riskOrder[right.status!] - riskOrder[left.status!],
    )[0];
    const claimIds = claims.map((claim) => claim.id);

    for (const piece of textPieces) {
      const intersectionStart = Math.max(start, piece.canonicalStart);
      const intersectionEnd = Math.min(end, piece.canonicalEnd);
      if (intersectionStart >= intersectionEnd) continue;
      const from = piece.pmStart + piece.utf16Index(intersectionStart - piece.canonicalStart);
      const to = piece.pmStart + piece.utf16Index(intersectionEnd - piece.canonicalStart);
      decorations.push(
        Decoration.inline(from, to, {
          "aria-label": getLabel(primary, claims.length),
          class: [
            "claim-mark",
            `claim-mark--${primary.status}`,
            state.activeClaimId && claimIds.includes(state.activeClaimId)
              ? "claim-mark--active"
              : "",
            state.stale ? "claim-mark--stale" : "",
          ]
            .filter(Boolean)
            .join(" "),
          "data-audit-claim-id": primary.id,
          "data-audit-id": state.auditId ?? "",
          "data-claim-ids": claimIds.join(" "),
          role: "button",
          tabindex: "0",
        }),
      );
    }
  }
  return DecorationSet.create(doc, decorations);
}

type TextPiece = {
  canonicalStart: number;
  canonicalEnd: number;
  pmStart: number;
  utf16Index: (relativeCodePointOffset: number) => number;
};

function mapCanonicalTextPieces(doc: ProseMirrorNode): TextPiece[] {
  const blocks: Array<{ node: ProseMirrorNode; position: number }> = [];
  doc.descendants((node, position) => {
    if (!node.isTextblock) return true;
    blocks.push({ node, position });
    return false;
  });

  const pieces: TextPiece[] = [];
  let canonicalPosition = 0;
  blocks.forEach(({ node, position }, blockIndex) => {
    node.descendants((child, childPosition) => {
      if (child.isText && child.text) {
        const length = Array.from(child.text).length;
        pieces.push({
          canonicalStart: canonicalPosition,
          canonicalEnd: canonicalPosition + length,
          pmStart: position + 1 + childPosition,
          utf16Index: (offset) => codePointOffsetToUtf16Index(child.text!, offset),
        });
        canonicalPosition += length;
      } else if (child.type.name === "hardBreak") {
        pieces.push({
          canonicalStart: canonicalPosition,
          canonicalEnd: canonicalPosition + 1,
          pmStart: position + 1 + childPosition,
          utf16Index: (offset) => offset,
        });
        canonicalPosition += 1;
      }
      return child.isInline;
    });
    if (blockIndex < blocks.length - 1) canonicalPosition += 1;
  });
  return pieces;
}
