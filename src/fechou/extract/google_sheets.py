"""Google Sheets source (read-only, service account).

Cells are read **unformatted** so the result does not depend on the
spreadsheet locale: numbers arrive as numbers (``89.9``, never ``"R$ 89,90"``
or ``"$89.90"``) and dates as serial numbers, which are converted to ISO dates
in the date column. A pt-BR sheet showing ``05/11/2026`` and an en-US sheet
showing ``11/5/2026`` both yield ``2026-11-05``. Cells typed as text are kept
as-is and go through the usual validation.
"""

import datetime as dt
import math
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from http import HTTPStatus
from pathlib import Path
from typing import Any, Protocol

import gspread
import pandas as pd
import requests
from google.auth.exceptions import RefreshError, TransportError
from google.oauth2.service_account import Credentials
from gspread.exceptions import APIError, SpreadsheetNotFound, WorksheetNotFound
from gspread.utils import DateTimeOption, ValueRenderOption

from fechou.errors import ConfigError, SourceError
from fechou.extract.base import HEADER_LINE_ATTR, RawTable

READONLY_SCOPES = ("https://www.googleapis.com/auth/spreadsheets.readonly",)
REQUEST_TIMEOUT = 60.0  # seconds per HTTP request
SHEETS_EPOCH = dt.date(1899, 12, 30)  # day 0 of Google Sheets serial dates

_RANGE_START_ROW_RE = re.compile(r"^[A-Z]+(\d+)")


class SheetsClient(Protocol):
    """The part of ``gspread.Client`` used here (lets tests inject a fake)."""

    def open_by_key(self, key: str) -> Any: ...


@dataclass(frozen=True, slots=True)
class SheetsConnection:
    client: SheetsClient
    account_email: str


class _RetryingHTTPClient(gspread.BackOffHTTPClient):
    """Retries 408/429/5xx with waits of 2, 4 and 8 s (same policy as delivery)."""

    _MAX_BACKOFF = 8


def connect(credentials_path: Path) -> SheetsConnection:
    """Authenticate with a service account key file (read-only scope)."""
    try:
        credentials = Credentials.from_service_account_file(  # type: ignore[no-untyped-call]
            str(credentials_path), scopes=READONLY_SCOPES
        )
    except FileNotFoundError:
        raise ConfigError(
            f"Arquivo de credenciais do Google não encontrado: {credentials_path}. "
            "Confira GOOGLE_APPLICATION_CREDENTIALS no .env."
        ) from None
    except (ValueError, KeyError):
        raise ConfigError(
            f"{credentials_path} não é uma chave JSON de conta de serviço válida. "
            "Baixe a chave em Google Cloud > IAM > Contas de serviço > Chaves."
        ) from None
    except OSError as exc:
        raise ConfigError(f"Não foi possível ler {credentials_path}: {exc.strerror}") from None
    client = gspread.Client(auth=credentials, http_client=_RetryingHTTPClient)
    client.set_timeout(REQUEST_TIMEOUT)
    return SheetsConnection(client=client, account_email=str(credentials.service_account_email))


def header_row_of(range_: str | None) -> int:
    """Spreadsheet line where the range starts ("B3:G" -> 3; "A:F" or None -> 1)."""
    match = _RANGE_START_ROW_RE.match(range_ or "")
    return int(match.group(1)) if match else 1


def serial_to_iso(value: float) -> str | None:
    """Google Sheets serial date (days since 1899-12-30) -> ``YYYY-MM-DD``."""
    try:
        return (SHEETS_EPOCH + dt.timedelta(days=math.floor(value))).isoformat()
    except (OverflowError, ValueError):
        return None


def cell_to_text(value: Any, *, is_date: bool = False) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):  # checkbox; bool is an int subclass
        return "VERDADEIRO" if value else "FALSO"
    if isinstance(value, int | float):
        if is_date and (iso := serial_to_iso(value)) is not None:
            return iso
        # Round away binary noise from formulas (98.89000000000001 -> "98.89")
        # without ever using scientific notation.
        return f"{round(value, 9):.9f}".rstrip("0").rstrip(".")
    return str(value)


def values_to_table(
    values: Sequence[Sequence[Any]], *, first_line: int, date_header: str
) -> RawTable:
    """Turn the API's list of rows into a raw table of strings.

    Leading blank rows are skipped (the header is the first non-blank row);
    rows are padded to the header width.
    """
    rows = [list(row) for row in values]
    offset = 0
    while offset < len(rows) and all(cell_to_text(cell).strip() == "" for cell in rows[offset]):
        offset += 1
    if offset == len(rows):
        raise SourceError("A aba está vazia: nenhum cabeçalho encontrado.")

    header = [cell_to_text(cell).strip() for cell in rows[offset]]
    body = rows[offset + 1 :]
    width = max([len(header), *(len(row) for row in body)])
    header += [""] * (width - len(header))
    header = [name or f"Unnamed: {index}" for index, name in enumerate(header)]
    duplicates = sorted({name for name in header if header.count(name) > 1})
    if duplicates:
        raise SourceError(
            "Cabeçalho com colunas repetidas: "
            + ", ".join(f"'{name}'" for name in duplicates)
            + ". Renomeie para que cada coluna tenha um nome único."
        )

    date_index = header.index(date_header) if date_header in header else -1
    table = pd.DataFrame(
        [
            [
                cell_to_text(row[index] if index < len(row) else "", is_date=index == date_index)
                for index in range(width)
            ]
            for row in body
        ],
        columns=pd.Index(header),
        dtype=str,
    )
    table.attrs[HEADER_LINE_ATTR] = first_line + offset
    return table


def _api_error_message(error: APIError, account_email: str) -> str:
    code = error.code
    message = str(error.error.get("message", ""))
    if code == HTTPStatus.FORBIDDEN and ("has not been used" in message or "disabled" in message):
        return (
            "A Google Sheets API não está ativada no projeto da conta de serviço. "
            "Ative em Google Cloud > APIs e serviços > Biblioteca > Google Sheets API."
        )
    if code == HTTPStatus.FORBIDDEN:
        return _not_shared_message(account_email)
    if code == HTTPStatus.BAD_REQUEST and "parse range" in message:
        return "Intervalo inválido para esta aba. Confira 'range' na configuração."
    if code == HTTPStatus.TOO_MANY_REQUESTS:
        return "Limite de requisições do Google atingido. Tente de novo em alguns minutos."
    if code >= HTTPStatus.INTERNAL_SERVER_ERROR:
        return f"O Google Sheets está indisponível (erro {code}). Tente de novo mais tarde."
    return f"Erro da API do Google Sheets ({code}): {message}"


def _not_shared_message(account_email: str) -> str:
    return (
        f"A conta de serviço {account_email} não tem acesso à planilha. "
        "Compartilhe a planilha com esse e-mail (permissão de Leitor)."
    )


@dataclass(frozen=True, slots=True)
class GoogleSheetsSource:
    source_id: str
    spreadsheet_id: str
    worksheet: str
    credentials_path: Path
    date_header: str
    range: str | None = None
    # None means the real ``connect`` (looked up at read time, so tests can patch it).
    connector: Callable[[Path], SheetsConnection] | None = field(default=None, repr=False)
    kind: str = "google_sheets"

    def read(self) -> RawTable:
        connection = (self.connector or connect)(self.credentials_path)
        try:
            values = self._fetch(connection)
        except SpreadsheetNotFound:
            raise SourceError(
                f"Planilha '{self.spreadsheet_id}' não encontrada. Confira 'spreadsheet_id' "
                f"e se ela foi compartilhada com {connection.account_email}."
            ) from None
        except PermissionError:  # gspread maps HTTP 403 on open to PermissionError
            raise SourceError(_not_shared_message(connection.account_email)) from None
        except APIError as exc:
            raise SourceError(_api_error_message(exc, connection.account_email)) from None
        except RefreshError:
            raise SourceError(
                "O Google recusou a chave da conta de serviço (chave revogada, conta "
                "desativada ou relógio do computador errado). Gere uma nova chave."
            ) from None
        except (TransportError, requests.RequestException):
            raise SourceError(
                "Não foi possível conectar ao Google Sheets. Verifique a internet e tente de novo."
            ) from None
        return values_to_table(
            values, first_line=header_row_of(self.range), date_header=self.date_header
        )

    def _fetch(self, connection: SheetsConnection) -> Sequence[Sequence[Any]]:
        spreadsheet = connection.client.open_by_key(self.spreadsheet_id)
        try:
            worksheet = spreadsheet.worksheet(self.worksheet)
        except WorksheetNotFound:
            titles = ", ".join(f"'{sheet.title}'" for sheet in spreadsheet.worksheets())
            raise SourceError(
                f"Aba '{self.worksheet}' não encontrada na planilha. "
                f"Abas disponíveis: {titles or '(nenhuma)'}."
            ) from None
        values: Sequence[Sequence[Any]] = worksheet.get_values(
            self.range,
            value_render_option=ValueRenderOption.unformatted,
            date_time_render_option=DateTimeOption.serial_number,
            pad_values=True,
        )
        return values
