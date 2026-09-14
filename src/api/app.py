"""FastAPI application for the local MVP."""

from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Annotated

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel

from src.api.contracts import (
    AnswerRequest,
    AnswerResponse,
    AuditEventResponse,
    ConversationCreate,
    ConversationDetail,
    ConversationSummary,
    CorpusFileResponse,
    CorpusJobCreate,
    CorpusJobResponse,
    CorpusPageResponse,
    CorpusUploadConstraints,
    ErrorResponse,
    MessageCreate,
    MessageResponse,
    SearchRequest,
    SearchResponse,
    TranslationRequest,
    TranslationResponse,
)
from src.common.artifact_storage import ArtifactStorage, ArtifactStorageConfig
from src.common.job_store import Job, JobState, JobStore
from src.common.settings import load_app_settings
from src.corpus.ingestion import (
    PageRenderer,
    Pdf2ImageRenderer,
    PdfUploadError,
    RenderConfig,
    UploadLimits,
    process_render_job,
    store_upload_pair,
)
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


@lru_cache(maxsize=1)
def get_job_store() -> JobStore:
    """Return the local SQLite corpus-job store."""

    settings = load_app_settings()
    return JobStore.from_database_url(settings.database_url)


@lru_cache(maxsize=1)
def get_artifact_storage() -> ArtifactStorage:
    """Return private local artifact storage for uploaded PDFs."""

    return ArtifactStorage(ArtifactStorageConfig.from_env())


@lru_cache(maxsize=1)
def get_upload_limits() -> UploadLimits:
    """Return validated per-file PDF upload limits."""

    return UploadLimits.from_env()


@lru_cache(maxsize=1)
def get_page_renderer() -> PageRenderer:
    """Return the configured bounded PDF page renderer."""

    return Pdf2ImageRenderer(RenderConfig.from_env())


JobStoreDependency = Annotated[JobStore, Depends(get_job_store)]
ArtifactStorageDependency = Annotated[ArtifactStorage, Depends(get_artifact_storage)]
UploadLimitsDependency = Annotated[UploadLimits, Depends(get_upload_limits)]
PageRendererDependency = Annotated[PageRenderer, Depends(get_page_renderer)]


def _not_found(conversation_id: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "code": "conversation_not_found",
            "message": f"Conversation {conversation_id} was not found.",
        },
    )


def _corpus_not_found(job_id: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "code": "corpus_job_not_found",
            "message": f"Corpus job {job_id} was not found.",
        },
    )


def _corpus_job_response(
    job: Job,
    store: JobStore,
    limits: UploadLimits,
) -> CorpusJobResponse:
    files = [
        CorpusFileResponse(
            role=record.role,
            language=record.language,
            original_name=record.original_name,
            sha256=record.sha256,
            size_bytes=record.size_bytes,
            page_count=record.page_count,
        )
        for record in store.list_uploads(job.id)
    ]
    pages = [
        CorpusPageResponse(
            role=record.role,
            language=record.language,
            page_number=record.page_number,
            sha256=record.sha256,
            size_bytes=record.size_bytes,
            width=record.width,
            height=record.height,
        )
        for record in store.list_pages(job.id)
    ]
    return CorpusJobResponse(
        job_id=job.id,
        state=job.state.value,
        stage=job.stage,
        progress=job.progress,
        error_code=job.error_code,
        law_type=job.law_type,
        title=job.title,
        document_id=job.document_id,
        created_at=job.created_at,
        updated_at=job.updated_at,
        expires_at=job.expires_at,
        upload_constraints=CorpusUploadConstraints(
            max_pdf_bytes=limits.max_pdf_bytes,
            max_pdf_pages=limits.max_pdf_pages,
        ),
        files=files,
        pages=pages,
    )


@app.post(
    "/v1/corpus/jobs",
    response_model=CorpusJobResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["corpus"],
)
def create_corpus_job(
    payload: CorpusJobCreate,
    store: JobStoreDependency,
    storage: ArtifactStorageDependency,
    limits: UploadLimitsDependency,
) -> CorpusJobResponse:
    """Create a local paired-PDF upload job."""

    expires_at = (
        datetime.now(timezone.utc) + timedelta(days=storage.config.retention_days)
    ).isoformat()
    job = store.create(
        law_type=payload.law_type.value,
        title=payload.title,
        expires_at=expires_at,
    )
    return _corpus_job_response(job, store, limits)


@app.get(
    "/v1/corpus/jobs/{job_id}",
    response_model=CorpusJobResponse,
    responses={status.HTTP_404_NOT_FOUND: {"model": ErrorResponse}},
    tags=["corpus"],
)
def get_corpus_job(
    job_id: str,
    store: JobStoreDependency,
    limits: UploadLimitsDependency,
) -> CorpusJobResponse:
    """Return upload status and content-safe file metadata."""

    job = store.get(job_id)
    if job is None:
        raise _corpus_not_found(job_id)
    return _corpus_job_response(job, store, limits)


@app.post(
    "/v1/corpus/jobs/{job_id}/files",
    response_model=CorpusJobResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
        status.HTTP_413_REQUEST_ENTITY_TOO_LARGE: {"model": ErrorResponse},
        status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    },
    tags=["corpus"],
)
def upload_corpus_files(
    job_id: str,
    background_tasks: BackgroundTasks,
    source_file: Annotated[UploadFile, File(description="Amharic PDF")],
    target_file: Annotated[UploadFile, File(description="English PDF")],
    confirm_same_document: Annotated[bool, Form()],
    store: JobStoreDependency,
    storage: ArtifactStorageDependency,
    limits: UploadLimitsDependency,
    renderer: PageRendererDependency,
) -> CorpusJobResponse:
    """Validate and privately store an Amharic/English PDF pair."""

    if store.get(job_id) is None:
        raise _corpus_not_found(job_id)
    if not confirm_same_document:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "document_pair_not_confirmed",
                "message": "Confirm that both PDFs represent the same document.",
            },
        )
    try:
        job, _ = store_upload_pair(
            job_id=job_id,
            source_file=source_file.file,
            source_filename=source_file.filename,
            source_content_type=source_file.content_type,
            target_file=target_file.file,
            target_filename=target_file.filename,
            target_content_type=target_file.content_type,
            storage=storage,
            store=store,
            limits=limits,
        )
    except PdfUploadError as error:
        status_by_category = {
            "conflict": status.HTTP_409_CONFLICT,
            "media_type": status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "too_large": status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        }
        raise HTTPException(
            status_code=status_by_category.get(
                error.category,
                status.HTTP_422_UNPROCESSABLE_ENTITY,
            ),
            detail={"code": error.code, "message": str(error)},
        ) from error
    job = store.transition(
        job.id,
        JobState.QUEUED,
        stage="page_rendering_queued",
        progress=0.0,
    )
    background_tasks.add_task(
        process_render_job,
        job.id,
        storage=storage,
        store=store,
        renderer=renderer,
    )
    return _corpus_job_response(job, store, limits)


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
