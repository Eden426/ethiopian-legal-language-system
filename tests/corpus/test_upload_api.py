from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from src.api.app import (
    app,
    get_artifact_storage,
    get_job_store,
    get_upload_limits,
)
from src.common.artifact_storage import ArtifactStorage, ArtifactStorageConfig
from src.common.job_store import JobStore
from src.corpus.ingestion import UploadLimits


def _pdf_bytes(*, pages: int = 1, width: int = 200) -> bytes:
    output = BytesIO()
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=width, height=300)
    writer.write(output)
    return output.getvalue()


@pytest.fixture
def corpus_client(tmp_path: Path) -> tuple[TestClient, JobStore, ArtifactStorage]:
    store = JobStore(tmp_path / "ells.db")
    storage = ArtifactStorage(ArtifactStorageConfig(tmp_path / "private", retention_days=7))
    limits = UploadLimits(max_pdf_bytes=1024 * 1024, max_pdf_pages=10)
    app.dependency_overrides[get_job_store] = lambda: store
    app.dependency_overrides[get_artifact_storage] = lambda: storage
    app.dependency_overrides[get_upload_limits] = lambda: limits
    with TestClient(app) as client:
        yield client, store, storage
    app.dependency_overrides.clear()


def _create_job(client: TestClient, law_type: str = "proclamation") -> str:
    response = client.post(
        "/v1/corpus/jobs",
        json={"law_type": law_type, "title": "Synthetic bilingual fixture"},
    )
    assert response.status_code == 201
    return response.json()["job_id"]


def _paired_files(
    source: bytes | None = None,
    target: bytes | None = None,
) -> dict[str, tuple[str, bytes, str]]:
    return {
        "source_file": (
            "አዋጅ.pdf",
            source if source is not None else _pdf_bytes(width=200),
            "application/pdf",
        ),
        "target_file": (
            "proclamation.pdf",
            target if target is not None else _pdf_bytes(width=201),
            "application/pdf",
        ),
    }


def test_create_book_job_and_upload_distinct_language_pdfs(
    corpus_client: tuple[TestClient, JobStore, ArtifactStorage],
) -> None:
    client, store, storage = corpus_client
    job_id = _create_job(client, law_type="book")
    source_pdf = _pdf_bytes(width=200)
    target_pdf = _pdf_bytes(width=201)

    response = client.post(
        f"/v1/corpus/jobs/{job_id}/files",
        files=_paired_files(source=source_pdf, target=target_pdf),
        data={"confirm_same_document": "true"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["law_type"] == "book"
    assert payload["state"] == "uploaded"
    assert [item["language"] for item in payload["files"]] == ["amh_Ethi", "eng_Latn"]
    assert [item["page_count"] for item in payload["files"]] == [1, 1]
    assert payload["files"][0]["original_name"] == "አዋጅ.pdf"
    assert "private" not in response.text
    assert store.get(job_id) is not None
    assert storage.upload_path(job_id, "source").read_bytes() == source_pdf
    assert storage.upload_path(job_id, "target").read_bytes() == target_pdf
    assert payload["files"][0]["sha256"] == hashlib.sha256(source_pdf).hexdigest()
    assert payload["files"][1]["sha256"] == hashlib.sha256(target_pdf).hexdigest()


def test_job_status_reports_constraints_without_local_paths(
    corpus_client: tuple[TestClient, JobStore, ArtifactStorage],
) -> None:
    client, _, _ = corpus_client
    job_id = _create_job(client)

    response = client.get(f"/v1/corpus/jobs/{job_id}")

    assert response.status_code == 200
    assert response.json()["law_type"] == "proclamation"
    assert response.json()["state"] == "created"
    assert response.json()["upload_constraints"] == {
        "max_pdf_bytes": 1024 * 1024,
        "max_pdf_pages": 10,
        "accepted_content_types": ["application/pdf"],
        "source_language": "amh_Ethi",
        "target_language": "eng_Latn",
    }
    assert str(Path.cwd()) not in response.text


def test_job_creation_rejects_unsupported_document_type(
    corpus_client: tuple[TestClient, JobStore, ArtifactStorage],
) -> None:
    client, _, _ = corpus_client

    response = client.post("/v1/corpus/jobs", json={"law_type": "court_case"})

    assert response.status_code == 422


def test_upload_requires_same_document_confirmation(
    corpus_client: tuple[TestClient, JobStore, ArtifactStorage],
) -> None:
    client, store, _ = corpus_client
    job_id = _create_job(client)

    response = client.post(
        f"/v1/corpus/jobs/{job_id}/files",
        files=_paired_files(),
        data={"confirm_same_document": "false"},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "document_pair_not_confirmed"
    assert store.list_uploads(job_id) == []


def test_upload_rejects_identical_language_files_without_partial_records(
    corpus_client: tuple[TestClient, JobStore, ArtifactStorage],
) -> None:
    client, store, storage = corpus_client
    job_id = _create_job(client)
    same_pdf = _pdf_bytes()

    response = client.post(
        f"/v1/corpus/jobs/{job_id}/files",
        files=_paired_files(source=same_pdf, target=same_pdf),
        data={"confirm_same_document": "true"},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "identical_language_files"
    assert store.list_uploads(job_id) == []
    assert not storage.upload_path(job_id, "source").exists()
    assert not storage.upload_path(job_id, "target").exists()


def test_upload_rejects_malformed_pdf(
    corpus_client: tuple[TestClient, JobStore, ArtifactStorage],
) -> None:
    client, store, _ = corpus_client
    job_id = _create_job(client)

    response = client.post(
        f"/v1/corpus/jobs/{job_id}/files",
        files=_paired_files(source=b"%PDF-not-a-readable-document"),
        data={"confirm_same_document": "true"},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "malformed_pdf"
    assert store.list_uploads(job_id) == []


def test_upload_rejects_wrong_content_type(
    corpus_client: tuple[TestClient, JobStore, ArtifactStorage],
) -> None:
    client, _, _ = corpus_client
    job_id = _create_job(client)
    files = _paired_files()
    files["source_file"] = ("source.pdf", _pdf_bytes(), "text/plain")

    response = client.post(
        f"/v1/corpus/jobs/{job_id}/files",
        files=files,
        data={"confirm_same_document": "true"},
    )

    assert response.status_code == 415
    assert response.json()["detail"]["code"] == "unsupported_file_type"


def test_upload_rejects_filename_path_components(
    corpus_client: tuple[TestClient, JobStore, ArtifactStorage],
) -> None:
    client, store, _ = corpus_client
    job_id = _create_job(client)
    files = _paired_files()
    files["source_file"] = ("../source.pdf", _pdf_bytes(), "application/pdf")

    response = client.post(
        f"/v1/corpus/jobs/{job_id}/files",
        files=files,
        data={"confirm_same_document": "true"},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_filename"
    assert store.list_uploads(job_id) == []


def test_upload_rejects_oversized_pdf(tmp_path: Path) -> None:
    store = JobStore(tmp_path / "ells.db")
    storage = ArtifactStorage(ArtifactStorageConfig(tmp_path / "private"))
    app.dependency_overrides[get_job_store] = lambda: store
    app.dependency_overrides[get_artifact_storage] = lambda: storage
    app.dependency_overrides[get_upload_limits] = lambda: UploadLimits(
        max_pdf_bytes=100,
        max_pdf_pages=10,
    )
    try:
        with TestClient(app) as client:
            job_id = _create_job(client)
            response = client.post(
                f"/v1/corpus/jobs/{job_id}/files",
                files=_paired_files(),
                data={"confirm_same_document": "true"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "file_too_large"
    assert store.list_uploads(job_id) == []


def test_upload_rejects_too_many_pages(tmp_path: Path) -> None:
    store = JobStore(tmp_path / "ells.db")
    storage = ArtifactStorage(ArtifactStorageConfig(tmp_path / "private"))
    app.dependency_overrides[get_job_store] = lambda: store
    app.dependency_overrides[get_artifact_storage] = lambda: storage
    app.dependency_overrides[get_upload_limits] = lambda: UploadLimits(
        max_pdf_bytes=1024 * 1024,
        max_pdf_pages=1,
    )
    try:
        with TestClient(app) as client:
            job_id = _create_job(client)
            response = client.post(
                f"/v1/corpus/jobs/{job_id}/files",
                files=_paired_files(source=_pdf_bytes(pages=2)),
                data={"confirm_same_document": "true"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "too_many_pages"
    assert store.list_uploads(job_id) == []


def test_second_upload_attempt_is_rejected(
    corpus_client: tuple[TestClient, JobStore, ArtifactStorage],
) -> None:
    client, _, _ = corpus_client
    job_id = _create_job(client)
    first = client.post(
        f"/v1/corpus/jobs/{job_id}/files",
        files=_paired_files(),
        data={"confirm_same_document": "true"},
    )

    second = client.post(
        f"/v1/corpus/jobs/{job_id}/files",
        files=_paired_files(
            source=_pdf_bytes(width=202),
            target=_pdf_bytes(width=203),
        ),
        data={"confirm_same_document": "true"},
    )

    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "job_not_uploadable"
