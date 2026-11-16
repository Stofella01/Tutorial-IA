import pytest

from src.storage import ConversationStorage, CorruptedHistoryError, StorageError

ID_A = "a" * 32
ID_B = "b" * 32


def make_conversation(conversation_id=ID_A, created_at="2026-01-01T10:00:00+00:00"):
    return {
        "id": conversation_id,
        "title": "Minha conversa",
        "created_at": created_at,
        "messages": [
            {"role": "user", "content": "Olá, ação!", "timestamp": created_at},
            {"role": "assistant", "content": "Oi!", "timestamp": created_at},
        ],
    }


def test_save_and_load_roundtrip(tmp_path):
    storage = ConversationStorage(tmp_path)
    conversation = make_conversation()

    storage.save(conversation)

    assert storage.load(ID_A) == conversation


def test_file_is_utf8_json_on_disk(tmp_path):
    storage = ConversationStorage(tmp_path)
    storage.save(make_conversation())

    text = (tmp_path / "conversations" / f"{ID_A}.json").read_text(encoding="utf-8")

    assert "Olá, ação!" in text  # acentos preservados, sem \u00e1


def test_load_missing_conversation_returns_none(tmp_path):
    storage = ConversationStorage(tmp_path)

    assert storage.load(ID_A) is None


def test_list_all_when_folder_does_not_exist(tmp_path):
    storage = ConversationStorage(tmp_path / "pasta-que-nao-existe")

    assert storage.list_all() == []


def test_list_all_is_sorted_newest_first(tmp_path):
    storage = ConversationStorage(tmp_path)
    storage.save(make_conversation(ID_A, "2026-01-01T10:00:00+00:00"))
    storage.save(make_conversation(ID_B, "2026-02-01T10:00:00+00:00"))

    ids = [item["id"] for item in storage.list_all()]

    assert ids == [ID_B, ID_A]


def test_delete_conversation(tmp_path):
    storage = ConversationStorage(tmp_path)
    storage.save(make_conversation())

    assert storage.delete(ID_A) is True
    assert storage.load(ID_A) is None
    assert storage.delete(ID_A) is False  # já não existe


def test_delete_all(tmp_path):
    storage = ConversationStorage(tmp_path)
    storage.save(make_conversation(ID_A))
    storage.save(make_conversation(ID_B))

    assert storage.delete_all() == 2
    assert storage.list_all() == []


def test_invalid_json_raises_corrupted_error(tmp_path):
    storage = ConversationStorage(tmp_path)
    folder = tmp_path / "conversations"
    folder.mkdir()
    (folder / f"{ID_A}.json").write_text("{ isto não é json", encoding="utf-8")

    with pytest.raises(CorruptedHistoryError):
        storage.load(ID_A)


def test_valid_json_with_wrong_structure_is_rejected(tmp_path):
    storage = ConversationStorage(tmp_path)
    folder = tmp_path / "conversations"
    folder.mkdir()
    (folder / f"{ID_A}.json").write_text('{"id": "x"}', encoding="utf-8")

    with pytest.raises(CorruptedHistoryError):
        storage.load(ID_A)


def test_list_all_isolates_corrupted_files_and_keeps_valid_ones(tmp_path):
    storage = ConversationStorage(tmp_path)
    storage.save(make_conversation(ID_B))
    folder = tmp_path / "conversations"
    (folder / f"{ID_A}.json").write_text("lixo", encoding="utf-8")

    conversations = storage.list_all()

    assert [item["id"] for item in conversations] == [ID_B]
    assert storage.skipped_files == 1
    assert (folder / f"{ID_A}.json.corrupted").exists()
    assert not (folder / f"{ID_A}.json").exists()


def test_invalid_id_is_rejected_to_prevent_path_traversal(tmp_path):
    storage = ConversationStorage(tmp_path)

    with pytest.raises(StorageError):
        storage.load("../../segredo")
    with pytest.raises(StorageError):
        storage.delete("../../segredo")


def test_save_rejects_invalid_conversation(tmp_path):
    storage = ConversationStorage(tmp_path)
    conversation = make_conversation()
    conversation["messages"][0]["role"] = "hacker"

    with pytest.raises(StorageError):
        storage.save(conversation)
