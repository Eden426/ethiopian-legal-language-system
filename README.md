# Ethiopian Legal Language System

One integrated system with three connected parts:

1. Amharic-to-English legal-scope machine translation using one selected model;
2. bilingual search and retrieval-augmented answers (RAG); and
3. a scanned-PDF parallel-corpus builder.

> Translations, alignments, and generated answers are non-official output and are not legal advice.
> Answers must cite supporting passages or abstain.

## Delivery order

### Project 1 — Amharic-to-English legal-scope machine translation

Build the first translation service with:

- Amharic-to-English translation using `facebook/nllb-200-distilled-600M`;
- a stable model interface that can load a future fine-tuned adapter;
- typed translation API requests and responses; and
- clearly labeled non-official generated output.

Fine-tuning and accuracy improvement are deferred until the application is working.

### Project 2 — Bilingual search and RAG

Build the bilingual evidence service with:

- import and validation for the existing `id`/`am`/`en` JSONL corpus;
- Amharic and English legal-passage search;
- citation-grounded answers; and
- deterministic abstention when supporting evidence is insufficient.

### Project 3 — Scanned-PDF parallel-corpus builder

Build a workflow where a contributor can:

- upload paired Amharic and English scanned PDFs;
- render them into ordered page images;
- run language-specific OCR;
- review proposed page and passage alignments side by side;
- edit and mark pairs as `accepted`, `review`, or `rejected`; and
- download deterministic UTF-8 JSONL with a SHA-256 manifest.

Original OCR, normalized text, reviewer edits, page references, provenance, and component alignment
scores remain separate. Unreviewed output is never automatically published or indexed.

### Integrated application

Approved corpus-builder exports can be added to Project 2's bilingual index. All three capabilities
share one web application, FastAPI backend, validation rules, storage boundary, and generated-content
labels.

See [PLAN.md](PLAN.md) for the architecture, task dependencies, milestone gates, API contracts, and
today's work checklist. See [REQUIREMENTS.md](REQUIREMENTS.md) for acceptance requirements.

## Technology stack

### Frontend

- React with TypeScript
- Vite
- Tailwind CSS v4
- A typed API client generated from or checked against FastAPI's OpenAPI contract

### Backend

- Python 3.10 or 3.11
- FastAPI for HTTP APIs and OpenAPI
- Pydantic for request, response, and configuration validation
- SQLite for local application records
- FAISS with JSONL metadata for bilingual vector search and citations
- Private local directories for PDFs, page images, OCR artifacts, and exports
- FastAPI background tasks for the first PDF/OCR workflow
- Hugging Face Transformers/PyTorch behind a lazy-loaded translation interface
- Pytest and Ruff for backend verification

PostgreSQL/pgvector, Redis workers, S3-compatible storage, authentication, and public hosting are
later upgrades, not MVP requirements. Model downloads, OCR downloads, GPU operations, and large
processing runs require separate authorization and an environment check.

## Planned repository layout

```text
frontend/       React, TypeScript, Vite, and Tailwind CSS v4 application
configs/        versioned application and model settings
data/           ignored local inputs; processed data, terminology, and manifests
docs/           dataset/model cards, decisions, and operation records
artifacts/      ignored generated adapters, metrics, predictions, and logs
src/api/        FastAPI routes, Pydantic contracts, and safe error handling
src/mt/         model loading and Amharic-to-English translation
src/rag/        indexing, bilingual retrieval, citations, and abstention
src/corpus/     PDF ingestion, OCR, normalization, alignment, review, and export
src/common/     configuration, database, storage, jobs, logging, and manifests
tests/          automated backend and integration checks
scripts/        thin reproducible command entry points
```

Raw/private legal documents, the local JSONL corpus, personal data, secrets, model caches, and full
checkpoints must remain outside Git.

## Current status

**Planning baseline.** The architecture and implementation order are defined. The React frontend,
FastAPI application, translation service, retrieval index, and corpus-processing workflow still need
implementation. No training or accuracy result is claimed.

## Backend setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
python -m pytest
```

Start the backend from the repository root:

```powershell
python -m uvicorn src.api.app:app --reload
```

Set up and start the frontend in a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

The local frontend runs at `http://localhost:5173`; the API health endpoint is
`http://localhost:8000/health`.

Validate a local legacy `id`/`am`/`en` JSONL file without printing its text:

```powershell
python -m scripts.validate_legacy_jsonl "path\to\corpus.jsonl"
```

Runtime settings use the `ELLS_` environment-variable prefix. Copy [.env.example](.env.example) as
a reference, but keep real local paths and secrets out of Git.

## Conversation history and audit

The local backend saves every Translate, Search, or Ask message inside a conversation. All MVP
conversations belong to the fixed `legal_language` category. SQLite stores the message content in
`data/ells.db`, which is ignored by Git.

Audit events are append-only through the API. They record the action, entity ID, message role/type,
content length, and UTC timestamp without duplicating full conversation text.

| Endpoint | Purpose |
| --- | --- |
| `POST /v1/conversations` | Create a saved conversation |
| `GET /v1/conversations` | List conversation history |
| `GET /v1/conversations/{id}` | Read one conversation and all messages |
| `POST /v1/conversations/{id}/messages` | Add a Translate, Search, or Ask message |
| `GET /v1/conversations/{id}/audit` | Read the conversation audit trail |

The MVP intentionally has no delete or audit-edit endpoint. Before public deployment, add user
authentication, ownership checks, a documented retention policy, and an authorized deletion flow.

## Ten things to do today

1. Assign contributors to tasks A0-01 through A0-03 and identify overlapping files.
2. Create a `feature/mt-rag-foundation` branch in a Git-enabled workspace.
3. Scaffold React, TypeScript, Vite, and Tailwind CSS v4 under `frontend/`.
4. Create the FastAPI application and a tested `GET /health` endpoint.
5. Add environment-based settings for API URL, database URL, corpus path, and model ID/revision.
6. Define Pydantic contracts for `/v1/translate`, `/v1/search`, and `/v1/answer`.
7. Add safe synthetic Amharic-English fixtures without copying private corpus rows into Git.
8. Implement a streaming validator for the existing `id`/`am`/`en` JSONL shape.
9. Create Translate, Search, and Ask pages connected to mocked typed API responses.
10. Run backend tests, Ruff, compile checks, and the frontend build; record only actual results.

## Collaboration and completion

- Add or update the relevant [PLAN.md](PLAN.md) row before implementation begins.
- Record the participating student team, affected files, dependencies, status, and acceptance evidence.
- Coordinate before editing files listed by another active task.
- Never push directly to `main`; use a lowercase kebab-case task branch.
- Keep changes focused and require student review for schema, retrieval, model, and legal-safety changes.
- A task is done only when implementation, tests, documentation, and plan evidence agree.

## Git branch flow

Build the MVP through small reviewed branches in this order:

1. `feature/mt-rag-foundation`
2. `feature/translation-service`
3. `feature/bilingual-rag`
4. `feature/corpus-builder`
5. `feature/corpus-rag-integration`
6. `chore/mvp-local-release`

Each branch starts from updated `main`, covers one reviewable task group, uses Conventional Commits,
passes its relevant checks, and merges through student review. Inspect every diff for private corpus
content before merging. Delete the merged branch and create the next branch from the new `main`.
The detailed flow and milestone gates are in [PLAN.md](PLAN.md).

For backend changes, run the narrow relevant tests first and then:

```powershell
python -m pytest
python -m ruff check .
python -m compileall -q src tests
```

Frontend work must also pass the configured lint, test, and production-build commands once the
frontend scaffold defines them.
