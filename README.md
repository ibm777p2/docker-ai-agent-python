# Deploy AI Agent

A containerized multi-agent service: a FastAPI (Fast Application Programming Interface framework)
backend that routes a single natural-language request through a LangGraph supervisor to
specialized agents that research a topic and send real email — packaged in Docker, backed by
PostgreSQL, and deployed on DigitalOcean App Platform.

**Stack:** FastAPI · LangGraph + LangChain · SQLModel · PostgreSQL 17 · Docker Compose · DigitalOcean

> **Status: active development.** The full path runs end to end today — request → supervisor →
> agent → tool → SMTP (Simple Mail Transfer Protocol) → response — in local Docker and in
> production. Hardening work is tracked openly in the [Roadmap](#roadmap) rather than left implicit.

```bash
curl -X POST https://<app>.ondigitalocean.app/api/chats/ \
  -H "Content-Type: application/json" \
  -d '{"message": "Research the health benefits of running, then email the summary to me@example.com"}'
```

One request. The supervisor researches the topic with one agent, hands the drafted subject and
body to a second agent, which calls the send tool and reports back what actually happened.

---

## Why this exists

Most agent demos run in a notebook against a local Python process. That hides the parts that
decide whether an agent ships: which component is allowed to take an irreversible action, where
identity comes from, what happens when a tool throws, and how the whole thing survives a deploy.

This service is built the other way around — container first, explicit trust boundaries, real
side effects — so the interesting problems are the production ones.

---

## Architecture

```
  POST /api/chats/  {"message": "..."}
         │
         ▼
  ┌──────────────────────────────────────────────────────────────┐
  │ FastAPI  ·  persist message  ·  invoke supervisor            │
  └───────────────────────────┬──────────────────────────────────┘
                              ▼
  ┌──────────────────────────────────────────────────────────────┐
  │ SUPERVISOR  (langgraph-supervisor)                           │
  │   routes turns · enforces "only email_agent may send"        │
  └───────────┬──────────────────────────────┬───────────────────┘
              ▼                              ▼
  ┌───────────────────────┐      ┌───────────────────────────────┐
  │ research_agent        │      │ email_agent                   │
  │  tools:               │      │  tools:                       │
  │   research_email      │      │   send_an_email    → SMTP SSL │
  │    → structured draft │      │   get_unread_emails→ IMAP SSL │
  │  cannot send email    │      │                               │
  └───────────────────────┘      └───────────────┬───────────────┘
                                                 │
                                                 ▼
                                   Gmail (SMTP send / IMAP read)

  ┌──────────────────────────────────────────────────────────────┐
  │ PostgreSQL 17 — message history (SQLModel, psycopg v3)       │
  └──────────────────────────────────────────────────────────────┘
```

### Design decisions

| Decision | Rationale |
| --- | --- |
| **Capability separation between agents** | `research_agent` is not given the send tool at all. The boundary is structural, not a prompt instruction — an agent cannot misuse a tool it was never bound to. |
| **Supervisor never reports success on its own** | Prompts require the supervisor to relay only what `email_agent` returned (`Sent email` / `Not sent: …`). Prevents the classic failure where a model narrates an action it never took. |
| **Identity via `RunnableConfig`, not tool arguments** | Tool parameters are filled by the *model*; `config.configurable` is filled by *application code*. User identity flows through config, so the model can neither see nor forge it. |
| **Tools return errors as strings, never raise** | A raised exception kills the graph; a returned `"Not sent: …"` goes back into the loop as an observation the model can reason about and report honestly. |
| **Structured output for drafting** (`with_structured_output`) | The draft comes back as a validated `EmailMessageSchema`, not prose to be regex-parsed. Includes an `invalid_request` flag so refusals are typed rather than free text. |
| **Hand-written agent loop kept alongside the framework** | `ai/assistants.py` implements the raw harness — transport → parse tool calls → dispatch → feed results back by `tool_call_id` → stop at `MAX_TURNS`. Demonstrates the mechanism the framework abstracts, and provides a dependency-free fallback path. |
| **`DATABASE_URL` scheme normalization** | Managed Postgres providers hand out `postgres://` / `postgresql://`; SQLAlchemy needs the driver-qualified `postgresql+psycopg://`. Rewritten at startup so the same image accepts any provider's connection string unmodified. |
| **Separate read model from table model** | `ChatMessageListItem` defines the wire response independently of the `ChatMessage` table, so adding a column does not silently widen the public API. |
| **Timezone-aware `created_at`** | `DateTime(timezone=True)` at the column level — timestamps are unambiguous across regions and safe for time-series queries. |
| **Compose `develop.watch` instead of `--reload`** | Restarts the *container*, not just the worker. Development behavior matches the deployed container boundary. |
| **Dependency layer cached before source copy** | Source edits rebuild in seconds instead of reinstalling the LangChain dependency tree. |
| **Virtual environment inside the image** (`/opt/venv`) | Isolates app packages from the base image's system Python. |
| **`OPENAI_BASE_URL` left configurable** | The client is OpenAI-compatible, so pointing at Docker Model Runner (`http://model-runner.docker.internal/engines/v1`) runs the agents against a local model with no key and no per-token cost during development. |

---

## Project layout

```
.
├── compose.yaml                  # topology, ports, watch rules, named volume
├── .env.sample / .env.sample-db  # documented configuration surface
├── docker-commands.md            # build / push / exec / model-runner reference
├── backend/
│   ├── Dockerfile                # venv, cached dependency layer, source copy
│   ├── .dockerignore
│   ├── requirements.txt
│   ├── railway.json              # alternate deploy target config
│   └── src/
│       ├── main.py               # app factory, lifespan, fail-fast env validation
│       └── api/
│           ├── db.py             # engine, URL normalization, session dependency
│           ├── chat/             # payload / table / read models + router
│           ├── ai/
│           │   ├── llms.py       # OpenAI-compatible client factory
│           │   ├── schemas.py    # structured-output contracts
│           │   ├── services.py   # structured draft generation
│           │   ├── tools.py      # @tool definitions, config-scoped identity
│           │   ├── agents.py     # react agents + supervisor graph
│           │   └── assistants.py # hand-rolled agent loop
│           └── emailer/
│               ├── sender.py             # SMTP over SSL
│               ├── inbox_reader.py       # inbox query wrapper
│               └── gmail_imap_parser.py  # ~800-line IMAP client
└── static_html/                  # optional static-asset service
```

### The IMAP layer

`gmail_imap_parser.py` is a full Internet Message Access Protocol (IMAP) client rather than a
thin wrapper, because reading a real inbox is messier than it looks:

- **UID-based addressing** — sequence numbers shift as the mailbox changes; unique identifiers don't.
- **Non-destructive reads** — fetching an unread message normally marks it read. The parser
  restores the unread flag, so the agent can inspect an inbox without mutating the user's state.
- **Flexible search criteria** — relative windows (hours / days / minutes), absolute ranges,
  sender filters, and unread-only, composed into valid IMAP search syntax.
- **Multipart body extraction** with header decoding (RFC 2047 encoded words, mixed charsets).
- **Multi-folder search** and graceful teardown on broken sockets.

---

## Running it

**Prerequisites:** Docker Desktop (or Docker Engine + Compose v2), an OpenAI-compatible API key,
and a Gmail app password if you want live email.

```bash
git clone https://github.com/ibm777p2/docker-ai-agent-python.git
cd docker-ai-agent-python
cp .env.sample .env          # fill in real values
docker compose up --build
```

Development with live restart:

```bash
docker compose up --watch
```

Teardown:

```bash
docker compose down          # keep database volume
docker compose down -v       # drop it
```

Local API at `http://localhost:8080`, interactive docs at `/docs`, OpenAPI schema at `/openapi.json`.

### Configuration

| Variable | Purpose |
| --- | --- |
| `API_KEY` | Required. Startup fails immediately if unset — misconfiguration surfaces at boot, not at first request. |
| `DATABASE_URL` | Postgres connection string; any common scheme is normalized at startup. |
| `OPENAI_API_KEY` | Required by the language-model client. |
| `OPENAI_MODEL_NAME` | Model identifier (default `gpt-4o-mini`). |
| `OPENAI_BASE_URL` | Optional. Point at Docker Model Runner for local inference. |
| `EMAIL_ADDRESS` / `EMAIL_PASSWORD` | Gmail account and **app password** — never an account password. |
| `EMAIL_HOST` / `EMAIL_PORT` | SMTP endpoint (defaults `smtp.gmail.com:465`). |
| `MY_PROJECT` | Display name on the index route. |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | Database bootstrap. |

Sample files are committed for onboarding; real `.env` files are gitignored.

---

## API surface

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/` | Service metadata / liveness. |
| `GET` | `/api/chats/` | Router health check. |
| `GET` | `/api/chats/recent/` | Ten most recent messages, via the read model. |
| `POST` | `/api/chats/` | Persist the message, run it through the supervisor, return the final agent turn. |

```bash
# plain generation
curl -X POST http://localhost:8080/api/chats/ \
  -H "Content-Type: application/json" \
  -d '{"message": "Summarize the benefits of running"}'

# research, then a real send — exercises both agents and the handoff
curl -X POST http://localhost:8080/api/chats/ \
  -H "Content-Type: application/json" \
  -d '{"message": "Research the benefits of running then email the summary to me@example.com"}'

# history
curl http://localhost:8080/api/chats/recent/
```

---

## Local model inference

The client is OpenAI-compatible, so development can run entirely offline against Docker Model
Runner — no vendor key, no per-token cost, no network round trip while iterating on prompts.

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

Set `OPENAI_BASE_URL=http://model-runner.docker.internal/engines/v1` and the agents use it with
no code change.

---

## Deployment

Deployed on **DigitalOcean App Platform**, built from `backend/Dockerfile` rather than a
buildpack — the deployed artifact is the image that was tested locally, not a re-derived one.
Managed Postgres is attached via `DATABASE_URL`, which the startup normalization accepts in
whatever scheme the platform injects. Secrets are supplied as platform environment variables and
never committed.

```bash
curl -X POST https://<app>.ondigitalocean.app/api/chats/ \
  -H "Content-Type: application/json" \
  -d '{"message": "Summarize the benefits of running"}'
```

`backend/railway.json` remains in the repository as a second, working deploy configuration —
the containerized build is portable across platforms by design.

Publishing the image directly:

```bash
docker build -f backend/Dockerfile -t ibm777p2/ai-pyapp:v1 backend/
docker push ibm777p2/ai-pyapp:v1
```

See `docker-commands.md` for the full build, exec, and cleanup reference.

---

## Roadmap

Known gaps, tracked deliberately.

- [ ] **Authentication on `/api/chats/`.** The endpoint can send email; `API_KEY` is currently
      validated as present at startup but not enforced per request. This is the top priority.
- [ ] **Recipient allowlist and rate limiting** on the send tool — hard limits that a prompt
      cannot talk its way past.
- [ ] **Move supervisor execution off the request path.** A multi-agent run is measured in
      seconds; it belongs in a background task with a job id and a polling or streaming endpoint.
- [ ] **Persist agent turns and tool calls**, not just the inbound message — an audit trail of
      what each agent did and which tools fired.
- [ ] **Alembic migrations.** `create_all()` builds tables but does not version schema changes.
- [ ] **Pin the image's default `CMD` to uvicorn.** Compose and the platform both override it
      today; the image should be correct standalone.
- [ ] **Compose healthcheck** with `depends_on: condition: service_healthy`, so the API waits for
      Postgres to accept connections rather than merely to exist.
- [ ] **Non-root container user** and a multi-stage build to drop build tooling from the runtime layer.
- [ ] **Test suite** — pytest against a throwaway Postgres service, with tool calls stubbed so
      agent routing can be asserted without sending real email.
- [ ] **GitHub Actions**: lint, test, build, push on tag.
- [ ] **Structured JSON logging** and a readiness endpoint separate from liveness.
- [ ] **Pinned transitive dependencies** via `pip-compile` for reproducible builds.

---

## Author

**Vincent Lai** — full-stack engineer, Bay Area.
[vincentlai.web.app](https://vincentlai.web.app) · [github.com/ibm777p2](https://github.com/ibm777p2)
