from pydantic import SecretStr, ValidationError

from crypto_agent.config import Settings

VALID_SETTINGS = {
    "OPENAI_API_KEY": "test-openai-key",
    "FREECRYPTO_API_KEY": "test-freecrypto-key",
    "NEWS_API_KEY": "test-news-key",
}


def test_settings_accept_valid_credentials() -> None:
    settings = Settings(_env_file=None, **VALID_SETTINGS)

    assert settings.openai_model == "gpt-4o-mini"
    assert settings.request_timeout_seconds == 15
    assert settings.max_http_retries == 2


def test_secrets_are_masked_in_repr() -> None:
    settings = Settings(_env_file=None, **VALID_SETTINGS)

    assert "test-openai-key" not in repr(settings)
    assert isinstance(settings.openai_api_key, SecretStr)


def test_placeholder_credentials_are_rejected() -> None:
    invalid = {**VALID_SETTINGS, "NEWS_API_KEY": "your_newsapi_key"}

    try:
        Settings(_env_file=None, **invalid)
    except ValidationError as error:
        assert "A real API credential is required" in str(error)
    else:
        raise AssertionError("Placeholder credentials must fail validation")


def test_runtime_limits_are_bounded() -> None:
    invalid = {**VALID_SETTINGS, "MAX_HTTP_RETRIES": 9}

    try:
        Settings(_env_file=None, **invalid)
    except ValidationError:
        pass
    else:
        raise AssertionError("Retry counts above the configured limit must fail")
