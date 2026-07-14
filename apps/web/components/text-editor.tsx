"use client";

import { translate, type Locale } from "@auditor/i18n";
import Placeholder from "@tiptap/extension-placeholder";
import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";

import { getCanonicalText } from "@/lib/canonical-text";
import { useLocale } from "@/lib/locale";

type TextEditorProps = {
  language: Locale;
  value: string;
  onLanguageChange: (language: Locale) => void;
  onTextChange: (text: string) => void;
};

export function TextEditor({
  language,
  value,
  onLanguageChange,
  onTextChange,
}: Readonly<TextEditorProps>) {
  const { locale, t } = useLocale();
  const editor = useEditor({
    immediatelyRender: false,
    content: value,
    extensions: [
      StarterKit.configure({ heading: false, codeBlock: false }),
      Placeholder.configure({
        placeholder: translate(locale, "editor.placeholder"),
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

  return (
    <div>
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
