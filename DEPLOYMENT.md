# TerraMind deployment status and setup

## Frontend

The existing Vercel project uses `frontend` as its root. Use the Next.js preset,
`npm ci`, and `npm run build`. Set the server-only `BACKEND_URL` environment
variable to the HTTPS origin of the deployed FastAPI service. The Next.js server
proxies authenticated API calls and stores access/refresh tokens in HttpOnly,
Secure production cookies. Do not expose backend URLs containing credentials,
API keys, or bearer tokens through `NEXT_PUBLIC_*` variables.

The public `/` route opens the browser sandbox immediately, without registration,
session checks, backend access, or provider keys. Field selection, document review,
timelines, the graph, and local search work with synthetic records. CSV uploads
are parsed locally (256 KB input, 500 rows, 128 KB parsed output); PDF and image
uploads create metadata records only. Local search ranks ready records by keyword
overlap and cites matching documents. It does not run a language model or infer
causation. Changes persist in browser storage when available. Settings → Reset
demo data restores the original records. Treat browser storage as disposable,
not a durable document store.

The optional `/live` route retains account registration and sign-in for private
farm data. It requires `BACKEND_URL` and a configured backend. Removing the public
sign-in gate does not grant anonymous access to private farm APIs. The signed-in
sample import uses normal backend ingestion and requires its storage and workers.

## Backend

The backend requires a persistent Python/container host, PostgreSQL, Neo4j,
Qdrant, Redis, Celery workers, S3-compatible storage, and provider credentials.
It cannot be deployed as part of the frontend-only Vercel project.

For local development, copy `backend/.env.example` to `backend/.env`, configure
provider credentials, and run `docker compose up --build` from `backend`.
Compose overrides database/cache hostnames to service names. Its built-in database
passwords and published database ports are for local development only.
Optional metrics: `docker compose --profile observability up --build`.

For production, provision managed services and set `APP_ENV=production`,
`DEBUG=false`, `DEMO_MODE=false`, a unique random `SECRET_KEY` (at least 32
characters), `DATABASE_URL`, Neo4j/Qdrant/Redis settings, storage credentials,
and LLM/OCR provider credentials. List-valued environment settings must be JSON
arrays. Configure `ALLOWED_HOSTS` and `CORS_ORIGINS` for the deployment domains.
Run `alembic upgrade head` before starting the API and workers.

Corrections are queued on the Celery worker and processed against only the
correction's plot dataset. A failed queue attempt remains retryable with the manual
trigger. Date-filtered queries return HTTP 501 until the graph adapter can enforce
event-date constraints. Graph confirmations require both endpoint nodes and farm/plot
scope validation. Readiness checks Postgres, Neo4j, Redis, and Qdrant.

## Validation

Run `python -m unittest discover -s checks -v` for isolated query-helper
regressions, and `python -m compileall -q backend` for Python syntax checks.
With backend dependencies installed, run `cd backend && python -m pytest -q`.
For the frontend, run `npm ci`, `npm run lint`, `npx tsc --noEmit`, and
`npm run build` from `frontend`.

The isolated helper checks do not validate database drivers, containers, or
real external services.

## Continuous integration

Pull requests and pushes to `main` run the frontend dependency audit, lint,
TypeScript check, and production build, plus backend syntax, isolated helper,
and API tests. The frontend security gate audits the committed lockfile so the
result matches the dependencies that Vercel will install.

Vercel deploys pull request previews and deploys production from `main`. Review
the preview and confirm the GitHub checks are green before merging. The backend
still needs managed services, provider credentials, and integration checks against
those real services before it can serve as a production farm management API.
