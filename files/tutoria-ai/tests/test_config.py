from pathlib import Path

from src.config import DEFAULT_MODEL, load_settings


def test_defaults_without_environment():
    settings = load_settings({})

    assert settings.has_api_key is False
    assert settings.base_url is None
    assert settings.model == DEFAULT_MODEL
    assert settings.max_context_messages == 10
    assert settings.problems == ()


def test_reads_environment_variables():
    env = {
        "OPENAI_API_KEY": "chave-de-teste-123",
        "OPENAI_BASE_URL": "https://exemplo.com/v1",
        "OPENAI_MODEL": "modelo-x",
        "MAX_CONTEXT_MESSAGES": "4",
    }
    settings = load_settings(env)

    assert settings.has_api_key is True
    assert settings.base_url == "https://exemplo.com/v1"
    assert settings.model == "modelo-x"
    assert settings.max_context_messages == 4


def test_example_placeholder_is_not_a_real_key():
    settings = load_settings({"OPENAI_API_KEY": "sua-chave-de-api-aqui"})

    assert settings.has_api_key is False


def test_invalid_values_fall_back_to_defaults_and_report_problems():
    settings = load_settings({"MAX_CONTEXT_MESSAGES": "abc", "OPENAI_BASE_URL": "ftp://x"})

    assert settings.max_context_messages == 10
    assert settings.base_url is None
    assert len(settings.problems) == 2


def test_context_limit_out_of_range_is_rejected():
    settings = load_settings({"MAX_CONTEXT_MESSAGES": "0"})

    assert settings.max_context_messages == 10
    assert len(settings.problems) == 1


def test_repr_does_not_expose_api_key():
    settings = load_settings({"OPENAI_API_KEY": "segredo-super-secreto"})

    assert "segredo-super-secreto" not in repr(settings)


def test_custom_data_dir_relative_is_inside_project():
    settings = load_settings({"TUTORIA_DATA_DIR": "meus-dados"})

    assert settings.data_dir.is_absolute()
    assert settings.data_dir.name == "meus-dados"
    assert isinstance(settings.data_dir, Path)
