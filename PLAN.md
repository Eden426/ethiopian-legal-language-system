# Integrated System Plan and Architecture

This file is the shared source of truth for the product architecture, delivery order, and
implementation tasks. Requirements remain in `REQUIREMENTS.md`. The immediate goal is one
integrated web system with three connected capabilities:

1. Amharic-to-English legal-scope machine translation using one selected model;
2. bilingual search and retrieval-augmented answers (RAG); and
3. a scanned-PDF parallel-corpus builder.

Model fine-tuning, accuracy improvement, benchmarking, and other research work are intentionally
deferred. The first delivery priority is a usable combined MT and RAG application. The corpus
builder follows as the second project and feeds improved reviewed data back into the first.

> All generated translations, alignments, and answers are non-official output and are not legal
> advice. A contributor must review automatically extracted or aligned text before it is marked
> accepted.

## 1. Delivery priorities

| Priority | System | First usable outcome | Deferred work |
| --- | --- | --- | --- |
| P0 | MT and bilingual RAG | One web application translates Amharic to English, searches the existing bilingual JSONL, and returns cited evidence or abstains | LoRA training, model comparison, accuracy and ranking tuning |
| P1 | Scanned-PDF corpus builder | A user uploads paired Amharic and English PDFs, reviews extracted and aligned pages/passages, and downloads validated JSONL | advanced layout models, automatic acceptance, large-scale processing |
| P2 | Corpus-to-RAG integration | Approved corpus-builder exports can be added to the search index without changing the MT/RAG API | automatic publication and large-scale indexing |
| P3 | Integrated MVP | One local web application and API serve all three systems | authentication, public hosting, production scaling, and additional languages |

P0 starts with the existing `id`/`am`/`en` JSONL so MT and RAG do not wait for the corpus builder.
P1 then creates richer reviewed records, and P2 connects those records to the existing index.

## 2. Product boundaries

### Included in the first system version

- Upload separate Amharic and English scanned PDFs for the same legal document.
- Validate file type, file size, page count, and safe filenames before processing.
- Convert each PDF into ordered page images without altering the original upload.
- Extract text per page with language-specific OCR settings.
- Preserve original OCR text and store normalized text separately.
- Propose page and passage alignment, with component scores and an explanation.
- Let a contributor edit, accept, reject, or flag each proposed pair for review.
- Export the approved corpus as deterministic UTF-8 JSONL plus a SHA-256 manifest.
- Offer a compatibility JSONL export containing `id`, `am`, and `en` for the current local corpus
  shape.
- Translate Amharic text to English using `facebook/nllb-200-distilled-600M` behind a replaceable
  model adapter.
- Search approved Amharic and English passages and return their document/page/article metadata.
- Generate an answer only from retrieved evidence, cite passage IDs, or abstain.

### Explicitly later

- Fine-tuning or LoRA adapter training and accuracy improvement.
- Choosing a different translation model or comparing multiple models.
- Automatic publication of unreviewed OCR or alignment output.
- Legal advice, official translations, legal outcome prediction, and unsupported citations.
- Additional languages, handwriting recognition, and complex table reconstruction.
- Open public uploads before rate limits, malware scanning, retention rules, and moderation are
  operational.

## 3. Integrated architecture

The MVP is a local modular monolith: a React web application and one FastAPI backend with separate
modules. It uses SQLite, FAISS, JSONL, and private local artifact directories. FastAPI background
tasks are sufficient for the first PDF-processing prototype.

```text
React + Vite + Tailwind CSS v4 web application
  |-- Corpus workspace: upload -> job status -> page viewer -> alignment review -> export
  |-- Translate: Amharic input -> English output
  `-- Search and ask: bilingual query -> evidence -> cited answer or abstention
          |
          v
FastAPI + Pydantic typed Python API
  |-- Upload and document service
  |-- Corpus pipeline service
  |-- Translation service
  |-- Retrieval and answer service
  `-- Export service
          |
          +---------------- FastAPI background tasks ------------------+
          |                                                            |
          v                                                            v
 PDF safety check -> page rendering -> OCR -> normalization -> alignment proposal
                                                                       |
                                                                       v
Storage
  |-- SQLite: records, jobs, reviews, and citations
  |-- Private local directories: PDFs, page images, OCR artifacts, and exports
  |-- FAISS + JSONL metadata: bilingual passage vectors and citation metadata
  `-- Model directory/config: pinned base-model revision and optional future adapter
```

PostgreSQL/pgvector, Redis workers, S3-compatible storage, authentication, and public deployment are
not MVP dependencies. Add them later only when local usage, data size, or multiple users require them.

### Module layout

| Area | Responsibility | Planned location |
| --- | --- | --- |
| Web client | React, Vite, Tailwind CSS v4, upload/review, translation, search | `frontend/` |
| API and job contracts | FastAPI, Pydantic, validation, job status, safe errors | `src/api/` |
| Document ingestion | PDF validation, page rendering, artifact metadata, cleanup | `src/corpus/ingestion/` |
| OCR | Per-page Amharic/English extraction with confidence and engine metadata | `src/corpus/ocr/` |
| Normalization | Non-destructive Unicode/whitespace normalization | `src/corpus/normalization/` |
| Alignment | Page/passage candidate matching and explainable component scores | `src/corpus/alignment/` |
| Review and export | Review state, schema validation, deterministic JSONL and checksums | `src/corpus/export/` |
| Translation | Selected model loader and batched Amharic-to-English inference | `src/mt/` |
| Search and RAG | Keyword/dense index, bilingual retrieval, citations, abstention | `src/rag/` |
| Shared services | Configuration, SQLite, local storage, background tasks, logging, manifests | `src/common/` |
| Reproducible commands | Admin, import, indexing, export, and local startup commands | `scripts/` |

### Main workflow

#### Project 1: MT and bilingual RAG

1. Import and validate the existing `id`/`am`/`en` JSONL without committing private data.
2. Convert valid rows into internal bilingual passage records with stable citation IDs.
3. Index both languages for keyword and bilingual vector retrieval.
4. Translate Amharic input with the selected NLLB model through `POST /v1/translate`.
5. Retrieve ranked evidence for Amharic or English queries through `POST /v1/search`.
6. Return a cited answer only when the configured evidence rule is satisfied; otherwise abstain.

#### Project 2: scanned-PDF parallel-corpus builder

1. The user creates a corpus job and uploads the Amharic and English PDFs.
2. The API stores uploads privately, records checksums, and queues processing.
3. A worker validates and renders the PDFs into page images.
4. OCR produces page-level text while keeping original extracted text unchanged.
5. Normalization creates a separate normalized value for matching and display.
6. Alignment proposes page pairs and passage pairs with individual scores for language identity,
   length ratio, numbers/dates/article references, and text similarity.
7. The reviewer sees both page images and texts side by side, edits if needed, and sets each pair to
   `accepted`, `review`, or `rejected`.
8. Export includes only the requested review states, validates every row, sorts deterministically,
   writes JSONL, and creates its checksum manifest.
9. Accepted passages may be promoted to Project 1's search index. Unreviewed output is never indexed by
   default.
10. Translation can use accepted corpus data later when the separate fine-tuning task begins.

## 4. Data contracts

### Canonical parallel-corpus JSONL row

Each line is one JSON object. Required values are marked with `*`.

```json
{
  "id": "gazette-0001-p003-a01",
  "document_id": "gazette-0001",
  "law_type": "proclamation",
  "title": null,
  "chapter_id": null,
  "article_id": "1",
  "paragraph_id": null,
  "source_language": "amh_Ethi",
  "target_language": "eng_Latn",
  "original_source": "...",
  "original_target": "...",
  "source": "...",
  "target": "...",
  "source_page": 3,
  "target_page": 3,
  "source_type": "official",
  "alignment_status": "accepted",
  "alignment_scores": {
    "language": 1.0,
    "length_ratio": 0.9,
    "numbers_and_dates": 1.0,
    "article_reference": 1.0,
    "text_similarity": 0.87
  },
  "provenance": {
    "source_file_sha256": "...",
    "target_file_sha256": "...",
    "ocr_engine": "...",
    "ocr_engine_version": "...",
    "created_at": "...",
    "reviewed_at": "..."
  }
}
```

The stable identifier, `document_id`, languages, paired text, `source_type`, review status, and
provenance are mandatory in the implemented schema. Original and normalized text remain separate.
The export must never invent missing article or paragraph identifiers; unavailable values are
`null`.

### Compatibility with the current JSONL

The referenced local sample is approximately 7.7 MB and its first record has three fields:
`id` (integer), `am` (string), and `en` (string). No text from it was copied into the repository.
An import adapter will map `am` to `source`, `en` to `target`, and preserve the legacy `id`. Records
without document/provenance metadata enter `review`, not `accepted`. A compatibility exporter may
produce the same three-field shape, but the canonical backend record remains richer.

### Core API contracts

| Endpoint | Purpose | Important response fields |
| --- | --- | --- |
| `POST /v1/corpus/jobs` | Create a paired-document processing job | `job_id`, upload constraints |
| `POST /v1/corpus/jobs/{id}/files` | Upload the two PDFs | file IDs, checksums, validation state |
| `GET /v1/corpus/jobs/{id}` | Read stage, progress, and safe errors | stage, counts, progress, status |
| `GET /v1/corpus/jobs/{id}/alignments` | Page through proposed pairs | images, texts, scores, status |
| `PATCH /v1/corpus/alignments/{id}` | Edit/review one alignment | saved revision and review status |
| `POST /v1/corpus/jobs/{id}/exports` | Build JSONL and manifest | export ID and state |
| `GET /v1/corpus/exports/{id}` | Download authorized output | short-lived download response |
| `POST /v1/translate` | Translate Amharic to English | generated text, model revision, warning |
| `POST /v1/search` | Retrieve bilingual evidence | ranked passages and citations |
| `POST /v1/answer` | Return cited answer or abstain | answer, citations, abstained, warning |
| `POST /v1/conversations` | Create history in the fixed category | conversation ID, category, timestamps |
| `GET /v1/conversations` | List saved conversations | title, category, created/updated timestamps |
| `GET /v1/conversations/{id}` | Read complete ordered conversation history | metadata and messages |
| `POST /v1/conversations/{id}/messages` | Append one conversation message | message ID, role, kind, timestamp |
| `GET /v1/conversations/{id}/audit` | Read content-safe append-only events | action, entity ID, metadata, timestamp |

## 5. Task plan

`Student team` is initially `unassigned`; contributors update it before implementation. `ready`
means the task has enough definition to begin. No implementation task is marked done in this plan.

| ID | Priority | Task | Student team | Files | Depends on | Status | Acceptance evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A0-01 | P0 | Scaffold React, Vite, Tailwind CSS v4, and FastAPI with health checks | student team | `frontend/`, `src/api/`, `tests/` | none | done | Vite started; production build passed; `/health` returned `ok`; 2 Pytest tests passed; scoped Ruff and compile checks passed |
| A0-02 | P0 | Define translation, search, answer, citation, and error contracts | student team | `src/api/`, `src/mt/`, `src/rag/`, `tests/` | A0-01 | done | strict Pydantic contracts and OpenAPI routes tested for validation and safe not-ready responses |
| A0-03 | P0 | Add safe configuration and legacy JSONL import/validation | student team | `src/common/`, `src/rag/`, `scripts/`, `tests/` | A0-02 | done | settings tests passed; malformed/duplicate tests passed; private sample: 19,292/19,292 structurally valid rows |
| A0-04 | P0 | Implement CPU-safe lazy loading for pinned NLLB-200 distilled 600M | unassigned | `src/mt/`, `configs/`, `tests/` | A0-02 | planned | import is offline; authorized smoke test records exact revision |
| A0-05 | P0 | Implement bilingual indexing, search, citations, and abstention | unassigned | `src/rag/`, `src/api/`, `scripts/`, `tests/` | A0-03 | planned | both languages retrieve traceable passages; weak evidence abstains |
| A0-06 | P0 | Build translation and search/answer pages | student team | `frontend/`, `src/api/`, `tests/` | A0-04, A0-05 | in_progress | integrated mock UI handles loading/errors, citations, and warnings; build passed; real model/index connections remain |
| A0-07 | P0 | Persist categorized conversation history and append-only audit events | student team | `src/history/`, `src/api/`, `tests/` | A0-02 | done | SQLite/API tests prove ordered history, fixed `legal_language` category, and content-safe audit records |
| A1-01 | P1 | Confirm canonical corpus schema, review states, and legacy mapping | unassigned | `src/corpus/`, `tests/`, `docs/DATASET_CARD.md` | A0-03 | planned | schema tests validate canonical and legacy rows without private fixtures |
| A1-02 | P1 | Define private local artifact storage, background tasks, retention, and job states | unassigned | `src/common/`, `src/api/`, `configs/`, `tests/` | A1-01 | planned | configuration and state-transition tests pass |
| A1-03 | P1 | Implement safe paired-PDF upload and queued job status API | unassigned | `src/api/`, `src/corpus/ingestion/`, `tests/` | A1-02 | planned | invalid, oversized, malformed, and mismatched inputs fail safely |
| A1-04 | P1 | Render PDFs into ordered page images and record artifact checksums | unassigned | `src/corpus/ingestion/`, `scripts/`, `tests/` | A1-03 | planned | synthetic PDF integration test preserves order and page count |
| A1-05 | P1 | Add replaceable Amharic and English OCR providers | unassigned | `src/corpus/ocr/`, `configs/`, `tests/` | A1-04 | planned | offline provider-contract tests and reviewed public sample smoke test |
| A1-06 | P1 | Implement non-destructive normalization and alignment proposals | unassigned | `src/corpus/normalization/`, `src/corpus/alignment/`, `tests/` | A1-01, A1-05 | planned | Unicode, numeric, duplicate, mixed-script, and ratio tests pass |
| A1-07 | P1 | Build side-by-side page/alignment review workspace | unassigned | `frontend/`, `src/api/`, `tests/` | A1-06 | planned | reviewer can edit and set review status without losing originals |
| A1-08 | P1 | Implement deterministic canonical and legacy JSONL exports | unassigned | `src/corpus/export/`, `src/api/`, `scripts/`, `tests/` | A1-07 | planned | schema, order, row count, UTF-8, and SHA-256 tests pass |
| A2-01 | P2 | Promote accepted corpus exports into the existing bilingual index | unassigned | `src/rag/`, `scripts/`, `tests/` | A0-05, A1-08 | planned | index retains document, page, article, language, and paired IDs |
| A3-01 | P3 | Integrate navigation, job monitoring, errors, and generated-content labels | unassigned | `frontend/`, `src/api/`, `tests/` | A0-06, A1-08, A2-01 | planned | end-to-end local workflow passes with non-sensitive fixtures |
| A3-02 | P3 | Add local startup commands, cleanup, backup, and restore instructions | unassigned | `scripts/`, `src/common/`, `docs/` | A3-01 | planned | clean local startup and restore checklist pass |
| L1-01 | Later | Fine-tune the selected MT model and improve accuracy | unassigned | `src/mt/`, `src/evaluation/`, `configs/`, `scripts/`, `docs/` | A0-04, A1-08 | deferred | separate reviewed training plan and authorized environment check |

## 6. Milestone gates

### Gate P0 — MT and bilingual RAG usable

- React/Vite/Tailwind and FastAPI run together in local development.
- One configured, pinned model revision serves Amharic-to-English translation.
- Existing bilingual JSONL records are validated and indexed without entering Git.
- Amharic and English queries return traceable passage citations.
- Generated answers cite retrieved evidence or explicitly abstain.
- Generated output is visibly labeled non-official.

### Gate P1 — Corpus builder usable

- Paired PDFs can be uploaded and processed as resumable background jobs.
- The user can trace every text segment back to a file checksum and page image.
- Original OCR and normalized/reviewed text are distinct.
- A human review is required before an alignment becomes accepted.
- Canonical JSONL validates, exports deterministically, and includes a checksum manifest.
- The legacy `id`/`am`/`en` import and export path works without discarding the canonical record.
- Private uploads and full extracted text do not appear in logs or Git.

### Gate P2 — Corpus-to-RAG integration usable

- Only approved records enter the index.
- Results retain bilingual pairing and document/page/article/passage citations.
- Retrieval and answer generation remain separate operations.
- An answer cites retrieved passages or explicitly abstains.

### Gate P3 — Integrated local MVP complete

- All three capabilities share one local application and consistent API errors.
- Upload limits, retention, deletion, backup, and restore are tested.
- A local clean setup runs the full workflow using non-sensitive fixtures.
- Public hosting remains out of scope until authentication, rate limits, malware scanning, privacy,
  and security review are completed.

## 7. Decisions required before affected tasks begin

These are implementation decisions, not blockers for the overall plan:

- Choose the first OCR engine after a small Amharic/English page-quality and local-resource check.
- Define the SQLite migration approach before persistent records are added.
- Define the private local artifact directory and cleanup policy.
- Define maximum PDF size/page count, job retention, and who may view or delete an upload.
- Confirm whether the two languages always arrive as separate PDFs; mixed bilingual PDFs require a
  separate ingestion path.
- Pin an immutable NLLB model revision before A0-04's model smoke test.

## 8. Ten things to do today

1. **Done:** Assign student-team contributors to A0-01 through A0-03 and record file overlap.
2. **Done:** Create a `feature/mt-rag-foundation` branch in a Git-enabled workspace.
3. **Done:** Scaffold `frontend/` with React, TypeScript, Vite, and Tailwind CSS v4.
4. **Done:** Add FastAPI application startup and `GET /health` under `src/api/`.
5. **Done:** Add environment-based settings for API URL, model ID/revision, data path, and database URL.
6. **Done:** Define Pydantic contracts for `/v1/translate`, `/v1/search`, and `/v1/answer`.
7. **Done:** Create safe synthetic Amharic/English fixtures; no private JSONL rows were copied into Git.
8. **Done:** Implement a streaming validator for the existing `id`/`am`/`en` JSONL shape.
9. **Done:** Create integrated Translate, Search, and Ask screens wired to clearly labeled mock APIs.
10. Run tests, Ruff, compile checks, and the frontend build; record actual results in the plan.

## 9. Git branch flow for the MVP

Use `main` only for reviewed, working milestones. Do not implement the entire MVP on one branch.

```text
main
  `-- feature/mt-rag-foundation
        |-- merge through reviewed pull request
        v
      main
  `-- feature/bilingual-rag
        |-- merge through reviewed pull request
        v
      main
  `-- feature/corpus-builder
        |-- merge through reviewed pull request
        v
      main
  `-- feature/corpus-rag-integration
        `-- merge through reviewed pull request -> MVP tag
```

Branch rules:

1. Update local `main` before starting a task branch.
2. Use one branch for one reviewable plan task or tightly connected task group.
3. Use `feature/<topic>`, `fix/<topic>`, `docs/<topic>`, or `chore/<topic>`.
4. Commit small working units with Conventional Commits such as
   `feat(api): add translation request contract`.
5. Run relevant checks and inspect the diff for private corpus data before opening a pull request.
6. Merge only after another student contributor reviews the files and acceptance evidence.
7. Delete the merged branch; start the next branch from the updated `main`.
8. Use `fix/<topic>` from `main` for defects; do not continue unrelated work on an old branch.
9. Tag the integrated local MVP only after P0–P3 gates pass.

Recommended branch sequence:

1. `feature/mt-rag-foundation` — frontend, FastAPI health check, contracts, settings, fixtures.
2. `feature/translation-service` — selected NLLB loader, translation endpoint, Translate page.
3. `feature/bilingual-rag` — JSONL validation, FAISS index, search, citations, abstention, UI.
4. `feature/corpus-builder` — PDF rendering, OCR, alignment review, JSONL export.
5. `feature/corpus-rag-integration` — add accepted exports to the FAISS index.
6. `chore/mvp-local-release` — startup scripts, documentation, backup/restore, final checks.

## 10. Verification order

For each implementation task, run the narrow tests first and then the relevant repository checks:

```powershell
python -m pytest
python -m ruff check .
python -m compileall -q src tests
```

Corpus changes additionally verify schema validation, deterministic row order, row counts, Unicode,
checksums, duplicate IDs, and no document overlap where splits are created. Model downloads, OCR
downloads, GPU work, and large processing runs require separate authorization and an environment
check. Documentation-only changes require a link, encoding, terminology, and consistency review.
