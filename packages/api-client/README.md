# API client

`openapi.json` is the generated source contract for this package. Regenerate it with
`corepack pnpm openapi:generate` whenever FastAPI routes or schemas change.
`src/schema.ts` is generated from that contract with `openapi-typescript`; do not edit
it by hand. The fetch boundary in `src/index.ts` uses those generated types and is used
by the browser integration. Run `corepack pnpm openapi:generate` after API changes.
