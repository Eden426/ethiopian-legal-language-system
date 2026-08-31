# Baseline Requirements

## Scope

Version 1 covers an aligned Amharic-English Ethiopian legal corpus, Amharic-to-English NLLB baseline and LoRA adaptation, bilingual retrieval, cited question answering, and reproducible evaluation.

## Required processed fields

```text
id, document_id, law_type, article_id, paragraph_id,
source_language, target_language, source, target,
source_page, target_page, alignment_status, alignment_score, source_type
```

At minimum, `id`, `document_id`, both language fields, `source`, `target`, `alignment_status`, and `source_type` must be populated. Valid source types are `official`, `human_translated`, `synthetic_human_corrected`, and `synthetic_unverified`. Unverified synthetic rows are prohibited from validation and test data.

## Acceptance requirements

- Normalize Unicode and whitespace without changing legal meaning; retain original extracted text.
- Preserve document, title, chapter, article, paragraph, page, language, and provenance metadata where available.
- Score language identity, empty text, duplicates, length ratio, semantic similarity, numbers, dates, article references, and terminology.
- Support `accepted`, `review`, and `rejected` alignment decisions with component scores.
- Split 80/10/10 by `document_id`, with no related or duplicate document leakage.
- Generate SHA-256 manifests for datasets and experiment artifacts.
- Evaluate original NLLB and LoRA on the same frozen test rows.
- Select checkpoints with validation data only.
- Report chrF++, BLEU, terminology accuracy, number/date/money preservation, and legal error categories.
- Support keyword and multilingual dense retrieval and evaluate Recall@k, MRR, and nDCG.
- Cite document, article, and passage identifiers; abstain when evidence is insufficient.
- Record config, seed, Git commit, data checksums, immutable model revision, hardware, dependencies, and results for every reported run.
- Clearly label all generated content as non-official and not legal advice.

## Resource constraints

Development and CPU-sized inference should support an 8 GB RAM workstation. LoRA training targets Ubuntu with an RTX 3060 6 GB GPU, batch size 1, gradient accumulation, FP16, and gradient checkpointing. Out-of-memory mitigation order is: shorten sequence length, retain batch size 1, reduce LoRA rank, reduce evaluation frequency, then investigate quantized loading.

## Out of scope

Training a transformer from scratch, full fine-tuning on 6 GB VRAM, legal outcome prediction, legal advice, and authoritative additional-language translation without human-validated corpora are outside Version 1.

