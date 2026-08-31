"""FastAPI application for the local MVP."""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel

from src.api.contracts import (
    AnswerRequest,
    AnswerResponse,
    AuditEventResponse,
    ConversationCreate,
    ConversationDetail,
    ConversationSummary,
    ErrorResponse,
    MessageCreate,
    MessageResponse,
    SearchRequest,
    SearchResponse,
    TranslationRequest,
    TranslationResponse,
)
from src.common.settings import load_app_settings
from src.history import ConversationNotFoundError, HistoryStore


class HealthResponse(BaseModel):
    """Public health-check response."""

    status: str
    service: str


app = FastAPI(
    title="Ethiopian Legal Language System API",
    version="0.1.0",
    description="Local API for non-official Amharic-English legal language tools.",
)


@app.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    """Report that the API process is ready to accept requests."""

    return HealthResponse(status="ok", service="ethiopian-legal-language-system")


@lru_cache(maxsize=1)
def get_history_store() -> HistoryStore:
    """Return the process-local history store configured for the MVP."""

    settings = load_app_settings()
    return HistoryStore.from_database_url(settings.database_url)


HistoryStoreDependency = Annotated[HistoryStore, Depends(get_history_store)]


def _not_found(conversation_id: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "code": "conversation_not_found",
            "message": f"Conversation {conversation_id} was not found.",
        },
    )


@app.post(
    "/v1/conversations",
    response_model=ConversationSummary,
    status_code=status.HTTP_201_CREATED,
    tags=["history"],
)
def create_conversation(
    payload: ConversationCreate,
    store: HistoryStoreDependency,
) -> ConversationSummary:
    """Create a conversation inside the fixed legal-language category."""

    return ConversationSummary.model_validate(store.create_conversation(payload.title))


@app.get(
    "/v1/conversations",
    response_model=list[ConversationSummary],
    tags=["history"],
)
def list_conversations(
    store: HistoryStoreDependency,
) -> list[ConversationSummary]:
    """List all conversations in the single category."""

    return [ConversationSummary.model_validate(item) for item in store.list_conversations()]


@app.get(
    "/v1/conversations/{conversation_id}",
    response_model=ConversationDetail,
    responses={status.HTTP_404_NOT_FOUND: {"model": ErrorResponse}},
    tags=["history"],
)
def get_conversation(
    conversation_id: str,
    store: HistoryStoreDependency,
) -> ConversationDetail:
    """Return one conversation and its complete ordered history."""

    try:
        conversation = store.get_conversation(conversation_id)
        messages = store.list_messages(conversation_id)
    except ConversationNotFoundError as error:
        raise _not_found(conversation_id) from error
    return ConversationDetail(
        **ConversationSummary.model_validate(conversation).model_dump(),
        messages=[MessageResponse.model_validate(item) for item in messages],
    )


@app.post(
    "/v1/conversations/{conversation_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    responses={status.HTTP_404_NOT_FOUND: {"model": ErrorResponse}},
    tags=["history"],
)
def add_message(
    conversation_id: str,
    payload: MessageCreate,
    store: HistoryStoreDependency,
) -> MessageResponse:
    """Append a message and its audit event atomically."""

    try:
        message = store.add_message(
            conversation_id,
            role=payload.role,
            kind=payload.kind,
            content=payload.content,
        )
    except ConversationNotFoundError as error:
        raise _not_found(conversation_id) from error
    return MessageResponse.model_validate(message)


@app.get(
    "/v1/conversations/{conversation_id}/audit",
    response_model=list[AuditEventResponse],
    responses={status.HTTP_404_NOT_FOUND: {"model": ErrorResponse}},
    tags=["history"],
)
def list_audit_events(
    conversation_id: str,
    store: HistoryStoreDependency,
) -> list[AuditEventResponse]:
    """Return append-only events without duplicating conversation text."""

    try:
        events = store.list_audit_events(conversation_id)
    except ConversationNotFoundError as error:
        raise _not_found(conversation_id) from error
    return [AuditEventResponse.model_validate(item) for item in events]


_NOT_IMPLEMENTED = {
    "model": ErrorResponse,
    "description": "The contract exists, but the MVP service is not connected yet.",
}


@app.post(
    "/v1/translate",
    response_model=TranslationResponse,
    responses={status.HTTP_501_NOT_IMPLEMENTED: _NOT_IMPLEMENTED},
    tags=["translation"],
)
def translate(_: TranslationRequest) -> TranslationResponse:
    """Expose the translation contract until the selected model is connected."""

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail={"code": "service_not_ready", "message": "Translation is not connected yet."},
    )


@app.post(
    "/v1/search",
    response_model=SearchResponse,
    responses={status.HTTP_501_NOT_IMPLEMENTED: _NOT_IMPLEMENTED},
    tags=["retrieval"],
)
def search(_: SearchRequest) -> SearchResponse:
    """Expose the search contract until the bilingual index is connected."""

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail={"code": "service_not_ready", "message": "Search is not connected yet."},
    )


@app.post(
    "/v1/answer",
    response_model=AnswerResponse,
    responses={status.HTTP_501_NOT_IMPLEMENTED: _NOT_IMPLEMENTED},
    tags=["retrieval"],
)
def answer(_: AnswerRequest) -> AnswerResponse:
    """Expose the answer contract until retrieval and generation are connected."""

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail={"code": "service_not_ready", "message": "Cited answers are not connected yet."},
    )
