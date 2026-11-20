from pathlib import Path

import pytest

from fechou.errors import ConfigError
from fechou.settings import Settings, load_settings, require_smtp


def test_defaults(clean_env: Path) -> None:
    settings = load_settings()

    assert settings.smtp_host is None
    assert settings.smtp_port == 587
    assert settings.smtp_security == "starttls"
    assert settings.database_path == Path("data/fechou.db")
    assert settings.log_level == "INFO"


def test_reads_dotenv_and_ignores_empty_values(clean_env: Path) -> None:
    (clean_env / ".env").write_text(
        "SMTP_HOST=smtp.exemplo.com\nSMTP_PORT=465\nSMTP_SECURITY=ssl\n"
        'SMTP_USER=\nSMTP_FROM="Fechou <r@exemplo.com>"\nTELEGRAM_BOT_TOKEN=\n',
        encoding="utf-8",
    )

    settings = load_settings()

    assert settings.smtp_host == "smtp.exemplo.com"
    assert settings.smtp_port == 465
    assert settings.smtp_security == "ssl"
    assert settings.smtp_user is None  # "SMTP_USER=" means not set
    assert settings.smtp_from == "Fechou <r@exemplo.com>"
    assert settings.telegram_bot_token is None


def test_environment_overrides_dotenv(clean_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (clean_env / ".env").write_text("SMTP_HOST=do-arquivo\n", encoding="utf-8")
    monkeypatch.setenv("SMTP_HOST", "do-ambiente")

    assert load_settings().smtp_host == "do-ambiente"


def test_invalid_values_name_the_variable(clean_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SMTP_PORT", "abc")
    monkeypatch.setenv("SMTP_SECURITY", "tls")

    with pytest.raises(ConfigError, match="SMTP_PORT, SMTP_SECURITY"):
        load_settings()


def test_secrets_are_not_exposed(clean_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SMTP_HOST", "smtp.exemplo.com")
    monkeypatch.setenv("SMTP_FROM", "r@exemplo.com")
    monkeypatch.setenv("SMTP_USER", "usuario")
    monkeypatch.setenv("SMTP_PASSWORD", "senha-super-secreta")

    settings = load_settings()
    smtp = require_smtp(settings)

    assert "senha-super-secreta" not in repr(settings)
    assert "senha-super-secreta" not in repr(smtp)
    assert smtp.password is not None
    assert smtp.password.get_secret_value() == "senha-super-secreta"


@pytest.mark.parametrize(
    ("env", "missing"),
    [
        ({}, "SMTP_HOST, SMTP_FROM"),
        ({"SMTP_HOST": "h"}, "SMTP_FROM"),
        ({"SMTP_HOST": "h", "SMTP_FROM": "f@x.com", "SMTP_USER": "u"}, "SMTP_PASSWORD"),
    ],
)
def test_require_smtp_lists_missing_variables(
    clean_env: Path, monkeypatch: pytest.MonkeyPatch, env: dict[str, str], missing: str
) -> None:
    for name, value in env.items():
        monkeypatch.setenv(name, value)

    with pytest.raises(ConfigError) as info:
        require_smtp(Settings())

    assert f"faltam variáveis de ambiente: {missing}." in str(info.value)


def test_require_smtp_without_authentication(
    clean_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SMTP_HOST", "localhost")
    monkeypatch.setenv("SMTP_PORT", "1025")
    monkeypatch.setenv("SMTP_SECURITY", "none")
    monkeypatch.setenv("SMTP_FROM", "r@exemplo.com")

    smtp = require_smtp(Settings())

    assert (smtp.host, smtp.port, smtp.security, smtp.user) == ("localhost", 1025, "none", None)
