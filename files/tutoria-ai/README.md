# 🎓 Tutoria AI

> Seu assistente pessoal de estudos: um chat com IA que atua como professor particular de tecnologia.

O Tutoria AI responde perguntas sobre Python, programação, engenharia de software, IA, machine learning, LLMs, APIs e desenvolvimento web, explicando de forma didática, com exemplos e passo a passo. As conversas ficam salvas em arquivos JSON locais.

Projeto de portfólio feito com **Python + Streamlit + SDK da OpenAI** (funciona com qualquer provedor compatível com a API da OpenAI).

## Funcionalidades

- Chat com respostas geradas por um LLM real (nada de respostas simuladas)
- Histórico de conversas em JSON, com id, título, data de criação e mensagens (autor, conteúdo, data/hora)
- Contexto da conversa: as últimas *N* mensagens são enviadas à IA (configurável)
- Nova conversa, lista de conversas anteriores, excluir uma conversa, limpar todo o histórico (com confirmação)
- Indicador de conexão que **só mostra "conectado" depois de verificar** (botão *Verificar* ou primeira resposta bem-sucedida)
- Sem chave de API: o app explica como configurar e desativa o chat (não finge respostas)
- Tratamento de erros: chave ausente ou inválida, falha de conexão, limite de requisições, resposta vazia, erro inesperado e histórico corrompido — sem expor chaves nas mensagens nem nos logs
- Tema escuro por padrão

## Tecnologias

| Tecnologia | Uso |
|---|---|
| Python 3.11+ | Linguagem principal |
| Streamlit | Interface web |
| OpenAI Python SDK | Comunicação com a API de IA |
| python-dotenv | Variáveis de ambiente (`.env`) |
| JSON | Armazenamento local do histórico |
| Pytest | Testes automatizados |

## Como executar (Windows + VS Code)

Pré-requisito: [Python 3.11 ou superior](https://www.python.org/downloads/) (marque *Add Python to PATH* na instalação). Confira com `python --version`.

1. Abra a pasta `tutoria-ai` no VS Code (*File → Open Folder*) e abra o terminal (`Ctrl+'`).

2. Crie o ambiente virtual:

   ```
   python -m venv .venv
   ```

3. Ative o ambiente virtual:

   ```
   .venv\Scripts\activate
   ```

   > Se o PowerShell bloquear com erro de "execução de scripts desabilitada", rode uma vez
   > `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` e tente de novo, ou use o terminal *Command Prompt*.
   > Quando funcionar, o terminal mostra `(.venv)` no começo da linha.

4. Instale as dependências:

   ```
   pip install -r requirements.txt
   ```

5. Configure as variáveis de ambiente: copie `.env.example` para `.env` e preencha (veja a seção abaixo):

   ```
   copy .env.example .env
   ```

6. Execute a aplicação:

   ```
   streamlit run app.py
   ```

   O navegador abrirá em `http://localhost:8501`.

7. Execute os testes:

   ```
   pytest -v
   ```

## Configurando a API

Edite o arquivo `.env`:

| Variável | Obrigatória | Descrição |
|---|---|---|
| `OPENAI_API_KEY` | Sim | Chave de API do seu provedor |
| `OPENAI_BASE_URL` | Não | Endereço do provedor. Sem ela, usa a OpenAI |
| `OPENAI_MODEL` | Não | Nome do modelo (padrão: `gpt-4o-mini`) |
| `MAX_CONTEXT_MESSAGES` | Não | Quantas mensagens anteriores vão como contexto (1 a 50, padrão 10) |

Exemplo com a própria OpenAI:

```
OPENAI_API_KEY=<sua chave>
OPENAI_MODEL=gpt-4o-mini
```

Exemplo com outro provedor compatível (confira no site dele o endereço e os nomes de modelo):

```
OPENAI_API_KEY=<chave do provedor>
OPENAI_BASE_URL=https://openrouter.ai/api/v1
OPENAI_MODEL=<nome do modelo no provedor>
```

**Custos e limites:** você precisa de uma chave válida, e cada pergunta consome tokens do seu plano no provedor. Isso pode gerar cobrança, e cada provedor aplica limites próprios de requisições e de crédito (quando atingidos, o app mostra um aviso). Consulte a página de preços do provedor escolhido. Alguns oferecem camada gratuita limitada, e ferramentas locais como o Ollama não cobram por token. Quanto maior `MAX_CONTEXT_MESSAGES`, mais tokens cada pergunta usa.

Depois de mudar o `.env`, **reinicie** o app (`Ctrl+C` e `streamlit run app.py`).

## Arquitetura

```
tutoria-ai/
├── app.py                 # Interface Streamlit e controle das interações
├── requirements.txt
├── pytest.ini
├── .env.example           # Modelo das variáveis (sem credenciais reais)
├── .gitignore
├── .streamlit/config.toml # Tema escuro
├── src/
│   ├── config.py          # Lê e valida as variáveis de ambiente
│   ├── ai_service.py      # Fala com a API de IA e traduz erros
│   ├── chat_manager.py    # Conversas, mensagens e contexto enviado à IA
│   └── storage.py         # Salva/carrega/exclui conversas em JSON
├── data/                  # Histórico local (ignorado pelo Git)
└── tests/                 # Testes com Pytest (sem API real)
```

Fluxo de uma pergunta:

1. `app.py` valida o texto digitado (`validate_user_input`).
2. `chat_manager` salva a mensagem na conversa (via `storage`).
3. `chat_manager.build_context` separa as últimas *N* mensagens.
4. `ai_service.generate_reply` envia instruções do professor + contexto ao modelo.
5. A resposta é salva e exibida. Em caso de erro, o usuário vê uma mensagem clara em português.

Decisões de projeto:

- **Um arquivo JSON por conversa** (`data/conversations/<id>.json`): fica fácil excluir uma conversa, e um arquivo corrompido não afeta as outras. Arquivos inválidos são renomeados para `.json.corrupted`.
- **Gravação segura**: escreve num arquivo temporário e troca no final, evitando arquivo pela metade.
- **Id validado** (32 caracteres hexadecimais) antes de virar nome de arquivo, o que impede "path traversal".
- **Erros do provedor nunca são mostrados em texto bruto**, pois podem conter trechos da chave. O app mostra mensagens próprias e registra só o tipo do erro.

## Testes

```
pytest -v
```

Os testes **não acessam a internet nem consomem créditos**: o `ai_service` recebe um cliente falso no lugar do cliente real. Cobrem criação de conversa, mensagens, salvar/carregar/excluir, histórico inexistente, JSON inválido, chave ausente, falhas da API (autenticação, limite, conexão, timeout, erro inesperado), resposta vazia, resposta simulada, e a garantia de que a chave não aparece em mensagens nem logs.

## Segurança

- Chaves só vêm de variáveis de ambiente; `.env` está no `.gitignore`
- Nenhum `eval()`/`exec()`; o texto do usuário nunca é executado
- O conteúdo das mensagens é renderizado pelo Streamlit sem HTML bruto
- Logs registram apenas o tipo do erro e o código HTTP
- A pasta `data/` é ignorada pelo Git (o histórico pode conter dados pessoais)

## Limitações conhecidas

- O histórico fica em **texto puro** no seu computador (sem criptografia nem login); o app é pensado para uso pessoal e local
- A lista de conversas relê os arquivos a cada interação; para milhares de conversas, seria preciso um banco de dados
- Sem *streaming*: a resposta aparece inteira de uma vez, depois de pronta
- A resposta da IA não é interrompida se o usuário trocar de conversa durante a espera
- O contexto é cortado por **número de mensagens**, não por tokens; mensagens muito longas podem estourar o limite do modelo
- O botão *Verificar* usa a lista de modelos do provedor; alguns provedores não oferecem essa rota (o app avisa; o chat pode funcionar mesmo assim)
- Se a gravação da resposta no disco falhar depois de a IA responder, a resposta é perdida

## Ideias de melhorias futuras

- Respostas em *streaming*
- Cortar contexto por tokens e resumir conversas longas
- Exportar conversas (Markdown/PDF) e renomear conversas
- Banco de dados (SQLite) e login para uso multiusuário
- Citar fontes com RAG sobre materiais de estudo
- Testes de interface com `streamlit.testing.v1.AppTest` e integração contínua (GitHub Actions)
