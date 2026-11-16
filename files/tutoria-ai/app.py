"""Tutoria AI — interface web (Streamlit).

Execute com:  streamlit run app.py
"""

from __future__ import annotations

import logging

import streamlit as st

from src.ai_service import AIService, AIServiceError
from src.chat_manager import ChatManager, Conversation, validate_user_input
from src.config import load_settings
from src.storage import ConversationStorage, StorageError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

APP_NAME = "Tutoria AI"
APP_TAGLINE = "Seu assistente pessoal de estudos."

# Texto fixo (nenhum conteúdo do usuário entra neste HTML).
CUSTOM_CSS = """
<style>
.block-container { max-width: 860px; padding-top: 2rem; }
section[data-testid="stSidebar"] .stButton > button { width: 100%; text-align: left; }
.tutoria-title { font-size: 2rem; font-weight: 700; margin: 0; line-height: 1.2; }
.tutoria-subtitle { color: #9aa4b2; margin: 0.15rem 0 0.75rem 0; }
@media (max-width: 640px) {
  .tutoria-title { font-size: 1.5rem; }
  .block-container { padding: 1rem 1rem 6rem 1rem; }
}
</style>
"""


# --------------------------------------------------------------------------- estado


def init_state() -> None:
    """Cria os objetos da aplicação uma única vez por sessão."""
    if "chat_manager" in st.session_state:
        return
    settings = load_settings()
    storage = ConversationStorage(settings.data_dir)
    st.session_state.settings = settings
    st.session_state.storage = storage
    st.session_state.chat_manager = ChatManager(storage, settings.max_context_messages)
    st.session_state.ai_service = AIService(settings)
    st.session_state.current_id = None  # None = conversa nova, ainda sem mensagens
    st.session_state.pending_reply = False  # True = falta pedir a resposta da IA
    st.session_state.confirm_clear = False
    st.session_state.error_message = None
    st.session_state.connection = {"state": "unchecked", "message": ""}


def get_current_conversation() -> Conversation | None:
    conversation_id = st.session_state.current_id
    if conversation_id is None:
        return None
    try:
        conversation = st.session_state.chat_manager.get_conversation(conversation_id)
    except StorageError as error:
        st.session_state.error_message = str(error)
        conversation = None
    if conversation is None:
        st.session_state.current_id = None
        st.session_state.pending_reply = False
    return conversation


def start_new_conversation() -> None:
    st.session_state.current_id = None
    st.session_state.pending_reply = False
    st.session_state.error_message = None


# --------------------------------------------------------------------------- sidebar


def render_sidebar() -> None:
    manager: ChatManager = st.session_state.chat_manager
    with st.sidebar:
        st.markdown("### 🎓 Tutoria AI")
        if st.button("➕ Nova conversa", key="new_conversation"):
            start_new_conversation()
            st.rerun()

        st.divider()
        st.caption("Conversas anteriores")
        try:
            conversations = manager.list_conversations()
        except StorageError as error:
            st.error(str(error))
            conversations = []

        skipped = st.session_state.storage.skipped_files
        if skipped:
            st.warning(
                f"{skipped} arquivo(s) de histórico estavam corrompidos e foram isolados "
                "(extensão .corrupted na pasta data/conversations)."
            )
        if not conversations:
            st.caption("Nenhuma conversa ainda.")

        for conversation in conversations:
            col_open, col_delete = st.columns([5, 1])
            is_current = conversation.id == st.session_state.current_id
            if col_open.button(
                conversation.title,
                key=f"open_{conversation.id}",
                type="primary" if is_current else "secondary",
            ):
                st.session_state.current_id = conversation.id
                st.session_state.pending_reply = False
                st.session_state.error_message = None
                st.rerun()
            if col_delete.button("🗑", key=f"delete_{conversation.id}", help="Excluir conversa"):
                delete_conversation(conversation.id)
                st.rerun()

        st.divider()
        render_clear_history(has_conversations=bool(conversations))


def delete_conversation(conversation_id: str) -> None:
    try:
        st.session_state.chat_manager.delete_conversation(conversation_id)
    except StorageError as error:
        st.session_state.error_message = str(error)
        return
    if st.session_state.current_id == conversation_id:
        start_new_conversation()


def render_clear_history(has_conversations: bool) -> None:
    if st.session_state.confirm_clear:
        st.warning("Apagar TODAS as conversas? Essa ação não pode ser desfeita.")
        col_yes, col_no = st.columns(2)
        if col_yes.button("Sim, apagar", key="clear_yes"):
            try:
                st.session_state.chat_manager.clear_history()
                start_new_conversation()
            except StorageError as error:
                st.session_state.error_message = str(error)
            st.session_state.confirm_clear = False
            st.rerun()
        if col_no.button("Cancelar", key="clear_no"):
            st.session_state.confirm_clear = False
            st.rerun()
    elif st.button("🧹 Limpar histórico", key="clear_history", disabled=not has_conversations):
        st.session_state.confirm_clear = True
        st.rerun()


# --------------------------------------------------------------------------- cabeçalho


CONNECTION_LABELS = {
    "missing": "🟠 API não configurada",
    "unchecked": "⚪ Conexão ainda não verificada",
    "ok": "🟢 Conexão com a IA funcionando",
    "error": "🔴 Falha na conexão com a IA",
}


def render_header() -> None:
    service: AIService = st.session_state.ai_service
    st.markdown(
        f'<p class="tutoria-title">🎓 {APP_NAME}</p>'
        f'<p class="tutoria-subtitle">{APP_TAGLINE}</p>',
        unsafe_allow_html=True,
    )

    col_status, col_button = st.columns([3, 1])
    if col_button.button("🔌 Verificar", key="check_connection", help="Testar a conexão com a IA"):
        with st.spinner("Verificando conexão..."):
            ok, message = service.check_connection()
        st.session_state.connection = {"state": "ok" if ok else "error", "message": message}

    state = "missing" if not service.is_configured else st.session_state.connection["state"]
    col_status.markdown(f"**{CONNECTION_LABELS[state]}**")
    message = st.session_state.connection["message"]
    if state == "error" and message:
        col_status.caption(message)


def render_setup_guidance() -> None:
    settings = st.session_state.settings
    for problem in settings.problems:
        st.warning(problem)
    if not st.session_state.ai_service.is_configured:
        st.info(
            "**Configure a IA para começar.**\n\n"
            "1. Copie o arquivo `.env.example` para `.env`.\n"
            "2. Preencha `OPENAI_API_KEY` (e `OPENAI_BASE_URL` / `OPENAI_MODEL` se usar "
            "outro provedor).\n"
            "3. Pare o app (Ctrl+C no terminal) e rode `streamlit run app.py` de novo.\n\n"
            "Enquanto isso o chat fica desativado: o Tutoria AI não simula respostas."
        )


# --------------------------------------------------------------------------- chat


def render_empty_state() -> None:
    st.markdown(
        "Comece uma conversa! Você pode perguntar, por exemplo:\n\n"
        "- *O que é uma função em Python?*\n"
        "- *Qual a diferença entre uma lista e um dicionário?*\n"
        "- *Como um LLM gera texto?*"
    )


def render_messages(conversation: Conversation) -> None:
    for message in conversation.messages:
        with st.chat_message(message.role):
            st.markdown(message.content)


def generate_pending_reply(conversation: Conversation) -> None:
    """Pede a resposta à IA, salva e atualiza a tela."""
    manager: ChatManager = st.session_state.chat_manager
    service: AIService = st.session_state.ai_service

    with st.chat_message("assistant"):
        with st.spinner("Pensando..."):
            try:
                reply = service.generate_reply(manager.build_context(conversation))
                manager.add_message(conversation, "assistant", reply)
                st.session_state.connection = {"state": "ok", "message": ""}
                st.session_state.error_message = None
            except AIServiceError as error:
                st.session_state.error_message = error.user_message
                st.session_state.connection = {"state": "error", "message": error.user_message}
            except StorageError as error:
                st.session_state.error_message = str(error)

    st.session_state.pending_reply = False
    st.rerun()


def handle_new_prompt(prompt: str, conversation: Conversation | None) -> None:
    """Valida a pergunta, salva e pede um novo ciclo da tela para chamar a IA."""
    manager: ChatManager = st.session_state.chat_manager
    try:
        text = validate_user_input(prompt, st.session_state.settings.max_input_chars)
        if conversation is None:
            conversation = manager.create_conversation()
        manager.add_message(conversation, "user", text)
    except (ValueError, StorageError) as error:
        st.session_state.error_message = str(error)
        st.rerun()
        return

    st.session_state.current_id = conversation.id
    st.session_state.pending_reply = True
    st.session_state.error_message = None
    st.rerun()


# --------------------------------------------------------------------------- principal


def main() -> None:
    st.set_page_config(page_title=APP_NAME, page_icon="🎓", layout="centered")
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    init_state()

    render_sidebar()
    render_header()
    render_setup_guidance()

    conversation = get_current_conversation()
    if conversation is None:
        render_empty_state()
    else:
        render_messages(conversation)
        if st.session_state.pending_reply:
            generate_pending_reply(conversation)

    if st.session_state.error_message:
        st.error(st.session_state.error_message)

    settings = st.session_state.settings
    prompt = st.chat_input(
        "Digite sua pergunta...",
        max_chars=settings.max_input_chars,
        disabled=not st.session_state.ai_service.is_configured,
    )
    if prompt:
        handle_new_prompt(prompt, conversation)


main()
