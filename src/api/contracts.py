"""Typed public contracts for translation, search, and cited answers."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

NON_OFFICIAL_WARNING = "Generated output is non-official and is not legal advice."


class ApiModel(BaseModel):
    """Strict base model for public API payloads."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)


class ErrorDetail(ApiModel):
    """Safe error payload that does not expose internal paths or stack traces."""

    code: str
    message: str


class ErrorResponse(ApiModel):
    """Envelope for a public API error."""

    detail: ErrorDetail


class Citation(ApiModel):
    """Traceable bilingual-passage citation."""

    passage_id: str
    document_id: str | None = None
    article_id: str | None = None
    page: int | None = Field(default=None, ge=1)
    language: Literal["amh_Ethi", "eng_Latn"]
    excerpt: str = Field(min_length=1, max_length=500)


class TranslationRequest(ApiModel):
    """Amharic-to-English translation request."""

    text: str = Field(min_length=1, max_length=5_000)
    source_language: Literal["amh_Ethi"] = "amh_Ethi"
    target_language: Literal["eng_Latn"] = "eng_Latn"


class TranslationResponse(ApiModel):
    """Generated English translation and model traceability."""

    translation: str
    source_language: Literal["amh_Ethi"] = "amh_Ethi"
    target_language: Literal["eng_Latn"] = "eng_Latn"
    model_id: str
    model_revision: str
    warning: str = NON_OFFICIAL_WARNING


class SearchRequest(ApiModel):
    """Bilingual evidence-search request."""

    query: str = Field(min_length=1, max_length=1_000)
    language: Literal["amh_Ethi", "eng_Latn"]
    limit: int = Field(default=5, ge=1, le=20)


class SearchResult(ApiModel):
    """One ranked bilingual passage."""

    rank: int = Field(ge=1)
    score: float = Field(ge=0, le=1)
    citation: Citation
    paired_text: str | None = Field(default=None, max_length=5_000)


class SearchResponse(ApiModel):
    """Ranked evidence for a bilingual query."""

    query: str
    results: list[SearchResult]


class AnswerRequest(ApiModel):
    """Question to answer only from retrieved evidence."""

    question: str = Field(min_length=1, max_length=1_000)
    language: Literal["amh_Ethi", "eng_Latn"]
    max_citations: int = Field(default=5, ge=1, le=10)


class AnswerResponse(ApiModel):
    """Cited answer or explicit abstention."""

    answer: str | None
    citations: list[Citation]
    abstained: bool
    abstention_reason: str | None = None
    warning: str = NON_OFFICIAL_WARNING


class ConversationCreate(ApiModel):
    """Create a conversation in the single MVP category."""

    title: str = Field(default="New conversation", min_length=1, max_length=120)


class ConversationSummary(ApiModel):
    """Conversation metadata for history navigation."""

    id: str
    category: Literal["legal_language"]
    title: str
    created_at: str
    updated_at: str


class MessageCreate(ApiModel):
    """Append one user, assistant, or system message."""

    role: Literal["user", "assistant", "system"]
    kind: Literal["translate", "search", "answer"]
    content: str = Field(min_length=1, max_length=10_000)


class MessageResponse(ApiModel):
    """Stored message returned as conversation history."""

    id: str
    conversation_id: str
    role: Literal["user", "assistant", "system"]
    kind: Literal["translate", "search", "answer"]
    content: str
    created_at: str


class ConversationDetail(ConversationSummary):
    """Conversation metadata and its complete ordered history."""

    messages: list[MessageResponse]


class AuditEventResponse(ApiModel):
    """Append-only event without duplicated conversation text."""

    id: int
    conversation_id: str
    action: str
    entity_type: str
    entity_id: str
    metadata: dict[str, str | int]
    occurred_at: str
