"""Carrega e valida as configurações da aplicação a partir de variáveis de ambiente."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_MAX_CONTEXT_MESSAGES = 10
DEFAULT_MAX_INPUT_CHARS = 4000
DEFAULT_TIMEOUT_SECONDS = 60.0

# Trechos que indicam que o valor é só o exemplo do .env.example, não uma chave real.
_PLACEHOLDER_MARKERS = ("sua-chave", "your-api-key", "your_api_key")


@dataclass(frozen=True)
class Settings:
    """Configurações já lidas e validadas."""

    # repr=False evita que a chave apareça se alguém imprimir o objeto por engano.
    api_key: str = field(default="", repr=False)
    base_url: str | None = None
    model: str = DEFAULT_MODEL
    max_context_messages: int = DEFAULT_MAX_CONTEXT_MESSAGES
    max_input_chars: int = DEFAULT_MAX_INPUT_CHARS
    request_timeout: float = DEFAULT_TIMEOUT_SECONDS
    data_dir: Path = PROJECT_ROOT / "data"
    # Avisos sobre valores inválidos (a aplicação usa o valor padrão no lugar).
    problems: tuple[str, ...] = ()

    @property
    def has_api_key(self) -> bool:
        """True se existe uma chave preenchida (e que não é o texto de exemplo)."""
        key = self.api_key.strip().lower()
        if not key:
            return False
        return not any(marker in key for marker in _PLACEHOLDER_MARKERS)


def _read_int(
    env: Mapping[str, str],
    name: str,
    default: int,
    minimum: int,
    maximum: int,
    problems: list[str],
) -> int:
    raw = env.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        problems.append(f"{name} deve ser um número inteiro. Usando o padrão ({default}).")
        return default
    if not minimum <= value <= maximum:
        problems.append(
            f"{name} deve estar entre {minimum} e {maximum}. Usando o padrão ({default})."
        )
        return default
    return value


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    """Lê as configurações.

    Sem argumentos, carrega o arquivo .env da raiz do projeto e usa os.environ.
    Nos testes, passe um dicionário em `env` para não depender do ambiente real.
    """
    if env is None:
        load_dotenv(PROJECT_ROOT / ".env", override=True)
        env = os.environ

    problems: list[str] = []

    base_url = env.get("OPENAI_BASE_URL", "").strip() or None
    if base_url and not base_url.startswith(("http://", "https://")):
        problems.append("OPENAI_BASE_URL deve começar com http:// ou https://. Ela foi ignorada.")
        base_url = None

    max_context = _read_int(
        env, "MAX_CONTEXT_MESSAGES", DEFAULT_MAX_CONTEXT_MESSAGES, 1, 50, problems
    )

    data_dir_raw = env.get("TUTORIA_DATA_DIR", "").strip()
    data_dir = Path(data_dir_raw) if data_dir_raw else PROJECT_ROOT / "data"
    if not data_dir.is_absolute():
        data_dir = PROJECT_ROOT / data_dir

    return Settings(
        api_key=env.get("OPENAI_API_KEY", "").strip(),
        base_url=base_url,
        model=env.get("OPENAI_MODEL", "").strip() or DEFAULT_MODEL,
        max_context_messages=max_context,
        data_dir=data_dir,
        problems=tuple(problems),
    )
