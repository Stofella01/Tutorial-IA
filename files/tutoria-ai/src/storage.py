"""Persistência das conversas em arquivos JSON (um arquivo por conversa).

Este módulo trabalha com dicionários simples. Quem transforma esses dicionários
em objetos é o chat_manager.py.

Estrutura de uma conversa no JSON:
{
  "id": "<32 caracteres hexadecimais>",
  "title": "Título",
  "created_at": "2026-01-01T12:00:00+00:00",
  "messages": [
    {"role": "user" | "assistant", "content": "...", "timestamp": "..."}
  ]
}
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# O id vira nome de arquivo; validar o formato impede ataques como "../../arquivo".
_ID_PATTERN = re.compile(r"[0-9a-f]{32}")
VALID_ROLES = ("user", "assistant")


class StorageError(Exception):
    """Erro ao ler ou gravar o histórico. A mensagem é segura para mostrar ao usuário."""


class CorruptedHistoryError(StorageError):
    """O arquivo existe, mas o conteúdo não é uma conversa válida."""


def validate_conversation_data(data: Any) -> None:
    """Confere se `data` tem o formato esperado. Lança CorruptedHistoryError se não tiver."""
    if not isinstance(data, dict):
        raise CorruptedHistoryError("Formato de conversa inválido.")

    for key in ("id", "title", "created_at"):
        if not isinstance(data.get(key), str) or not data[key]:
            raise CorruptedHistoryError(f"Campo '{key}' ausente ou inválido.")

    if not _ID_PATTERN.fullmatch(data["id"]):
        raise CorruptedHistoryError("Identificador de conversa inválido.")

    messages = data.get("messages")
    if not isinstance(messages, list):
        raise CorruptedHistoryError("Campo 'messages' ausente ou inválido.")

    for message in messages:
        if not isinstance(message, dict):
            raise CorruptedHistoryError("Mensagem em formato inválido.")
        if message.get("role") not in VALID_ROLES:
            raise CorruptedHistoryError("Mensagem com autor inválido.")
        if not isinstance(message.get("content"), str):
            raise CorruptedHistoryError("Mensagem sem conteúdo válido.")
        if not isinstance(message.get("timestamp"), str):
            raise CorruptedHistoryError("Mensagem sem data/hora válida.")


class ConversationStorage:
    """Salva, carrega e exclui conversas dentro de <data_dir>/conversations/."""

    def __init__(self, data_dir: str | Path) -> None:
        self.directory = Path(data_dir) / "conversations"
        # Quantos arquivos inválidos foram isolados na última chamada de list_all().
        self.skipped_files = 0

    def _path_for(self, conversation_id: str) -> Path:
        if not isinstance(conversation_id, str) or not _ID_PATTERN.fullmatch(conversation_id):
            raise StorageError("Identificador de conversa inválido.")
        return self.directory / f"{conversation_id}.json"

    def save(self, conversation: dict[str, Any]) -> None:
        """Grava a conversa. Escreve num arquivo temporário e troca no final,
        para não deixar o arquivo pela metade se algo falhar no meio."""
        validate_conversation_data(conversation)
        path = self._path_for(conversation["id"])
        temp_path = path.with_name(path.name + ".tmp")
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            with open(temp_path, "w", encoding="utf-8") as file:
                json.dump(conversation, file, ensure_ascii=False, indent=2)
            os.replace(temp_path, path)
        except OSError as error:
            logger.error("Falha ao salvar conversa: %s", type(error).__name__)
            raise StorageError("Não foi possível salvar a conversa no disco.") from None

    def load(self, conversation_id: str) -> dict[str, Any] | None:
        """Retorna a conversa, ou None se ela não existir.

        Lança CorruptedHistoryError se o arquivo existir mas estiver inválido.
        """
        path = self._path_for(conversation_id)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as file:
                data = json.load(file)
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise CorruptedHistoryError("O arquivo da conversa está corrompido.") from None
        except OSError as error:
            logger.error("Falha ao ler conversa: %s", type(error).__name__)
            raise StorageError("Não foi possível ler a conversa do disco.") from None

        validate_conversation_data(data)
        if data["id"] != conversation_id:
            raise CorruptedHistoryError("O identificador não corresponde ao arquivo.")
        return data

    def list_all(self) -> list[dict[str, Any]]:
        """Retorna todas as conversas válidas, da mais nova para a mais antiga.

        Arquivos corrompidos não derrubam a aplicação: são renomeados para
        '<id>.json.corrupted' (para você poder inspecionar) e contados em skipped_files.
        """
        self.skipped_files = 0
        if not self.directory.exists():
            return []

        conversations: list[dict[str, Any]] = []
        for path in sorted(self.directory.glob("*.json")):
            if not _ID_PATTERN.fullmatch(path.stem):
                continue
            try:
                data = self.load(path.stem)
            except CorruptedHistoryError:
                self._quarantine(path)
                self.skipped_files += 1
                continue
            except StorageError:
                self.skipped_files += 1
                continue
            if data is not None:
                conversations.append(data)

        conversations.sort(key=lambda item: item["created_at"], reverse=True)
        return conversations

    def delete(self, conversation_id: str) -> bool:
        """Apaga uma conversa. Retorna True se ela existia."""
        path = self._path_for(conversation_id)
        if not path.exists():
            return False
        try:
            path.unlink()
        except OSError as error:
            logger.error("Falha ao excluir conversa: %s", type(error).__name__)
            raise StorageError("Não foi possível excluir a conversa.") from None
        return True

    def delete_all(self) -> int:
        """Apaga todas as conversas (inclusive arquivos isolados). Retorna quantos arquivos."""
        if not self.directory.exists():
            return 0
        removed = 0
        for pattern in ("*.json", "*.json.corrupted", "*.json.tmp"):
            for path in self.directory.glob(pattern):
                try:
                    path.unlink()
                    removed += 1
                except OSError as error:
                    logger.error("Falha ao excluir arquivo: %s", type(error).__name__)
                    raise StorageError("Não foi possível limpar o histórico.") from None
        return removed

    @staticmethod
    def _quarantine(path: Path) -> None:
        target = path.with_name(path.name + ".corrupted")
        try:
            os.replace(path, target)
            logger.warning("Arquivo de histórico inválido isolado: %s", target.name)
        except OSError as error:
            logger.error("Não foi possível isolar arquivo inválido: %s", type(error).__name__)
