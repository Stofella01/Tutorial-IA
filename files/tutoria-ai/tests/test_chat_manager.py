import pytest

from src.chat_manager import (
    DEFAULT_TITLE,
    MAX_TITLE_LENGTH,
    ChatManager,
    make_title,
    validate_user_input,
)
from src.storage import ConversationStorage


def make_manager(tmp_path, max_context=10):
    return ChatManager(ConversationStorage(tmp_path), max_context_messages=max_context)


def test_create_conversation_has_id_title_date_and_no_messages(tmp_path):
    manager = make_manager(tmp_path)

    conversation = manager.create_conversation()

    assert len(conversation.id) == 32
    assert conversation.title == DEFAULT_TITLE
    assert conversation.created_at
    assert conversation.messages == []
    assert manager.get_conversation(conversation.id) is not None  # foi salva


def test_each_conversation_gets_a_unique_id(tmp_path):
    manager = make_manager(tmp_path)

    assert manager.create_conversation().id != manager.create_conversation().id


def test_add_messages_keeps_author_content_and_timestamp(tmp_path):
    manager = make_manager(tmp_path)
    conversation = manager.create_conversation()

    manager.add_message(conversation, "user", "O que é Python?")
    manager.add_message(conversation, "assistant", "Uma linguagem de programação.")

    assert [m.role for m in conversation.messages] == ["user", "assistant"]
    assert conversation.messages[0].content == "O que é Python?"
    assert all(m.timestamp for m in conversation.messages)


def test_first_user_message_becomes_the_title(tmp_path):
    manager = make_manager(tmp_path)
    conversation = manager.create_conversation()

    manager.add_message(conversation, "user", "O que é Python?")
    manager.add_message(conversation, "user", "Outra pergunta")

    assert conversation.title == "O que é Python?"


def test_messages_are_persisted_and_reloaded(tmp_path):
    manager = make_manager(tmp_path)
    conversation = manager.create_conversation()
    manager.add_message(conversation, "user", "Olá")
    manager.add_message(conversation, "assistant", "Oi, tudo bem?")

    # um novo ChatManager (como após reiniciar o app) enxerga os mesmos dados
    reloaded = make_manager(tmp_path).get_conversation(conversation.id)

    assert reloaded.title == "Olá"
    assert [m.content for m in reloaded.messages] == ["Olá", "Oi, tudo bem?"]


def test_add_message_rejects_invalid_role_and_empty_content(tmp_path):
    manager = make_manager(tmp_path)
    conversation = manager.create_conversation()

    with pytest.raises(ValueError):
        manager.add_message(conversation, "system", "texto")
    with pytest.raises(ValueError):
        manager.add_message(conversation, "user", "   ")


def test_list_conversations_and_new_conversation_keeps_old_ones(tmp_path):
    manager = make_manager(tmp_path)
    first = manager.create_conversation()
    manager.add_message(first, "user", "Primeira")
    second = manager.create_conversation()
    manager.add_message(second, "user", "Segunda")

    titles = {c.title for c in manager.list_conversations()}

    assert titles == {"Primeira", "Segunda"}


def test_delete_conversation(tmp_path):
    manager = make_manager(tmp_path)
    keep = manager.create_conversation()
    remove = manager.create_conversation()

    assert manager.delete_conversation(remove.id) is True

    assert manager.get_conversation(remove.id) is None
    assert manager.get_conversation(keep.id) is not None


def test_clear_history(tmp_path):
    manager = make_manager(tmp_path)
    manager.create_conversation()
    manager.create_conversation()

    manager.clear_history()

    assert manager.list_conversations() == []


def test_build_context_respects_limit_and_keeps_latest_messages(tmp_path):
    manager = make_manager(tmp_path, max_context=3)
    conversation = manager.create_conversation()
    for number in range(6):
        manager.add_message(conversation, "user" if number % 2 == 0 else "assistant", f"m{number}")

    context = manager.build_context(conversation)

    assert [item["content"] for item in context] == ["m3", "m4", "m5"]
    assert set(context[0]) == {"role", "content"}  # só o que a API precisa


def test_validate_user_input():
    assert validate_user_input("  oi  ", 100) == "oi"
    with pytest.raises(ValueError):
        validate_user_input("   ", 100)
    with pytest.raises(ValueError):
        validate_user_input("x" * 101, 100)


def test_make_title_truncates_long_text():
    title = make_title("palavra " * 30)

    assert len(title) <= MAX_TITLE_LENGTH
    assert title.endswith("…")
