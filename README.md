# Ethiopian Legal Language System

One integrated system with three connected parts:

1. Amharic-to-English legal-scope machine translation using one selected model;
2. bilingual search and retrieval-augmented answers (RAG); and
3. a scanned-PDF parallel-corpus builder.

> Translations, alignments, and generated answers are non-official output and are not legal advice.
> Answers must cite supporting passages or abstain.

## Delivery order

The system numbering describes the three final capabilities. The implementation order is different:

1. **Build Project 3 first:** finish the scanned-PDF parallel-corpus builder and produce a reviewed,
   validated dataset.
2. **Build Project 1 second:** connect the selected translation model and later fine-tune it using
   an approved dataset version.
3. **Build Project 2 third:** index only approved bilingual passages for search and cited answers.

This corpus-first order prevents the translation and retrieval systems from depending on an
unfinished or untraceable dataset.

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

## Current implementation priority: Project 3

The student team should finish the corpus builder through small reviewed branches:

1. `feature/corpus-schema` — canonical row schema, source inventory, legacy import, validation.
2. `feature/pdf-ingestion` — safe paired-PDF upload, checksums, and ordered page rendering.
3. `feature/bilingual-ocr` — replaceable Amharic and English OCR providers and page metadata.
4. `feature/page-alignment` — normalization and explainable page/passage alignment proposals.
5. `feature/alignment-review` — side-by-side review, correction, and review status workflow.
6. `feature/corpus-splits-export` — deterministic document-level splits, JSONL compatibility export,
   leakage checks, and SHA-256 manifests.

Do not begin with real private PDFs. Build and test each stage using synthetic or clearly public
fixtures. The local corpus and uploaded documents remain outside Git.

See [PLAN.md](PLAN.md) for the architecture, task dependencies, milestone gates, API contracts, and
Project 3 completion checklist. See [REQUIREMENTS.md](REQUIREMENTS.md) for acceptance requirements.

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

**Corpus schema, paired-PDF upload, ordered page rendering, and bilingual OCR implemented.** The
React/Vite application shell, FastAPI typed contracts, safe configuration, legacy JSONL migration,
local conversation history, stable IDs, private storage, rendering checksums, and replaceable
Amharic/English OCR are implemented. A contributor can select `proclamation` or `book`, upload
the two language PDFs, and monitor rendering and OCR. Normalization, alignment review, export,
translation model loading, and a production retrieval index are not yet implemented. No dataset,
training, OCR-accuracy, or translation-accuracy result is claimed.

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

## Parallel-corpus upload

Open the **Corpus** workspace, choose **Proclamation** or **Book**, and select the matching Amharic
and English PDFs. The API validates the filename, PDF media type and signature, readable page count,
configured size/page limits, and that the two language files are not identical. Accepted files are
stored under the ignored private artifact root with SHA-256 metadata in local SQLite. The upload
queues a FastAPI background task that renders one page at a time into ordered PNG files, records
each page's language, dimensions, byte count, and SHA-256 checksum, and updates content-safe
`stage`, `progress`, and `error_code` fields. File content and local paths are not returned by
the API, and a rendering failure removes partial page images without changing the original PDFs.

The configurable per-file defaults are 50 MiB and 500 pages:

```text
ELLS_ARTIFACT_ROOT=data/artifacts
ELLS_ARTIFACT_RETENTION_DAYS=30
ELLS_MAX_PDF_BYTES=52428800
ELLS_MAX_PDF_PAGES=500
ELLS_PDF_RENDER_DPI=200
ELLS_OCR_CONFIG=configs/ocr.yaml
```

Page rendering uses `pdf2image` and requires Poppler's `pdfinfo` and `pdftoppm` commands.
If they are not on `PATH`, set `ELLS_POPPLER_PATH` to Poppler's binary directory. The DPI must
be between 72 and 600. FastAPI background tasks are suitable for this local prototype but are not
a durable production queue: a process restart can interrupt active work.

OCR uses the versioned `configs/ocr.yaml` settings and a replaceable provider interface. The
default provider is local Tesseract and requires both the `amh` and `eng` language packs. It
processes one page at a time and stores exact UTF-8 provider output under the ignored private
artifact root. SQLite records the source-page checksum, output checksum, byte/character counts,
mean word confidence, language, and engine version. OCR output remains unreviewed research data;
it is neither normalized nor accepted automatically.

The upload endpoints are:

| Endpoint | Purpose |
| --- | --- |
| `POST /v1/corpus/jobs` | Create a `proclamation` or `book` job and return upload limits |
| `POST /v1/corpus/jobs/{id}/files` | Store the paired PDFs and queue bounded page rendering |
| `GET /v1/corpus/jobs/{id}` | Read stage, progress, safe errors, and file/page/OCR metadata |

Supabase is not required for the local MVP. SQLite and private local files remain the planned
storage boundary until authentication, public hosting, or multi-user access is approved.

Validate a local legacy `id`/`am`/`en` JSONL file without printing its text:

```powershell
python -m scripts.validate_legacy_jsonl "path\to\corpus.jsonl"
```

The canonical contract lives in `src/corpus/schema.py`. Legacy migration requires an explicit
`law_type`, `source_type`, and fixed timezone-aware creation timestamp. Missing document metadata is
marked `unresolved_legacy`, and every migrated row remains in `review`.

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

## What to do next

1. Review the stacked `feature/pdf-ingestion` and `feature/bilingual-ocr` changes, including
   private artifact handling, exact Unicode preservation, and safe failure behavior.
2. Run a student-reviewed smoke check on a clearly public bilingual legal sample and record its
   provenance without committing the document or treating the OCR as accepted.
3. Merge reviewed branches in dependency order, then begin A1-06 non-destructive normalization and
   explainable alignment proposals.

The complete Project 3 checklist is in [PLAN.md](PLAN.md#8-how-to-finish-project-3).

## Collaboration and completion

- Add or update the relevant [PLAN.md](PLAN.md) row before implementation begins.
- Record the participating student team, affected files, dependencies, status, and acceptance evidence.
- Coordinate before editing files listed by another active task.
- Never push directly to `main`; use a lowercase kebab-case task branch.
- Keep changes focused and require student review for schema, retrieval, model, and legal-safety changes.
- A task is done only when implementation, tests, documentation, and plan evidence agree.

## Git branch flow

Build the MVP through small reviewed branches in this order:

1. `feature/corpus-schema`
2. `feature/pdf-ingestion`
3. `feature/bilingual-ocr`
4. `feature/page-alignment`
5. `feature/alignment-review`
6. `feature/corpus-splits-export`
7. `feature/translation-service`
8. `feature/bilingual-rag`
9. `chore/mvp-local-release`

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
