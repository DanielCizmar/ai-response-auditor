# Internationalization

Reviewed English and Slovak catalogs live in `src/en.json` and `src/sk.json`.
Application state persists language-independent keys and enums; interface copy is
resolved at render time. The browser preference key is `auditor.interface-locale`.
