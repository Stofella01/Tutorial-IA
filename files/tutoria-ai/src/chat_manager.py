"""Gerencia conversas e mensagens e prepara o contexto enviado à IA."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from src.storage import VALID_ROLES, ConversationStorage

DEFAULT_TITLE = "Nova conversa"
MAX_TITLE_LENGTH = 40


def _now() -> str:
    """Data e hora atuais em UTC, no formato ISO 8601."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Message:
    role: str  # "user" (usuário) ou "assistant" (IA)
    content: str
    timestamp: str

    def to_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content, "timestamp": self.timestamp}


@dataclass
class Conversation:
    id: str
    title: str
    created_at: str
    messages: list[Message] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "created_at": self.created_at,
            "messages": [message.to_dict() for message in self.messages],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Conversation:
        """Cria a conversa a partir de um dicionário já validado pelo storage."""
        messages = [
            Message(item["role"], item["content"], item["timestamp"])
            for item in data["messages"]
        ]
        return cls(data["id"], data["title"], data["created_at"], messages)


def validate_user_input(text: str, max_chars: int) -> str:
    """Remove espaços extras e confere o tamanho. Lança ValueError com mensagem amigável."""
    if not isinstance(text, str):
        raise ValueError("A mensagem precisa ser um texto.")
    cleaned = text.replace("\x00", "").strip()
    if not cleaned:
        raise ValueError("Digite uma pergunta antes de enviar.")
    if len(cleaned) > max_chars:
        raise ValueError(f"A mensagem é muito longa (máximo de {max_chars} caracteres).")
    return cleaned


def make_title(text: str) -> str:
    """Cria o título da conversa a partir da primeira pergunta."""
    single_line = " ".join(text.split())
    if len(single_line) <= MAX_TITLE_LENGTH:
        return single_line or DEFAULT_TITLE
    return single_line[: MAX_TITLE_LENGTH - 1].rstrip() + "…"


class ChatManager:
    def __init__(self, storage: ConversationStorage, max_context_messages: int = 10) -> None:
        self.storage = storage
        self.max_context_messages = max(1, max_context_messages)

    def create_conversation(self) -> Conversation:
        conversation = Conversation(uuid.uuid4().hex, DEFAULT_TITLE, _now())
        self.storage.save(conversation.to_dict())
        return conversation

    def get_conversation(self, conversation_id: str) -> Conversation | None:
        data = self.storage.load(conversation_id)
        return Conversation.from_dict(data) if data else None

    def list_conversations(self) -> list[Conversation]:
        return [Conversation.from_dict(data) for data in self.storage.list_all()]

    def add_message(self, conversation: Conversation, role: str, content: str) -> Message:
        """Adiciona uma mensagem à conversa e salva em disco."""
        if role not in VALID_ROLES:
            raise ValueError("Autor da mensagem inválido.")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("A mensagem não pode ser vazia.")

        message = Message(role, content.strip(), _now())
        conversation.messages.append(message)
        if role == "user" and conversation.title == DEFAULT_TITLE:
            conversation.title = make_title(message.content)
        self.storage.save(conversation.to_dict())
        return message

    def build_context(self, conversation: Conversation) -> list[dict[str, str]]:
        """Devolve as últimas mensagens (até o limite configurado) no formato da API."""
        recent = conversation.messages[-self.max_context_messages :]
        return [{"role": message.role, "content": message.content} for message in recent]

    def delete_conversation(self, conversation_id: str) -> bool:
        return self.storage.delete(conversation_id)

    def clear_history(self) -> int:
        return self.storage.delete_all()
