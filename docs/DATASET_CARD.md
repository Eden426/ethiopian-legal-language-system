# Dataset Card — Draft Canonical Contract

## Status

Schema version: `1.0-draft`.

No corpus version is released or approved yet. No source document, legal translation, license,
distribution permission, dataset statistic, alignment threshold, or quality result is claimed by
this draft. The student team must review those items before any dataset release.

## Intended use

The canonical contract represents reviewed Amharic-to-English parallel passages derived from a
paired proclamation or bilingual legal book. It is research data for the Ethiopian Legal Language
System and is not an official translation or legal advice.

## Required record structure

Every row uses a stable `id` and `document_id`, explicit `amh_Ethi` and `eng_Latn` language codes,
original and working text values, source type, review state, explainable alignment components, and
provenance. Optional title, chapter, article, paragraph, and page values remain `null` when they are
not available; the importer does not invent them.

The implemented source types are:

- `official`;
- `human_translated`;
- `synthetic_human_corrected`; and
- `synthetic_unverified`.

The implemented review states are `review`, `accepted`, and `rejected`.

## Acceptance rules

A row cannot become `accepted` unless:

- document metadata is resolved;
- all five alignment components are present: language identity, length ratio, numbers/dates,
  article references, and text similarity;
- a timezone-aware review timestamp and reviewer ID are recorded; and
- its source type is not `synthetic_unverified`.

Accepted and rejected rows require human-review provenance. Automatically generated proposals and
legacy imports start in `review`.

## Stable identifiers

Uploaded paired documents receive a deterministic identifier derived from the legal-source type and
the two original file SHA-256 checksums. Alignment IDs use that document ID plus source page, target
page, and within-page sequence. Text edits therefore do not silently change the alignment ID.

Legacy row IDs are preserved in `legacy_id`. Their canonical IDs are deterministic hashes of the
legacy corpus checksum, original ID type, and original ID value.

## Legacy `id`/`am`/`en` migration

The migration adapter copies `am` and `en` exactly into both original and working text fields. It
records the legacy file checksum and line number, leaves unavailable page and score fields null, and
sets the row to `review`.

If no reviewed `document_id` is supplied, all rows from that legacy file receive one visibly
unresolved document ID and `metadata_status=unresolved_legacy`. This deliberately prevents treating
sentence IDs as independent documents and prevents acceptance before document provenance is
reconstructed. The contributor must explicitly supply `law_type` and `source_type`; the adapter does
not guess them.

## Source inventory and licensing

No source is approved in this draft. Before adding a proclamation or book, record its title,
publishing authority or contributor, document identifier, language edition, acquisition location,
license or distribution restriction, file checksum, and whether the text is official or generated.
Private links and raw/private documents must remain outside Git.

## Privacy and governance

Raw PDFs and extracted text remain in ignored private local storage. Tests use only fabricated,
non-sensitive Amharic-English examples. Validation errors identify rows by stable ID or line number
and do not include document text.

Validation and test partitions will be frozen only after document provenance and related-document
grouping are reviewed. `synthetic_unverified` rows must remain identifiable and will be prohibited
from validation and test exports by A1-08.

## Known limitations and next work

- The schema supports the MVP's `proclamation` and `book` choices only.
- No OCR engine, normalization rule, alignment threshold, or terminology list is approved yet.
- The legacy corpus lacks verified document-level provenance until the student team reconstructs it.
- Page rendering, OCR, alignment review, deterministic splitting, exports, statistics, checksums,
  bias review, and release history remain pending in A1-04 through A1-08.
