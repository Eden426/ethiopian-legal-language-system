# Integrated System Plan and Architecture

This file is the shared source of truth for the product architecture, delivery order, and
implementation tasks. Requirements remain in `REQUIREMENTS.md`. The immediate goal is one
integrated web system with three connected capabilities:

1. Amharic-to-English legal-scope machine translation using one selected model;
2. bilingual search and retrieval-augmented answers (RAG); and
3. a scanned-PDF parallel-corpus builder.

Model fine-tuning, accuracy improvement, benchmarking, and other research work are intentionally
deferred. The first delivery priority is Project 3, the scanned-PDF parallel-corpus builder. Its
reviewed, validated output will feed Project 1 translation work and Project 2 bilingual RAG.

> All generated translations, alignments, and answers are non-official output and are not legal
> advice. A contributor must review automatically extracted or aligned text before it is marked
> accepted.

## 1. Delivery priorities

| Priority | System | First usable outcome | Deferred work |
| --- | --- | --- | --- |
| P0 | Project 3: scanned-PDF corpus builder | A user uploads paired Amharic and English PDFs, reviews extracted and aligned pages/passages, and downloads validated JSONL | advanced layout models, automatic acceptance, large-scale processing |
| P1 | Project 1: machine translation | The application translates Amharic to English through the selected base model and can later load an adapter | LoRA training, model comparison, accuracy tuning |
| P2 | Project 2: bilingual retrieval and RAG | Approved bilingual passages support search, citations, and answers that abstain when evidence is weak | ranking optimization and large-scale indexing |
| P3 | Integrated MVP | One local web application and API serve all three systems | authentication, public hosting, production scaling, and additional languages |

P0 is now the critical path. The existing `id`/`am`/`en` JSONL is an input to validate and migrate,
not an automatically accepted final dataset. P1 and P2 begin only after a versioned P0 export passes
schema, review-status, row-count, checksum, and document-leakage checks.

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

#### Project 3 first: scanned-PDF parallel-corpus builder

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
9. Accepted passages may be promoted to Project 2's search index. Unreviewed output is never indexed by
   default.
10. Translation can use accepted corpus data later when the separate fine-tuning task begins.

#### Project 1 second: machine translation

1. Load only an explicitly selected and pinned NLLB model revision.
2. Translate Amharic input through `POST /v1/translate` while preserving request IDs.
3. Label generated output as non-official and record the exact model revision.
4. Keep the base-model interface compatible with a future adapter.

#### Project 2 third: bilingual retrieval and RAG

1. Import only accepted, versioned corpus-builder records with stable citation IDs.
2. Index both languages for keyword and bilingual vector retrieval.
3. Retrieve ranked evidence for Amharic or English queries through `POST /v1/search`.
4. Return a cited answer only when the configured evidence rule is satisfied; otherwise abstain.

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
means the task has enough definition to begin. Foundation tasks marked `done` retain their recorded
acceptance evidence; all corpus-builder, model, retrieval, and integration tasks remain gated by
their listed dependencies.

| ID | Priority | Task | Student team | Files | Depends on | Status | Acceptance evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A0-01 | Foundation | Scaffold React, Vite, Tailwind CSS v4, and FastAPI with health checks | student team | `frontend/`, `src/api/`, `tests/` | none | done | Vite started; production build passed; `/health` returned `ok`; 2 Pytest tests passed; scoped Ruff and compile checks passed |
| A0-02 | Foundation | Define translation, search, answer, citation, and error contracts | student team | `src/api/`, `src/mt/`, `src/rag/`, `tests/` | A0-01 | done | strict Pydantic contracts and OpenAPI routes tested for validation and safe not-ready responses |
| A0-03 | Foundation | Add safe configuration and legacy JSONL import/validation | student team | `src/common/`, `src/rag/`, `scripts/`, `tests/` | A0-02 | done | settings tests passed; malformed/duplicate tests passed; private sample: 19,292/19,292 structurally valid rows |
| A0-04 | P1 | Implement CPU-safe lazy loading for pinned NLLB-200 distilled 600M | unassigned | `src/mt/`, `configs/`, `tests/` | A1-08, A0-02 | deferred | import is offline; authorized smoke test records exact revision |
| A0-05 | P2 | Implement bilingual indexing, search, citations, and abstention | unassigned | `src/rag/`, `src/api/`, `scripts/`, `tests/` | A1-08 | deferred | both languages retrieve traceable passages; weak evidence abstains |
| A0-06 | P3 | Connect translation and search/answer pages | student team | `frontend/`, `src/api/`, `tests/` | A0-04, A0-05 | deferred | integrated mock UI exists; real model/index connections wait for approved corpus export |
| A0-07 | P3 | Persist categorized conversation history and append-only audit events | student team | `src/history/`, `src/api/`, `tests/` | A0-02 | done | SQLite/API tests prove ordered history, fixed `legal_language` category, and content-safe audit records |
| A1-01 | P0 | Confirm canonical corpus schema, review states, and legacy mapping | student team | `src/corpus/`, `tests/`, `docs/DATASET_CARD.md` | A0-03 | ready | schema tests validate canonical and legacy rows without private fixtures |
| A1-02 | P0 | Define private local artifact storage, background tasks, retention, and job states | unassigned | `src/common/`, `src/api/`, `configs/`, `tests/` | A1-01 | planned | configuration and state-transition tests pass |
| A1-03 | P0 | Implement safe paired-PDF upload and queued job status API | unassigned | `src/api/`, `src/corpus/ingestion/`, `tests/` | A1-02 | planned | invalid, oversized, malformed, and mismatched inputs fail safely |
| A1-04 | P0 | Render PDFs into ordered page images and record artifact checksums | unassigned | `src/corpus/ingestion/`, `scripts/`, `tests/` | A1-03 | planned | synthetic PDF integration test preserves order and page count |
| A1-05 | P0 | Add replaceable Amharic and English OCR providers | unassigned | `src/corpus/ocr/`, `configs/`, `tests/` | A1-04 | planned | offline provider-contract tests and reviewed public sample smoke test |
| A1-06 | P0 | Implement non-destructive normalization and alignment proposals | unassigned | `src/corpus/normalization/`, `src/corpus/alignment/`, `tests/` | A1-01, A1-05 | planned | Unicode, numeric, duplicate, mixed-script, and ratio tests pass |
| A1-07 | P0 | Build side-by-side page/alignment review workspace | unassigned | `frontend/`, `src/api/`, `tests/` | A1-06 | planned | reviewer can edit and set review status without losing originals |
| A1-08 | P0 | Implement deterministic corpus splits plus canonical and legacy JSONL exports | unassigned | `src/corpus/splitting/`, `src/corpus/export/`, `src/api/`, `scripts/`, `tests/` | A1-07 | planned | deterministic 80/10/10 document-level splits pass schema, isolation, related/duplicate leakage, review-state, row-count, ID-correspondence, UTF-8, and SHA-256 checks |
| A2-01 | P2 | Promote accepted corpus exports into the existing bilingual index | unassigned | `src/rag/`, `scripts/`, `tests/` | A0-05, A1-08 | planned | index retains document, page, article, language, and paired IDs |
| A3-01 | P3 | Integrate navigation, job monitoring, errors, and generated-content labels | unassigned | `frontend/`, `src/api/`, `tests/` | A0-06, A1-08, A2-01 | planned | end-to-end local workflow passes with non-sensitive fixtures |
| A3-02 | P3 | Add local startup commands, cleanup, backup, and restore instructions | unassigned | `scripts/`, `src/common/`, `docs/` | A3-01 | planned | clean local startup and restore checklist pass |
| L1-01 | Later | Fine-tune the selected MT model and improve accuracy | unassigned | `src/mt/`, `src/evaluation/`, `configs/`, `scripts/`, `docs/` | A0-04, A1-08 | deferred | separate reviewed training plan and authorized environment check |

## 6. Milestone gates

### Gate P0 — Project 3 corpus builder complete

- Paired PDFs can be uploaded and processed as resumable background jobs.
- The user can trace every text segment back to a file checksum and page image.
- Original OCR and normalized/reviewed text are distinct.
- A human review is required before an alignment becomes accepted.
- Canonical JSONL validates, exports deterministically, and includes a checksum manifest.
- Train, validation, and test exports use a deterministic 80/10/10 split by `document_id`, with no
  duplicate, amended, or closely related document leakage across splits.
- `synthetic_unverified` records remain identifiable in training data and never enter validation or
  test exports.
- The legacy `id`/`am`/`en` import and export path works without discarding the canonical record.
- Private uploads and full extracted text do not appear in logs or Git.

### Gate P1 — Project 1 translation usable

- One configured, pinned model revision serves Amharic-to-English translation.
- Model loading is lazy and does not download or initialize a GPU during import.
- Output identifies the model revision and is visibly labeled generated and non-official.
- The base model can later load a fine-tuned adapter without breaking the API.

### Gate P2 — Project 2 bilingual RAG usable

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

## 8. How to finish Project 3

Follow this order; do not combine all corpus work into one pull request.

1. Merge the current foundation/documentation branch into `main` after student review.
2. Create `feature/corpus-schema` from updated `main` and assign A1-01.
3. Define the canonical Pydantic schema, deterministic ID rule, review states, provenance fields, and
   safe legacy `id`/`am`/`en` migration.
4. Validate the existing local JSONL and produce counts/errors only; do not commit its text.
5. Create `feature/pdf-ingestion` and implement PDF validation, paired-document metadata, checksums,
   page rendering, and private artifact paths.
6. Create `feature/bilingual-ocr` and implement replaceable Amharic/English OCR contracts, confidence,
   engine version, and original page text preservation.
7. Create `feature/page-alignment` and implement non-destructive normalization plus page/passage
   proposals with separate language, ratio, numeric, article-reference, and similarity scores.
8. Calibrate thresholds with student review; automatic proposals must start as `review`, not
   `accepted`.
9. Create `feature/alignment-review` and implement side-by-side images/text, corrections, reviewer
   state, and revision history.
10. Create `feature/corpus-splits-export` and implement deterministic 80/10/10 splitting by
    `document_id`, canonical JSONL, legacy compatibility JSONL, schema validation, row counts, sorted
    IDs, and SHA-256 manifests.
11. Verify duplicate IDs, Unicode preservation, empty/malformed rows, extreme ratios, document and
    related-document isolation, `synthetic_unverified` exclusion from validation/test, checksum
    reproducibility, and export/import ID correspondence.
12. Version the approved dataset, update `docs/DATASET_CARD.md`, record limitations, and merge only
    after another student contributor reviews schema, privacy, and acceptance evidence.

## 9. Git branch flow for the MVP

Use `main` only for reviewed, working milestones. Do not implement the entire MVP on one branch.

```text
main
  `-- feature/corpus-schema
        |-- merge through reviewed pull request
        v
      main
  `-- feature/pdf-ingestion
        |-- merge through reviewed pull request
        v
      main
  `-- feature/bilingual-ocr
        |-- merge through reviewed pull request
        v
      main
  `-- feature/page-alignment
        |-- merge through reviewed pull request
        v
      main
  `-- feature/alignment-review
        |-- merge through reviewed pull request
        v
      main
  `-- feature/corpus-splits-export
        `-- merge through reviewed pull request -> Project 3 dataset version
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

1. `feature/corpus-schema` — schema, IDs, provenance, review states, legacy migration.
2. `feature/pdf-ingestion` — upload validation, checksums, storage, and page rendering.
3. `feature/bilingual-ocr` — OCR provider boundary, page text, confidence, engine metadata.
4. `feature/page-alignment` — normalization, proposals, component scores, thresholds.
5. `feature/alignment-review` — side-by-side review, edits, decisions, revision history.
6. `feature/corpus-splits-export` — deterministic document-level splits, JSONL compatibility export,
   leakage checks, checksums, and dataset card.
7. `feature/translation-service` — begin Project 1 only after the Project 3 gate passes.
8. `feature/bilingual-rag` — begin Project 2 using accepted versioned corpus records.

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
