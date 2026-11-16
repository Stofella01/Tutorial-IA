"""Comunicação com o provedor de IA (qualquer API compatível com a da OpenAI)."""

from __future__ import annotations

import logging
from typing import Any

import openai
from openai import OpenAI

from src.config import Settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Você é o Tutoria AI, um professor particular de tecnologia. \
Você ajuda estudantes com Python, programação, engenharia de software, inteligência \
artificial, machine learning, LLMs, APIs, desenvolvimento web e tecnologia em geral.

Siga estas regras:
- Explique primeiro de forma simples e só depois aprofunde, se fizer sentido.
- Dê exemplos práticos e, quando possível, exemplos de código curtos e comentados.
- Evite respostas excessivamente complexas para iniciantes e explique cada termo técnico \
na primeira vez que ele aparecer.
- Incentive o aprendizado: sugira um pequeno exercício ou o próximo passo, em vez de apenas \
entregar respostas prontas.
- Se não souber a resposta ou não tiver certeza, diga isso claramente. Não invente \
informações, funções, bibliotecas ou fontes.
- Responda no idioma do usuário (em português quando ele escrever em português).
- Se a pergunta fugir de tecnologia, responda de forma breve e, se fizer sentido, \
relacione com o estudo de tecnologia.
- Nunca peça nem repita chaves de API, senhas ou outros dados sensíveis."""


class AIServiceError(Exception):
    """Erro na comunicação com a IA. `user_message` é seguro para mostrar ao usuário
    (nunca contém chave de API nem o texto bruto do erro do provedor)."""

    def __init__(self, user_message: str) -> None:
        super().__init__(user_message)
        self.user_message = user_message


class MissingAPIKeyError(AIServiceError):
    def __init__(self) -> None:
        super().__init__(
            "A chave de API não está configurada. Preencha OPENAI_API_KEY no arquivo .env."
        )


class EmptyResponseError(AIServiceError):
    def __init__(self) -> None:
        super().__init__("A IA devolveu uma resposta vazia. Tente reformular a pergunta.")


def _translate_error(error: Exception) -> AIServiceError:
    """Converte um erro do SDK numa mensagem segura em português.

    Nunca usamos str(error): as mensagens dos provedores podem trazer trechos da chave.
    Só registramos o nome da classe do erro e o código HTTP, quando existir.
    """
    status = getattr(error, "status_code", None)
    logger.warning("Falha ao chamar a API de IA: %s (status=%s)", type(error).__name__, status)

    if isinstance(error, openai.AuthenticationError):
        text = "A chave de API foi recusada pelo provedor. Confira OPENAI_API_KEY no arquivo .env."
    elif isinstance(error, openai.PermissionDeniedError):
        text = "A chave de API não tem permissão para usar este modelo ou recurso."
    elif isinstance(error, openai.RateLimitError):
        text = (
            "Limite de requisições ou de crédito atingido no provedor. "
            "Aguarde um pouco e confira o seu plano."
        )
    elif isinstance(error, openai.NotFoundError):
        text = "Modelo ou endereço não encontrado. Confira OPENAI_MODEL e OPENAI_BASE_URL."
    elif isinstance(error, openai.APITimeoutError):
        text = "O provedor demorou demais para responder. Tente novamente."
    elif isinstance(error, openai.APIConnectionError):
        text = "Falha de conexão com o provedor de IA. Confira sua internet e OPENAI_BASE_URL."
    elif isinstance(error, openai.APIStatusError):
        text = f"O provedor retornou um erro (código {status}). Tente novamente em instantes."
    else:
        text = "Ocorreu um erro inesperado ao consultar a IA."
    return AIServiceError(text)


class AIService:
    """Envia mensagens ao modelo e devolve o texto da resposta."""

    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        self.settings = settings
        # `client` permite injetar um cliente falso nos testes.
        self._client = client

    @property
    def is_configured(self) -> bool:
        return self.settings.has_api_key

    def _get_client(self) -> Any:
        if self._client is None:
            self._client = OpenAI(
                api_key=self.settings.api_key,
                base_url=self.settings.base_url,
                timeout=self.settings.request_timeout,
                max_retries=2,
            )
        return self._client

    def generate_reply(self, messages: list[dict[str, str]]) -> str:
        """Envia o contexto (lista de {"role", "content"}) e devolve a resposta da IA."""
        if not self.is_configured:
            raise MissingAPIKeyError()

        payload = [{"role": "system", "content": SYSTEM_PROMPT}, *messages]
        try:
            response = self._get_client().chat.completions.create(
                model=self.settings.model,
                messages=payload,
            )
        except Exception as error:  # o SDK pode lançar vários tipos; todos são traduzidos
            raise _translate_error(error) from None

        try:
            content = response.choices[0].message.content
        except (AttributeError, IndexError, TypeError):
            content = None
        if not isinstance(content, str) or not content.strip():
            raise EmptyResponseError()
        return content.strip()

    def check_connection(self) -> tuple[bool, str]:
        """Testa o acesso ao provedor sem gastar tokens (lista os modelos).

        Retorna (deu_certo, mensagem). Alguns provedores não oferecem essa rota;
        nesse caso a resposta explica que o teste não é conclusivo.
        """
        if not self.is_configured:
            return False, MissingAPIKeyError().user_message
        try:
            self._get_client().models.list()
        except openai.NotFoundError:
            return False, (
                "Este provedor não permite listar modelos, então não foi possível "
                "verificar. Envie uma mensagem para testar."
            )
        except Exception as error:
            return False, _translate_error(error).user_message
        return True, "Conexão com o provedor verificada."
