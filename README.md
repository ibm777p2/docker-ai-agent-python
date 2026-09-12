# DeployAI — Containerized FastAPI + Postgres Service Template

A production-shaped starting point for Python API (Application Programming Interface) services
that need to be developed in containers and deployed without rewrites. The same image that runs
on a laptop runs in CI and on the platform — no "works on my machine" gap between environments.

**Stack:** FastAPI · SQLModel · PostgreSQL 17 · Docker Compose · Railway

> **Status: active development.** The container, database, and deploy paths run end to end
> today; the service layer is intentionally minimal while the foundation is built out.
> Current gaps are tracked openly in the [Roadmap](#roadmap) rather than left implicit.

---

## Why this exists

Most Python API examples stop at `uvicorn main:app` on the host machine. That skips the parts
that actually decide whether a service ships: dependency isolation, database lifecycle, config
via environment, image portability, and a deploy target. This template starts from the container
and works outward, so the first deploy is a configuration change rather than a re-architecture.

Design decisions worth calling out:

| Decision | Rationale |
| --- | --- |
| Virtual environment **inside** the image (`/opt/venv`) | Isolates app dependencies from the system Python in the base image; keeps `pip` upgrades from touching OS-managed packages. |
| `requirements.txt` copied and installed **before** the source | Docker layer caching — source edits rebuild in seconds instead of reinstalling the dependency tree. |
| Compose `develop.watch` instead of `--reload` | Restarts the *container*, not just the worker process. Code changes are validated against the real container boundary, so dev behavior matches production behavior. |
| SQLModel over raw SQL or a heavier ORM (Object-Relational Mapper) | One class definition serves as the Pydantic validation schema, the response serializer, and the table definition — less drift between layers. |
| `psycopg` v3 with the binary wheel | Modern driver, no local `libpq` build step, smaller and more reproducible image builds. |
| Named volume for Postgres data | Database state survives `docker compose down` and container rebuilds; teardown is explicit (`-v`). |
| Config strictly from environment | Twelve-factor style. The app fails fast at startup if `API_KEY` is missing rather than failing later at request time. |
| Separate `Dockerfile` per service | The static-site service and the API build independently; neither carries the other's dependencies. |

---

## Architecture

```
                    ┌────────────────────────────────────────────┐
   host :8080 ─────►│ backend (python:3.14-slim)                 │
                    │   uvicorn → FastAPI app                    │
                    │   GET  /            service metadata       │
                    │   ...  /api/chats/  chat router            │
                    │   venv /opt/venv · source /app             │
                    └────────────────┬───────────────────────────┘
                                     │ DATABASE_URL
                                     │ postgresql+psycopg://…@db_service:5432/camba
                    ┌────────────────▼───────────────────────────┐
   host :5432 ─────►│ db_service (postgres:17.5)                 │
                    │   volume: dc_managed_db_volume             │
                    └────────────────────────────────────────────┘

   optional         ┌────────────────────────────────────────────┐
   host :3030 ─────►│ static_html (python -m http.server)        │  (disabled in compose.yaml)
                    └────────────────────────────────────────────┘
```

Services resolve each other by Compose service name over the default bridge network —
the API reaches Postgres at `db_service:5432`, never at `localhost`.

### Request lifecycle

1. FastAPI's `lifespan` hook runs `init_db()` at startup, creating tables from SQLModel metadata.
2. A request hits a router mounted under `/api/chats`.
3. `Depends(get_session)` yields a scoped SQLAlchemy/SQLModel session per request and closes it after.
4. The payload is validated by `ChatMessagePayload`, persisted as `ChatMessage`, refreshed to pick
   up the generated primary key, and returned through `response_model` — validated on the way in
   *and* on the way out.

---

## Project layout

```
.
├── compose.yaml              # service topology, port mapping, watch rules, volumes
├── .env.sample               # API_KEY, DATABASE_URL
├── .env.sample-db            # Postgres bootstrap credentials
├── docker-commands.md        # build/push/exec/model-runner reference
├── backend/
│   ├── Dockerfile            # venv, cached dependency layer, source copy
│   ├── .dockerignore         # keeps dev-only paths out of build context
│   ├── railway.json          # deploy config: builder, watch patterns, start command
│   ├── requirements.txt
│   └── src/
│       ├── main.py           # app factory, lifespan, env validation, router mounting
│       └── api/
│           ├── db.py         # engine, init_db(), get_session() dependency
│           └── chat/
│               ├── models.py # payload schema + table model
│               └── routing.py# APIRouter endpoints
└── static_html/              # optional static-asset service
```

---

## Running it

**Prerequisites:** Docker Desktop (or Docker Engine + Compose v2).

```bash
git clone https://github.com/ibm777p2/docker-ai-agent-python.git
cd docker-ai-agent-python
cp .env.sample .env.local        # then set a real API_KEY
docker compose up --build
```

Live-reload development, using Compose's watch rules:

```bash
docker compose up --watch
```

`backend/src/` changes restart the container; `requirements.txt` or `Dockerfile` changes
trigger a full rebuild.

Teardown:

```bash
docker compose down        # keep database volume
docker compose down -v     # drop database volume as well
```

### Environment

| Variable | Used by | Purpose |
| --- | --- | --- |
| `API_KEY` | backend | Required. App raises at startup if unset — misconfiguration surfaces immediately, not on first request. |
| `DATABASE_URL` | backend | `postgresql+psycopg://dbuser:db-password@db_service:5432/camba` |
| `MY_PROJECT` | backend | Display name returned by the index route. |
| `PORT` | backend | Container-side listen port (8000). |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | db_service | Database bootstrap. |

Sample files are committed for onboarding; real `.env` files are gitignored.

---

## API surface

Interactive docs are generated from the type annotations at `http://localhost:8080/docs`
(OpenAPI schema at `/openapi.json`).

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/` | Service metadata / liveness. |
| `GET` | `/api/chats/` | Router health check. |
| `GET` | `/api/chats/recent/` | Ten most recent messages. |
| `POST` | `/api/chats/` | Validate and persist a message; returns the row with its generated id. |

```bash
curl http://localhost:8080/

curl -X POST http://localhost:8080/api/chats/ \
  -H "Content-Type: application/json" \
  -d '{"message": "hello from the host"}'

curl http://localhost:8080/api/chats/recent/
```

From inside another container, the host is reachable at `host.docker.internal`:

```bash
curl -X POST http://host.docker.internal:8080/api/chats/ \
  -H "Content-Type: application/json" -d '{"message": "hello from a container"}'
```

---

## Local model inference

The template targets workloads that call a language model, and Docker Model Runner keeps that
dependency local during development — no vendor key, no per-token cost, no network round trip
while iterating.

```bash
# from the host
curl http://localhost:12434/engines/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "ai/gemma3", "messages": [{"role": "user", "content": "ping"}]}'

# from within a container
curl http://model-runner.docker.internal/engines/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "ai/gemma3", "messages": [{"role": "user", "content": "ping"}]}'
```

The endpoint is OpenAI-compatible, so the same client code points at a hosted provider in
production by swapping a base URL and adding a key.

---

## Deployment

`backend/railway.json` builds from the Dockerfile rather than a buildpack, so the deployed
artifact is the image that was tested locally. `watchPatterns` scope redeploys to the paths that
actually affect the build, and `startCommand` runs uvicorn bound to `0.0.0.0`.

Publishing the image directly:

```bash
docker build -f backend/Dockerfile -t ibm777p2/ai-pyapp:v1 backend/
docker push ibm777p2/ai-pyapp:v1
```

See `docker-commands.md` for the full build, exec, and cleanup reference.

---

## Roadmap

Tracked deliberately — this is a template in progress, and each item below is a known gap
rather than an oversight.

- [ ] **Alembic migrations.** `SQLModel.metadata.create_all()` creates tables but does not version
      schema changes; migrations are required before any real data lands in it.
- [ ] **Pin the image's default `CMD` to uvicorn.** Compose and Railway both override it today;
      the image should be correct standalone.
- [ ] **Compose healthcheck + `depends_on: condition: service_healthy`** so the API waits for
      Postgres to accept connections instead of just for the container to exist.
- [ ] **Non-root container user** and a multi-stage build to drop build-time tooling from the
      runtime layer.
- [ ] **API key authentication middleware** — the key is validated as present, not yet enforced
      on requests.
- [ ] **Pytest suite** against a throwaway Postgres service, with FastAPI's `TestClient`.
- [ ] **GitHub Actions**: lint, test, build, push on tag.
- [ ] **Structured JSON logging and `/health` readiness split** (liveness vs. dependency checks).
- [ ] **Pinned transitive dependencies** via `pip-compile` for reproducible builds.

---

## Author

**Vincent Lai** — full-stack engineer, Bay Area.
[vincentlai.web.app](https://vincentlai.web.app) · [github.com/ibm777p2](https://github.com/ibm777p2)
