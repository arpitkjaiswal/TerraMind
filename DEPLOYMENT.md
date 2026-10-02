# TerraMind deployment status and setup

## Frontend

The existing Vercel project uses `frontend` as its root. Use the Next.js preset,
`npm ci`, and `npm run build`. No secrets are needed for the sample dashboard.
The UI explicitly identifies sample data and simulated uploads/review actions.
Live query failures are displayed instead of being replaced with fabricated success.
The **View sample answer for Field B** button shows the original demo question.

To connect a backend, set the server-side `BACKEND_URL` to its HTTPS origin in
Vercel and rebuild. `/api/v1/*` requests are proxied to that origin. Do not put
API keys or shared bearer tokens in public environment variables.

The dashboard currently uses mock farms/plots and has no sign-in flow. A backend
URL alone does not turn this into a production farm management application:
real account sign-in, authenticated API calls, and farm data loading still need
integration. Upload/OCR controls remain explicitly labeled local simulations.

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

The review environment could not download npm/Python dependencies, so the full
build/API tests must be checked in GitHub Actions and Vercel. The isolated helper
checks do not validate database drivers, containers, or real external services.
