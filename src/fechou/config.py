"""YAML configuration (``config.yaml``) models and loader.

Secrets never live here: they come from environment variables (``.env``).
Relative paths inside the YAML are resolved against the config file's folder.
"""

import re
from pathlib import Path
from typing import Annotated, Any, Literal, Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)
from pydantic_core import ErrorDetails

from fechou.errors import ConfigError

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
_SOURCE_ID_RE = r"^[a-z0-9][a-z0-9_-]*$"


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CsvSourceConfig(_StrictModel):
    type: Literal["csv"]
    id: Annotated[str, Field(pattern=_SOURCE_ID_RE, max_length=64)]
    path: Path
    delimiter: Annotated[str, Field(min_length=1, max_length=1)] = ","
    # utf-8-sig also reads plain UTF-8 and strips the BOM Excel adds on export.
    encoding: str = "utf-8-sig"


class GoogleSheetsSourceConfig(_StrictModel):
    type: Literal["google_sheets"]
    id: Annotated[str, Field(pattern=_SOURCE_ID_RE, max_length=64)]
    spreadsheet_id: Annotated[str, Field(min_length=1)]
    worksheet: Annotated[str, Field(min_length=1)]
    range: str | None = None


SourceConfig = Annotated[
    CsvSourceConfig | GoogleSheetsSourceConfig,
    Field(discriminator="type"),
]

_NonEmptyStr = Annotated[str, Field(min_length=1)]


class ColumnMapping(_StrictModel):
    """Internal field name -> column header in the spreadsheet."""

    date: _NonEmptyStr
    product: _NonEmptyStr
    quantity: _NonEmptyStr
    unit_price: _NonEmptyStr
    category: _NonEmptyStr | None = None
    seller: _NonEmptyStr | None = None

    def mapped(self) -> dict[str, str]:
        """Only the fields that are mapped to a column."""
        return {field: column for field, column in self.model_dump().items() if column}


class ReportConfig(_StrictModel):
    title: str = "Relatório semanal de vendas"
    business_name: _NonEmptyStr
    timezone: str = "America/Sao_Paulo"
    empty_period_policy: Literal["send_empty", "skip"] = "send_empty"
    accent_color: str = "#1f6f5c"
    logo_path: Path | None = None

    @property
    def zone(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @field_validator("timezone")
    @classmethod
    def _check_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"fuso horário desconhecido: '{value}'") from exc
        return value

    @field_validator("accent_color")
    @classmethod
    def _check_color(cls, value: str) -> str:
        if not _HEX_COLOR_RE.match(value):
            raise ValueError("use uma cor hexadecimal no formato #RRGGBB")
        return value


class EmailDeliveryConfig(_StrictModel):
    enabled: bool = False
    to: list[str] = Field(default_factory=list)
    subject: str = "Fechamento da semana {start} a {end}"

    @field_validator("to")
    @classmethod
    def _check_addresses(cls, value: list[str]) -> list[str]:
        bad = [address for address in value if not _EMAIL_RE.match(address)]
        if bad:
            raise ValueError("e-mail inválido: " + ", ".join(bad))
        return value

    @field_validator("subject")
    @classmethod
    def _check_subject(cls, value: str) -> str:
        try:
            value.format(start="01/01/2026", end="07/01/2026", business="Loja")
        except (KeyError, IndexError, ValueError) as exc:
            raise ValueError(
                "assunto inválido; use apenas {start}, {end} e {business} "
                f"como variáveis (problema: {exc})"
            ) from None
        return value

    @model_validator(mode="after")
    def _require_recipients(self) -> Self:
        if self.enabled and not self.to:
            raise ValueError("e-mail habilitado sem destinatários em 'to'")
        return self


class TelegramDeliveryConfig(_StrictModel):
    enabled: bool = False


class DeliveryConfig(_StrictModel):
    email: EmailDeliveryConfig = Field(default_factory=EmailDeliveryConfig)
    telegram: TelegramDeliveryConfig = Field(default_factory=TelegramDeliveryConfig)


class AppConfig(_StrictModel):
    source: SourceConfig
    columns: ColumnMapping
    report: ReportConfig
    delivery: DeliveryConfig = Field(default_factory=DeliveryConfig)


# --- loading ------------------------------------------------------------------

_MESSAGES_PT = {
    "missing": "campo obrigatório ausente",
    "extra_forbidden": "campo desconhecido",
    "string_type": "deve ser texto",
    "bool_parsing": "deve ser true ou false",
    "bool_type": "deve ser true ou false",
    "list_type": "deve ser uma lista",
    "model_type": "deve ser um bloco de campos",
    "dict_type": "deve ser um bloco de campos",
    "string_too_short": "não pode ser vazio",
    "string_too_long": "texto longo demais",
    "string_pattern_mismatch": "use só letras minúsculas, números, '-' ou '_'",
    "union_tag_invalid": "tipo inválido (use 'csv' ou 'google_sheets')",
    "union_tag_not_found": "campo 'type' obrigatório (use 'csv' ou 'google_sheets')",
}


def _describe_error(error: ErrorDetails) -> str:
    location = ".".join(str(part) for part in error["loc"]) or "(raiz)"
    error_type = error["type"]
    if error_type == "value_error":
        message = str(error.get("ctx", {}).get("error", error["msg"]))
    elif error_type == "literal_error":
        message = f"valor inválido; opções: {error.get('ctx', {}).get('expected', '')}"
    else:
        message = _MESSAGES_PT.get(error_type, error["msg"])
    return f"  - {location}: {message}"


def _resolve(path: Path | None, base_dir: Path) -> Path | None:
    if path is None or path.is_absolute():
        return path
    return (base_dir / path).resolve()


def parse_config(data: Any, base_dir: Path) -> AppConfig:
    """Validate an already-parsed YAML document."""
    if not isinstance(data, dict):
        raise ConfigError("Configuração inválida: o arquivo deve ser um mapeamento YAML.")
    try:
        config = AppConfig.model_validate(data)
    except ValidationError as exc:
        details = "\n".join(_describe_error(error) for error in exc.errors())
        raise ConfigError(f"Configuração inválida:\n{details}") from None

    source = config.source
    if isinstance(source, CsvSourceConfig):
        resolved = _resolve(source.path, base_dir)
        assert resolved is not None
        source = source.model_copy(update={"path": resolved})
    report = config.report.model_copy(
        update={"logo_path": _resolve(config.report.logo_path, base_dir)}
    )
    return config.model_copy(update={"source": source, "report": report})


def load_config(path: Path) -> AppConfig:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ConfigError(f"Arquivo de configuração não encontrado: {path}") from None
    except OSError as exc:
        raise ConfigError(f"Não foi possível ler {path}: {exc.strerror}") from None
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ConfigError(f"YAML inválido em {path}: {exc}") from None
    return parse_config(data, base_dir=path.resolve().parent)
