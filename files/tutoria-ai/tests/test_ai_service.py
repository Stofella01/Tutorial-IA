"""Testes do AIService. Nenhum teste acessa a internet nem consome créditos:
usamos um cliente falso no lugar do cliente real da OpenAI."""

import logging
from types import SimpleNamespace

import httpx
import openai
import pytest

from src.ai_service import (
    SYSTEM_PROMPT,
    AIService,
    AIServiceError,
    EmptyResponseError,
    MissingAPIKeyError,
)
from src.chat_manager import ChatManager
from src.config import load_settings
from src.storage import ConversationStorage

SECRET_KEY = "chave-secreta-123"


class FakeClient:
    """Imita o pedaço do cliente da OpenAI que o projeto usa."""

    def __init__(self, reply="Resposta simulada", error=None, response=None):
        self.error = error
        self.calls = []
        self._response = response or SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=reply))]
        )
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))
        self.models = SimpleNamespace(list=self._list)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self._response

    def _list(self):
        if self.error:
            raise self.error
        return []


def make_settings(api_key=SECRET_KEY):
    return load_settings({"OPENAI_API_KEY": api_key, "OPENAI_MODEL": "modelo-teste"})


def make_status_error(error_class, status):
    # a mensagem do "provedor" traz a chave, como acontece em erros 401 reais
    request = httpx.Request("POST", "https://api.exemplo.com/v1/chat/completions")
    response = httpx.Response(status, request=request)
    return error_class(f"Incorrect API key provided: {SECRET_KEY}", response=response, body=None)


def make_request():
    return httpx.Request("POST", "https://api.exemplo.com/v1/chat/completions")


# ---------------------------------------------------------------- resposta simulada


def test_returns_simulated_reply_and_sends_system_prompt_plus_context():
    client = FakeClient(reply="  Uma função agrupa código.  ")
    service = AIService(make_settings(), client=client)
    context = [{"role": "user", "content": "O que é uma função?"}]

    reply = service.generate_reply(context)

    assert reply == "Uma função agrupa código."
    sent = client.calls[0]
    assert sent["model"] == "modelo-teste"
    assert sent["messages"][0] == {"role": "system", "content": SYSTEM_PROMPT}
    assert sent["messages"][1:] == context


def test_full_flow_question_context_reply_and_history(tmp_path):
    manager = ChatManager(ConversationStorage(tmp_path), max_context_messages=10)
    service = AIService(make_settings(), client=FakeClient(reply="Python é uma linguagem."))
    conversation = manager.create_conversation()

    manager.add_message(conversation, "user", "O que é Python?")
    reply = service.generate_reply(manager.build_context(conversation))
    manager.add_message(conversation, "assistant", reply)

    saved = manager.get_conversation(conversation.id)
    assert [m.role for m in saved.messages] == ["user", "assistant"]
    assert saved.messages[1].content == "Python é uma linguagem."


# ---------------------------------------------------------------- sem chave de API


def test_missing_api_key_raises_clear_error_without_calling_api():
    client = FakeClient()
    service = AIService(make_settings(api_key=""), client=client)

    with pytest.raises(MissingAPIKeyError) as info:
        service.generate_reply([{"role": "user", "content": "oi"}])

    assert "OPENAI_API_KEY" in info.value.user_message
    assert client.calls == []


def test_example_placeholder_key_counts_as_missing():
    service = AIService(make_settings(api_key="sua-chave-de-api-aqui"), client=FakeClient())

    assert service.is_configured is False


def test_check_connection_without_key():
    ok, message = AIService(make_settings(api_key="")).check_connection()

    assert ok is False
    assert "OPENAI_API_KEY" in message


# ---------------------------------------------------------------- falhas da API


def test_empty_reply_raises_error():
    for empty in ("", "   ", None):
        service = AIService(make_settings(), client=FakeClient(reply=empty))
        with pytest.raises(EmptyResponseError):
            service.generate_reply([{"role": "user", "content": "oi"}])


def test_response_without_choices_raises_empty_error():
    client = FakeClient(response=SimpleNamespace(choices=[]))
    service = AIService(make_settings(), client=client)

    with pytest.raises(EmptyResponseError):
        service.generate_reply([{"role": "user", "content": "oi"}])


def test_api_failures_become_friendly_messages_without_leaking_the_key():
    cases = [
        (make_status_error(openai.AuthenticationError, 401), "chave de API foi recusada"),
        (make_status_error(openai.RateLimitError, 429), "Limite de requisições"),
        (make_status_error(openai.NotFoundError, 404), "OPENAI_MODEL"),
        (make_status_error(openai.InternalServerError, 500), "código 500"),
        (openai.APIConnectionError(request=make_request()), "Falha de conexão"),
        (openai.APITimeoutError(request=make_request()), "demorou demais"),
        (RuntimeError(f"erro estranho com {SECRET_KEY}"), "erro inesperado"),
    ]

    for error, expected_text in cases:
        service = AIService(make_settings(), client=FakeClient(error=error))
        with pytest.raises(AIServiceError) as info:
            service.generate_reply([{"role": "user", "content": "oi"}])

        assert expected_text in info.value.user_message
        assert SECRET_KEY not in info.value.user_message
        assert SECRET_KEY not in str(info.value)


def test_logs_do_not_contain_the_api_key():
    records = []

    class ListHandler(logging.Handler):
        def emit(self, record):
            records.append(record.getMessage())

    logger = logging.getLogger("src.ai_service")
    handler = ListHandler()
    logger.addHandler(handler)
    try:
        error = make_status_error(openai.AuthenticationError, 401)
        service = AIService(make_settings(), client=FakeClient(error=error))
        with pytest.raises(AIServiceError):
            service.generate_reply([{"role": "user", "content": "oi"}])
    finally:
        logger.removeHandler(handler)

    assert records  # o erro foi registrado...
    assert all(SECRET_KEY not in text for text in records)  # ...sem expor a chave


# ---------------------------------------------------------------- verificação de conexão


def test_check_connection_success():
    ok, message = AIService(make_settings(), client=FakeClient()).check_connection()

    assert ok is True
    assert message


def test_check_connection_failure_is_translated():
    error = make_status_error(openai.AuthenticationError, 401)
    ok, message = AIService(make_settings(), client=FakeClient(error=error)).check_connection()

    assert ok is False
    assert SECRET_KEY not in message
