# TerraMind frontend

An immediately accessible agricultural evidence sandbox built with Next.js 16,
React 19, and TypeScript. `/` needs no API keys or backend. `/live` is the optional
private farm workspace; see [deployment instructions](../DEPLOYMENT.md).

## Run

Use Node.js 22 or newer (CI uses 22):

```sh
npm ci
npm run dev
```

## Verify

```sh
npm run lint
npm test
npm run typecheck
npm run build
npm run test:api
npm run test:browser
```

`npm run check` runs all of these. Browser tests use `/usr/bin/chromium` when
available, or Playwright's Chromium (`npx playwright install --with-deps chromium`).
Set `CHROMIUM_PATH` to use another installed Chromium executable.
The tests start and stop their own production servers on ports 3100 and 3200.
API proxy tests use a deterministic stub; browser live-workspace requests are
mocked. These checks do not establish readiness of cloud storage or AI providers.

The browser sandbox parses CSV content locally and ranks ready records with
lexical search. PDF/image records are metadata only. Synthetic examples and local
search are labeled explicitly. Private tokens remain in server-managed HttpOnly
cookies. No provider credentials belong in `NEXT_PUBLIC_*` variables.
