# Ethiopian Legal Language System — Agentic Rules

This file is the repository-wide source of truth for AI coding assistants. It applies to Codex, Claude Code, Gemini, Cursor, Copilot, and similar tools. Tool-specific instruction files should point here instead of duplicating these rules.

The repository is a school-team research project. Files, datasets, plans, and results are shared project resources. Describe participation using terms such as **student team**, **task**, **reviewer**, and **contributor**.

## 1. Mission and conduct

- Build a reproducible Amharic-to-English Ethiopian legal-language research system following `README.md`, `PLAN.md`, and `REQUIREMENTS.md`.
- Communicate clearly and concisely. Separate verified facts, assumptions, open questions, and recommendations.
- Do not invent corpus sources, citations, legal translations, evaluation results, model performance, or completed work.
- Treat generated translations and answers as non-official research output, never legal advice.
- Preserve Amharic/Ge'ez Unicode accurately. Never repair encoding by guessing or by silently deleting characters.
- Prefer the smallest change that satisfies the current task and acceptance requirement.

## 2. Instruction and planning order

Before changing code:

1. Read this file and `coding_standards.md`.
2. Read the relevant requirements and milestone in `PLAN.md`.
3. Inspect the current implementation, tests, configuration, and working-tree state.
4. State assumptions when the repository cannot answer an important question.
5. Add or update the applicable plan row when implementation work begins.

Do not copy rules into tool-specific files. Reusable reviewer behavior belongs in `.claude/agents/` or an equivalent thin integration, while project policy stays here.

## 3. School-team collaboration

- All project files are shared. Planning a change identifies possible overlap so teams can coordinate.
- A plan row records the participating student team, affected files, dependencies, status, and acceptance evidence.
- Before editing a file listed by another active task, coordinate through the shared task or pull request.
- Do not overwrite or discard another contributor's uncommitted work.
- Keep changes focused. Separate corpus schema, training, retrieval, API, and documentation changes when they can be reviewed independently.
- Decisions affecting research validity—splits, metrics, filtering thresholds, model choice, or legal evaluation—require documented team review.
- AI assistance must be reviewable by students. Agents may propose and implement work, but must report assumptions, tests, limitations, and unresolved risks.

## 4. Git and review workflow

- Never push directly to `main` unless the school team explicitly establishes a different workflow.
- Use lowercase kebab-case branches: `feature/<topic>`, `fix/<topic>`, `experiment/<run-id>`, `docs/<topic>`, or `chore/<topic>`.
- Use the logged-in student's Git identity. Never invent or substitute an agent identity.
- Make atomic commits using Conventional Commits, for example `feat(corpus): add document-level split validation`.
- Before proposing a commit or pull request, inspect the diff and staged files for private data, secrets, model binaries, generated outputs, and accidental corpus content.
- Run checks appropriate to the change. Documentation-only changes need link/encoding/consistency review; Python changes require tests and linting; experiment changes require configuration and manifest validation.
- Review findings must cite the file, location, failure scenario, and applicable requirement. Fix critical findings before merge.
- Do not claim CI, GPU, model, or end-to-end results that were not actually run.

## 5. Data governance and research integrity

- Never commit raw/private legal documents, confidential case data, personally identifiable information, access tokens, private links, model caches, or full checkpoints.
- Preserve source provenance, licensing/distribution restrictions, original extracted text, and transformation history.
- Split by `document_id`, not by sentence. Check duplicate, amended, or closely related documents for leakage across splits.
- Freeze validation/test data before model selection. Never tune filtering, prompts, checkpoints, or hyperparameters using test results.
- `synthetic_unverified` data must never enter validation or test sets and must remain identifiable in training data.
- A correction to frozen data creates a new dataset version and new checksum manifest; it does not silently replace the old set.
- Report negative and null results honestly. Never remove inconvenient examples or metrics without a documented, reproducible reason.
- Human evaluation instructions, sampling, anonymized ratings, and adjudication rules must be retained.

## 6. Python, configuration, and dependencies

- Target the supported Python range in `pyproject.toml`; write cross-platform paths with `pathlib`.
- Keep reusable logic in `src/`, command entry points in `scripts/`, configuration in `configs/`, and automated checks in `tests/`.
- Do not hard-code local absolute paths, secrets, device IDs, dataset locations, model revisions, thresholds, or experiment hyperparameters.
- Validate external inputs and configuration early with actionable errors.
- Use type hints for public functions and concise docstrings for behavior that is not obvious from the signature.
- Pin an immutable model revision and record dependency versions for reported experiments.
- Add a dependency only when the standard library and existing dependencies cannot reasonably satisfy the requirement. Explain heavyweight ML dependencies.
- Ensure CPU-safe imports where possible; importing a utility module must not download a model or initialize a GPU.

## 7. Corpus and language processing

- Normalize Unicode intentionally and test Amharic/Ge'ez examples. Preserve both original and normalized values.
- Never use destructive normalization that can erase punctuation, numerals, article identifiers, names, negation, or modality.
- Every accepted aligned row must have a stable ID, provenance, language codes, paired text, and an explainable review status.
- Quality decisions must retain component scores and thresholds; avoid an unexplained single opaque score.
- Dataset exports must be deterministic, schema-validated, and checksummed.
- Tests must include empty text, mixed scripts, malformed rows, duplicates, extreme length ratios, and document leakage.

## 8. Models, retrieval, and evaluation

- Compare the untouched NLLB baseline and LoRA adapter on identical frozen test IDs.
- Select checkpoints using validation data only and record seed, config, Git commit, dataset checksums, model revision, hardware, and runtime.
- Evaluate legal meaning in addition to general fluency: negation, omission, addition, modality, article numbers, dates, monetary values, named parties, and terminology.
- Retrieval records must retain document, article, paragraph, language, and aligned-passage identifiers.
- A generated answer must cite supporting indexed passages or abstain. It must not fabricate a citation.
- Keep official source text visibly distinct from generated translation, summaries, or answers.
- Treat metrics as evidence with limitations, not proof of legal correctness.

## 9. Verification expectations

Run the smallest meaningful set first, then the broader relevant suite:

```powershell
python -m pytest
python -m ruff check .
python -m compileall -q src tests
```

For data or experiment changes, also validate schemas, split isolation, checksums, configuration loading, output row counts, and ID correspondence. GPU training and large downloads are separate operations and require clear authorization and an environment check.

## 10. Completion report

When handing work back to the school team, report:

- what changed and why;
- files affected;
- checks actually run and their results;
- data/model/privacy implications;
- assumptions and unresolved limitations; and
- the next plan item, if relevant.

Never hide a failed or skipped check. A task is complete only when implementation, tests, documentation, and plan evidence agree.
