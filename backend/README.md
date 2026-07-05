# Aegis — Backend

> FastAPI + Cognee + Neo4j + Qdrant — Temporal Knowledge-Graph Engine for Farmland

## Quick start (local, Docker)

```bash
cd backend
cp .env.example .env          # fill in your API keys
docker compose up             # starts all services + API + workers
```

API docs at: http://localhost:8000/docs

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ Next.js Frontend                                                 │
└───────────────────────┬─────────────────────────────────────────┘
                        │ HTTPS / REST
┌───────────────────────▼─────────────────────────────────────────┐
│ FastAPI (API Gateway)                                            │
│  ├─ Auth (JWT, per-farm tenant scoping)                          │
│  ├─ Rate limiting (slowapi)                                      │
│  ├─ Structured logging (structlog)                               │
│  ├─ Prometheus metrics                                           │
│  └─ OpenTelemetry tracing                                        │
└──────────┬──────────────────┬───────────────────────────────────┘
           │                  │
     ┌─────▼──────┐    ┌──────▼───────┐
     │  Postgres  │    │ Celery Queue │
     │ (metadata) │    │ (Redis broker│
     └────────────┘    └──────┬───────┘
                              │
              ┌───────────────▼──────────────────┐
              │  Cognee Pipeline Workers          │
              │  extract → cognify → memify       │
              └──────┬─────────────┬─────────────┘
                     │             │
              ┌──────▼────┐  ┌─────▼─────┐
              │  Neo4j    │  │  Qdrant   │
              │  (graph)  │  │  (vectors)│
              └───────────┘  └───────────┘
```

## Services

| Service | Port | Purpose |
|---|---|---|
| FastAPI | 8000 | REST API |
| Postgres | 5432 | Relational metadata |
| Neo4j | 7687 / 7474 | Knowledge graph |
| Qdrant | 6333 | Vector store + semantic cache |
| Redis | 6379 | Query cache + Celery broker |
| Prometheus | 9090 | Metrics |

## API Endpoints

### Auth
```
POST /auth/login          Login → access + refresh tokens
POST /auth/refresh        Refresh access token
POST /auth/register       Register + create farm
GET  /auth/me             Current user info
```

### Query (primary endpoint)
```
POST /api/v1/query/       Run a diagnostic query
GET  /api/v1/query/history  Query history
GET  /api/v1/query/{id}   Retrieve specific query + evidence trail
```

**Query response shape (first-class fields):**
```json
{
  "answer_text": "...",
  "confidence_label": "documented_fact | statistical_association | unconfirmed_hypothesis",
  "confidence_score": 0.87,
  "evidence_trail": [
    { "node_label": "Chlorpyrifos-X Application",
      "node_type": "ChemicalProduct",
      "relationship_type": "APPLIED_TO",
      "source_document_label": "Pesticide Log Apr 2024",
      "date": "2024-04-10" }
  ],
  "graph_hops": 3,
  "latency_ms": 1840,
  "cache_hit": false
}
```

### Documents
```
POST /api/v1/documents/upload         Upload file (PDF/photo/CSV)
GET  /api/v1/documents/               List documents
GET  /api/v1/documents/review-queue   Pending OCR review (agronomist+)
POST /api/v1/documents/{id}/approve   Approve OCR result
POST /api/v1/documents/{id}/reject    Reject OCR result
GET  /api/v1/documents/{id}/status    Ingest progress polling
```

### Plots
```
GET    /api/v1/plots/                 List plots
POST   /api/v1/plots/                 Create plot
GET    /api/v1/plots/{id}             Get plot
PUT    /api/v1/plots/{id}             Update plot
DELETE /api/v1/plots/{id}             Delete plot (admin)
GET    /api/v1/plots/{id}/graph       Knowledge graph subgraph (nodes + edges)
```

### Corrections
```
POST /api/v1/corrections/                       Submit evidence correction
GET  /api/v1/corrections/                       List corrections (agronomist+)
POST /api/v1/corrections/{id}/confirm-edge      Confirm causal edge (CONFIRMED_CAUSE)
POST /api/v1/corrections/trigger-memify         Trigger memify batch (admin)
```

## Cognee Pipeline

```
Document upload
    ↓
OCR / PDF parse (Azure AI DI → Google Cloud Vision fallback)
    ↓
Confidence routing:
  ≥ 85%  → auto-cognify (Celery task)
  40–85% → human review queue
  < 40%  → rejected
    ↓
Cognee.extract() — adds text to dataset
    ↓
Cognee.cognify() — extracts entities/relationships
  Ontology: Field | ChemicalProduct | WeatherEvent | CropVariant | YieldMeasurement | Practice
  Edges:    APPLIED_TO | OCCURRED_DURING | PRECEDED | CORRELATED_WITH
  CONFIRMED_CAUSE — never auto-asserted, only via agronomist confirmation
    ↓
Neo4j graph nodes (farm_id + plot_id scoped)
Qdrant vectors (per-farm collection)
    ↓ (nightly or on-demand)
Cognee.memify() — processes corrections, improves graph
Redis query cache invalidated
```

## Running tests

```bash
pip install -r requirements.txt
pytest                       # all tests
pytest tests/unit/           # unit only (no external services needed)
pytest tests/integration/    # integration (mocked external services)
```

## Environment variables

Copy `.env.example` → `.env` and fill in:

| Key | Required | Notes |
|---|---|---|
| `SECRET_KEY` | ✅ | `openssl rand -hex 32` |
| `DATABASE_URL` | ✅ | Postgres asyncpg URL |
| `NEO4J_PASSWORD` | ✅ | |
| `ANTHROPIC_API_KEY` | ✅ | Primary LLM |
| `OPENAI_API_KEY` | ✅ | Embeddings |
| `AZURE_FORM_RECOGNIZER_KEY` | Recommended | OCR primary |
| `GOOGLE_APPLICATION_CREDENTIALS` | Recommended | OCR fallback |
| `AWS_ACCESS_KEY_ID` / `SECRET` | ✅ | S3 for document storage |

## Celery workers

```bash
# Cognify queue (LLM-heavy, slow)
celery -A app.workers.celery_app.celery_app worker --queues=cognify --concurrency=2

# Memify queue (nightly batch)
celery -A app.workers.celery_app.celery_app worker --queues=memify --concurrency=1

# Beat scheduler (triggers nightly memify)
celery -A app.workers.celery_app.celery_app beat
```
