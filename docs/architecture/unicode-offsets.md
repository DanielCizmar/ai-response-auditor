# Canonical Unicode offset convention

Version `unicode-code-points-v1` defines every persisted text offset as a zero-based,
end-exclusive count of Unicode code points in the immutable canonical plain text.
No NFC or NFKC normalization is applied after offsets are created.

Python string indices already use this convention. JavaScript strings use UTF-16
code units, so browser code must convert through `Array.from(text)` before slicing
or mapping a persisted offset into an editor position. An offset is valid only when:

```text
canonical_text[start_offset:end_offset] == exact_text
```

Sentence and claim validators enforce that invariant. Fixtures cover Slovak
diacritics, emoji, combining characters, paragraphs, lists, and hard breaks.
