# Web application

The Next.js application is an editorial evidence workbench. Start it from the
repository root with `corepack pnpm dev:web` and create a production build with
`corepack pnpm build:web`.

Set `NEXT_PUBLIC_API_BASE_URL` to the local FastAPI origin when it differs from
`http://127.0.0.1:8000`. When the API cannot be reached, the shell remains usable
and presents a concrete local setup action instead of implying that audits work.

The M1.3 TipTap surface accepts pasted or edited English and Slovak text. Canonical
text uses LF for block boundaries and hard breaks, preserves entered Unicode code
points without normalization, and is limited to 10,000 Unicode characters. UI
language and audited-text language are independent choices. Audit execution is not
part of this milestone, so the action is visibly unavailable.
