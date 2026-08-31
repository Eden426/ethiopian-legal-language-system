# Ethiopian Legal Language System — Coding Standards

These standards translate the research requirements into practical engineering rules for student teams and AI assistants.

## 1. Design principles

- **Research validity first:** reproducibility and leakage prevention take priority over impressive metrics.
- **Traceability:** every derived row and reported output must connect to source metadata, configuration, code revision, and checksums.
- **Legal meaning preservation:** fluency must never hide lost negation, modality, numbers, names, citations, or legal terms.
- **Privacy by default:** raw/private data stays local and outside Git; logs and test fixtures use non-sensitive examples.
- **Resource awareness:** preprocessing supports streaming/chunking, and training respects the declared 6 GB GPU constraint.
- **Bilingual accessibility:** documentation and interfaces must safely render Amharic/Ge'ez and Latin text.

## 2. Project structure

```text
src/corpus/       extraction, normalization, alignment, review, splitting
src/mt/           baseline inference, LoRA training, translation
src/evaluation/   MT, retrieval, RAG, and human-evaluation utilities
src/rag/          indexing, retrieval, citation, and abstention logic
src/api/          typed local API
src/common/       config, logging, seeds, manifests, shared validation
configs/          versioned experiment configuration
scripts/          thin reproducible command entry points
tests/            unit, integration, schema, and leakage tests
docs/             cards, protocols, decisions, and experiment records
```

Do not place business logic in notebooks or shell scripts. Notebooks may explore data, but accepted logic must move into tested modules.

## 3. Python style

- Follow PEP 8 and the Ruff settings in `pyproject.toml`.
- Use four spaces, UTF-8, LF-compatible text, and a maximum line length of 100.
- Name functions/variables `snake_case`, classes `PascalCase`, constants `UPPER_SNAKE_CASE`, and private helpers with a leading underscore.
- Use explicit imports; avoid wildcard imports and import-time side effects.
- Add type hints to public functions and meaningful internal boundaries. Avoid `Any` unless interfacing with an untyped library, and narrow it immediately.
- Prefer small pure functions for normalization, validation, scoring, and metrics.
- Use `pathlib.Path`, context managers, f-strings, and dataclasses or Pydantic models for structured records.
- Return structured results. Do not use magic tuple positions for experiment outputs.
- Raise specific exceptions with context; never use a bare `except` or silently swallow failures.

## 4. Data and schema rules

- Schema field names are lowercase `snake_case` and stable once released.
- IDs must be deterministic or backed by a documented generation rule.
- Preserve `original_*` data separately from normalized or reviewed values.
- Store language using explicit codes such as `amh_Ethi` and `eng_Latn`; do not infer language from a filename alone.
- Represent missing values consistently and validate required fields before processing.
- Read/write text explicitly as UTF-8. CSV exports must use a documented quoting policy; JSONL uses one valid object per line.
- Sort deterministic exports using documented keys before hashing.
- Never log full sensitive text. Log stable IDs, counts, stages, and sanitized error context.

## 5. Configuration and reproducibility

- Hyperparameters, paths, thresholds, language codes, seeds, and model identifiers belong in versioned YAML, not source code.
- Validate configs at startup and reject unknown or incompatible values when practical.
- Reported runs require an immutable model revision, environment/dependency record, Git commit, dataset checksums, config copy, hardware, timestamps, metrics, and output checksums.
- Seed Python, NumPy, PyTorch, data shuffling, and worker processes where applicable. Document remaining nondeterminism.
- Commands must not silently overwrite prior experiment results. Use unique run IDs and fail or require an explicit resume/overwrite option.

## 6. ML implementation

- Model loading, preprocessing, inference, evaluation, and artifact writing must be separable and testable.
- Avoid downloading models during import or unit tests. Mock external model boundaries in fast tests.
- Use batched/streaming processing and bounded memory. Do not load a full corpus when iteration suffices.
- Preserve input IDs through tokenization, batching, generation, and output writing.
- Test that prediction/reference ID sets match exactly before scoring.
- Check device and precision support explicitly. FP16 is valid only on compatible hardware.
- Save adapters and declared artifacts, not unnecessary full base-model copies.

## 7. Retrieval and API rules

- Index only approved records and carry citation metadata through every transformation.
- Keep retrieval ranking separate from answer generation so each can be evaluated independently.
- Define an evidence threshold and deterministic abstention behavior; low evidence must not be converted into a confident answer.
- API inputs and outputs use typed Pydantic models with bounded text lengths and actionable validation errors.
- Do not expose stack traces, local paths, secrets, private text, or internal model prompts through API responses.
- Mark official text, generated translation, and generated answer using explicit fields—not presentation conventions alone.

## 8. Testing standards

- Use Arrange–Act–Assert and descriptive names such as `test_split_rejects_document_overlap`.
- Unit tests must be deterministic, offline, and fast. Mark network, model, GPU, and long-running tests separately.
- Every defect fix includes a regression test when reproducible.
- Corpus tests cover Unicode, empty/malformed data, duplicate IDs, mixed scripts, numeric preservation, and leakage.
- MT tests cover ID preservation, forced target language, batching, output schema, and metric edge cases.
- RAG tests cover citation retention, insufficient evidence, unsupported claims, and bilingual paired evidence.
- Never use private corpus samples as fixtures. Use synthetic, public-domain, or minimally fabricated non-sensitive text clearly labeled as test data.

## 9. Security and dependency standards

- Secrets come from environment variables or ignored local files. Maintain `.env.example` if variables are introduced.
- Validate filenames and paths before file access; do not allow output paths to escape the intended project/artifact directory.
- Treat downloaded documents, serialized Python objects, model artifacts, and user queries as untrusted input.
- Avoid unsafe deserialization such as arbitrary pickle loading. Prefer `safetensors` and validated JSON/YAML.
- Review dependency purpose, license, maintenance, and security impact. Pin exact resolved versions for final reproducibility even when development constraints use ranges.

## 10. Commits and reviews

Use Conventional Commits:

```text
<type>(<scope>): <imperative summary>
```

Common types are `feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `chore`, and `experiment`. Keep summaries lowercase with no trailing period.

A review must prioritize, in order: data/privacy exposure, research leakage, legal-safety failures, correctness, reproducibility, tests, performance/resource use, and maintainability. Use `.claude/agents/code-reviewer.md` as the reusable checklist.

