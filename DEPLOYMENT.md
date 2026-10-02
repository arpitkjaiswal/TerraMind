# TerraMind deployment status and setup

## Frontend

The existing Vercel project uses `frontend` as its root. Use the Next.js preset,
`npm ci`, and `npm run build`. No secrets are needed for the sample dashboard.
The UI identifies its data as a local demo. Uploads, review decisions, and query
counts are saved in browser storage; uploaded files are not sent to a server.
Demo queries summarize visible record titles and dates, and do not read file
contents or infer causes. The graph and timeline are scoped to the selected field.
Use **Settings → Reset demo data** to restore the original sample set.

To connect a backend, set the server-side `BACKEND_URL` to its HTTPS origin in
Vercel and rebuild. `/api/v1/*` requests are proxied to that origin. Do not put
API keys or shared bearer tokens in public environment variables.

The dashboard currently uses mock farms/plots and has no sign-in flow. A backend
URL alone does not turn this into a production farm management application:
real account sign-in, authenticated API calls, farm data loading, and document
processing still need integration. Demo query output is not a live AI answer.

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

Correction reprocessing is not implemented in the existing Cognee adapter. It
now fails explicitly and leaves corrections pending rather than claiming they
were processed. Cognee configuration/search compatibility, temporal filtering,
worker transaction ordering, and end-to-end OCR/storage/provider behavior still
require integration validation before production backend deployment.

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
still needs managed services, provider credentials, account sign-in, and real
farm data integration before it can serve as a production farm management API.
