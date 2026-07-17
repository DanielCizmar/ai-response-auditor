"use client";

import type { AuditClaim } from "@auditor/api-client";
import { translate, type Locale, type MessageKey } from "@auditor/i18n";
import Placeholder from "@tiptap/extension-placeholder";
import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { useEffect, type KeyboardEvent, type MouseEvent } from "react";

import {
  canonicalTextToDocument,
  getCanonicalText,
} from "@/lib/canonical-text";
import {
  createClaimHighlights,
  updateClaimHighlights,
} from "@/lib/claim-highlights";
import { useLocale } from "@/lib/locale";

type TextEditorProps = {
  language: Locale;
  value: string;
  auditId: string | null;
  claims: AuditClaim[];
  activeClaimId: string | null;
  highlightsStale: boolean;
  onLanguageChange: (language: Locale) => void;
  onClaimSelect: (claimIds: string[]) => void;
  onTextChange: (text: string) => void;
};

export function TextEditor({
  language,
  value,
  auditId,
  claims,
  activeClaimId,
  highlightsStale,
  onLanguageChange,
  onClaimSelect,
  onTextChange,
}: Readonly<TextEditorProps>) {
  const { locale, t } = useLocale();
  const editor = useEditor({
    immediatelyRender: false,
    content: canonicalTextToDocument(value),
    extensions: [
      StarterKit.configure({ heading: false, codeBlock: false }),
      Placeholder.configure({
        placeholder: translate(locale, "editor.placeholder"),
      }),
      createClaimHighlights({
        getLabel: (claim, overlapCount) =>
          overlapCount > 1
            ? t("claim.highlight.overlap", {
                count: overlapCount,
                status: claimStatusLabel(claim, t),
                text: claim.exact_text,
              })
            : t("claim.highlight.label", {
                status: claimStatusLabel(claim, t),
                text: claim.exact_text,
              }),
      }),
    ],
    editorProps: {
      attributes: {
        "aria-label": t("editor.label"),
        "aria-describedby": "editor-help editor-validation",
        class:
          "auditor-editor min-h-[18rem] font-prose text-[1.075rem] leading-8 text-ink outline-none",
        role: "textbox",
      },
    },
    onUpdate: ({ editor: currentEditor }) => {
      onTextChange(getCanonicalText(currentEditor));
    },
    onCreate: ({ editor: currentEditor }) => {
      onTextChange(getCanonicalText(currentEditor));
    },
  }, [locale]);

  useEffect(() => {
    if (!editor || getCanonicalText(editor) === value) return;
    editor.commands.setContent(canonicalTextToDocument(value), {
      emitUpdate: false,
    });
  }, [editor, value]);

  useEffect(() => {
    if (!editor) return;
    updateClaimHighlights(editor, {
      claims,
      auditId,
      activeClaimId,
      stale: highlightsStale,
    });
  }, [activeClaimId, auditId, claims, editor, highlightsStale]);

  function selectClaimFromTarget(target: EventTarget | null) {
    if (!(target instanceof Element)) return false;
    const claimIds =
      target
        .closest<HTMLElement>("[data-claim-ids]")
        ?.dataset.claimIds?.split(" ")
        .filter(Boolean) ?? [];
    if (claimIds.length === 0) return false;
    onClaimSelect(claimIds);
    return true;
  }

  function handleClaimClick(event: MouseEvent<HTMLDivElement>) {
    selectClaimFromTarget(event.target);
  }

  function handleClaimKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key !== "Enter" && event.key !== " ") return;
    if (selectClaimFromTarget(event.target)) {
      event.preventDefault();
      event.stopPropagation();
    }
  }

  return (
    <div onClick={handleClaimClick} onKeyDownCapture={handleClaimKeyDown}>
      <div className="mb-5 flex flex-col gap-3 border-b border-faint-line pb-4 sm:flex-row sm:items-center sm:justify-between">
        <label className="flex items-center gap-3 text-sm font-semibold text-ink">
          {t("editor.language.label")}
          <select
            className="min-w-32 border border-line bg-paper px-3 py-2 text-sm font-normal text-ink outline-none focus-visible:ring-2 focus-visible:ring-mineral"
            onChange={(event) => onLanguageChange(event.target.value as Locale)}
            value={language}
          >
            <option value="en">{t("editor.language.en")}</option>
            <option value="sk">{t("editor.language.sk")}</option>
          </select>
        </label>
        <p id="editor-help" className="max-w-md text-xs leading-5 text-evidence-needed sm:text-right">
          {t("editor.help")}
        </p>
      </div>
      <EditorContent editor={editor} aria-describedby="editor-help editor-validation" />
    </div>
  );
}

function claimStatusLabel(
  claim: AuditClaim,
  t: (key: MessageKey) => string,
): string {
  const key = claim.status ? statusKeys[claim.status] : undefined;
  return key ? t(key) : t("claim.notAvailable");
}

const statusKeys: Record<string, MessageKey> = {
  low_risk: "claim.status.lowRisk",
  review_recommended: "claim.status.reviewRecommended",
  evidence_needed: "claim.status.evidenceNeeded",
  internally_inconsistent: "claim.status.internallyInconsistent",
  overstated: "claim.status.overstated",
  not_verifiable: "claim.status.notVerifiable",
};
