"""Environment settings (``.env``): secrets and machine-specific values.

Business configuration lives in the YAML file; this module only holds what
must never be committed (credentials) or depends on the host (paths, level).
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from fechou.errors import ConfigError

SmtpSecurity = Literal["starttls", "ssl", "none"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,  # "SMTP_USER=" in .env means "not set"
        extra="ignore",
    )

    google_application_credentials: Path | None = None

    smtp_host: str | None = None
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_user: str | None = None
    smtp_password: SecretStr | None = None
    smtp_from: str | None = None
    smtp_security: SmtpSecurity = "starttls"
    smtp_timeout: float = Field(default=30.0, gt=0)

    telegram_bot_token: SecretStr | None = None
    telegram_chat_id: str | None = None

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    database_path: Path = Path("data/fechou.db")
    output_dir: Path = Path("out")


@dataclass(frozen=True, slots=True)
class SmtpSettings:
    """Validated subset needed to send e-mail."""

    host: str
    port: int
    sender: str
    security: SmtpSecurity
    timeout: float
    user: str | None = None
    password: SecretStr | None = None

    def __repr__(self) -> str:  # never print the password, even masked objects
        return (
            f"SmtpSettings(host={self.host!r}, port={self.port}, sender={self.sender!r}, "
            f"security={self.security!r}, user={self.user!r})"
        )


def load_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as exc:
        fields = ", ".join(str(error["loc"][0]).upper() for error in exc.errors() if error["loc"])
        raise ConfigError(
            f"Variáveis de ambiente inválidas: {fields}. Confira o .env (veja .env.example)."
        ) from None


def require_smtp(settings: Settings) -> SmtpSettings:
    """Fail fast, before reading any data, when e-mail delivery is not configured."""
    missing = [
        name
        for name, value in (("SMTP_HOST", settings.smtp_host), ("SMTP_FROM", settings.smtp_from))
        if not value
    ]
    if settings.smtp_user and settings.smtp_password is None:
        missing.append("SMTP_PASSWORD")
    if missing:
        raise ConfigError(
            "E-mail habilitado, mas faltam variáveis de ambiente: "
            + ", ".join(missing)
            + ". Preencha o .env (veja .env.example)."
        )
    assert settings.smtp_host is not None and settings.smtp_from is not None
    return SmtpSettings(
        host=settings.smtp_host,
        port=settings.smtp_port,
        sender=settings.smtp_from,
        security=settings.smtp_security,
        timeout=settings.smtp_timeout,
        user=settings.smtp_user,
        password=settings.smtp_password,
    )
