from pathlib import Path

from fastapi.testclient import TestClient

from src.api.app import app, get_history_store
from src.history import HistoryStore


def test_store_keeps_ordered_history_and_content_safe_audit(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "history.db")
    conversation = store.create_conversation("Translation review")

    first = store.add_message(
        conversation.id,
        role="user",
        kind="translate",
        content="የሙከራ ጽሑፍ",
    )
    second = store.add_message(
        conversation.id,
        role="assistant",
        kind="translate",
        content="Synthetic test text",
    )

    history = store.list_messages(conversation.id)
    events = store.list_audit_events(conversation.id)
    assert [message.id for message in history] == [first.id, second.id]
    assert conversation.category == "legal_language"
    assert [event.action for event in events] == [
        "conversation.created",
        "message.created",
        "message.created",
    ]
    assert events[1].metadata == {
        "content_length": len("የሙከራ ጽሑፍ"),
        "kind": "translate",
        "role": "user",
    }
    assert "የሙከራ" not in str(events)


def test_history_api_saves_conversation_messages_and_audit(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "api-history.db")
    app.dependency_overrides[get_history_store] = lambda: store
    try:
        with TestClient(app) as client:
            created = client.post(
                "/v1/conversations", json={"title": "Legal language session"}
            )
            conversation_id = created.json()["id"]
            message = client.post(
                f"/v1/conversations/{conversation_id}/messages",
                json={"role": "user", "kind": "answer", "content": "What is Article 2?"},
            )
            detail = client.get(f"/v1/conversations/{conversation_id}")
            audit = client.get(f"/v1/conversations/{conversation_id}/audit")
    finally:
        app.dependency_overrides.clear()

    assert created.status_code == 201
    assert created.json()["category"] == "legal_language"
    assert message.status_code == 201
    assert detail.json()["messages"][0]["content"] == "What is Article 2?"
    assert [event["action"] for event in audit.json()] == [
        "conversation.created",
        "message.created",
    ]
    assert audit.json()[1]["metadata"]["content_length"] == len("What is Article 2?")
    assert "What is Article 2?" not in str(audit.json())


def test_history_api_returns_safe_not_found(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "missing.db")
    app.dependency_overrides[get_history_store] = lambda: store
    try:
        with TestClient(app) as client:
            response = client.get("/v1/conversations/unknown")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "conversation_not_found"
