"""Google Sheets adapter tests with a fake gspread client (no network)."""

import datetime as dt
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import requests
from google.auth.exceptions import RefreshError, TransportError
from gspread.exceptions import APIError, SpreadsheetNotFound, WorksheetNotFound

from fechou.config import ColumnMapping
from fechou.errors import ConfigError, SourceError
from fechou.extract import google_sheets
from fechou.extract.google_sheets import (
    GoogleSheetsSource,
    SheetsConnection,
    cell_to_text,
    connect,
    header_row_of,
    serial_to_iso,
)
from fechou.transform.validate import validate_rows
from tests.conftest import HEADER

ACCOUNT = "fechou@projeto-teste.iam.gserviceaccount.com"
SHEET_ID = "1AbC-dEf_123"
# Serial dates (days since 1899-12-30), as the API returns them unformatted.
NOV_9 = (dt.date(2026, 11, 9) - dt.date(1899, 12, 30)).days
NOV_10 = NOV_9 + 1


def api_error(code: int, message: str, status: str = "") -> APIError:
    response = requests.Response()
    response.status_code = code
    response._content = json.dumps(
        {"error": {"code": code, "message": message, "status": status}}
    ).encode()
    return APIError(response)


class FakeWorksheet:
    def __init__(self, title: str, values: list[list[Any]]) -> None:
        self.title = title
        self.values = values
        self.calls: list[tuple[str | None, dict[str, Any]]] = []

    def get_values(self, range_name: str | None = None, **kwargs: Any) -> list[list[Any]]:
        self.calls.append((range_name, kwargs))
        return self.values


class FakeSpreadsheet:
    def __init__(self, *worksheets: FakeWorksheet) -> None:
        self._worksheets = worksheets

    def worksheet(self, title: str) -> FakeWorksheet:
        for sheet in self._worksheets:
            if sheet.title == title:
                return sheet
        raise WorksheetNotFound(title)

    def worksheets(self) -> list[FakeWorksheet]:
        return list(self._worksheets)


class FakeClient:
    def __init__(self, spreadsheet: FakeSpreadsheet | None = None, error: Exception | None = None):
        self.spreadsheet = spreadsheet
        self.error = error
        self.opened: list[str] = []

    def open_by_key(self, key: str) -> FakeSpreadsheet:
        self.opened.append(key)
        if self.error is not None:
            raise self.error
        assert self.spreadsheet is not None
        return self.spreadsheet


def make_source(
    client: FakeClient, *, worksheet: str = "Vendas", range_: str | None = None
) -> GoogleSheetsSource:
    return GoogleSheetsSource(
        source_id="loja",
        spreadsheet_id=SHEET_ID,
        worksheet=worksheet,
        range=range_,
        credentials_path=Path("sa.json"),
        date_header="Data",
        connector=lambda _path: SheetsConnection(client=client, account_email=ACCOUNT),
    )


def sheet_with(values: list[list[Any]], title: str = "Vendas") -> tuple[FakeClient, FakeWorksheet]:
    worksheet = FakeWorksheet(title, values)
    return FakeClient(FakeSpreadsheet(worksheet)), worksheet


class TestRead:
    def test_unformatted_values_become_valid_rows(self, columns: ColumnMapping) -> None:
        client, worksheet = sheet_with(
            [
                HEADER,
                [NOV_9, "Camiseta", "Vestuário", 2, 89.9, "Ana"],
                [NOV_10 + 0.75, "Boné", "Acessórios", 1, 98.89000000000001, "Bruno"],
                # Cells typed as text keep working (pt-BR formats).
                ["11/11/2026", "Meia", "", "3", "R$ 12,50", ""],
            ]
        )

        table = make_source(client).read()
        result = validate_rows(table, columns)

        assert client.opened == [SHEET_ID]
        assert result.invalid == ()
        assert [(r.date, r.quantity, r.unit_price) for r in result.valid] == [
            (dt.date(2026, 11, 9), 2, Decimal("89.90")),
            (dt.date(2026, 11, 10), 1, Decimal("98.89")),
            (dt.date(2026, 11, 11), 3, Decimal("12.50")),
        ]
        range_name, options = worksheet.calls[0]
        assert range_name is None
        assert options == {
            "value_render_option": "UNFORMATTED_VALUE",
            "date_time_render_option": "SERIAL_NUMBER",
            "pad_values": True,
        }

    def test_ragged_rows_are_padded_and_invalid_lines_are_numbered(
        self, columns: ColumnMapping
    ) -> None:
        client, _ = sheet_with(
            [
                HEADER,
                [NOV_9, "Camiseta", "Vestuário", 2, 89.9],  # trailing empty cell omitted
                [],  # blank line in the middle
                [NOV_9, "Boné", "Acessórios", 0, 10],
            ]
        )

        result = validate_rows(make_source(client).read(), columns)

        assert len(result.valid) == 1
        assert result.valid[0].seller is None
        assert [row.line for row in result.invalid] == [4]

    def test_range_and_leading_blank_rows_shift_line_numbers(self, columns: ColumnMapping) -> None:
        client, worksheet = sheet_with(
            [[], ["", ""], HEADER, [NOV_9, "Boné", "Acessórios", -1, 10, "Ana"]]
        )

        result = validate_rows(make_source(client, range_="A3:F").read(), columns)

        assert worksheet.calls[0][0] == "A3:F"
        # Header found on line 3 + 2 skipped blank rows = line 5; data on line 6.
        assert [row.line for row in result.invalid] == [6]

    def test_extra_columns_without_header_get_placeholder_names(self) -> None:
        client, _ = sheet_with([["Data", "Produto"], [NOV_9, "Boné", "sobra"]])

        table = make_source(client).read()

        assert list(table.columns) == ["Data", "Produto", "Unnamed: 2"]

    def test_empty_worksheet(self) -> None:
        client, _ = sheet_with([])

        with pytest.raises(SourceError, match="A aba está vazia"):
            make_source(client).read()

    def test_duplicate_headers_are_rejected(self) -> None:
        client, _ = sheet_with([["Data", "Produto", "Produto"]])

        with pytest.raises(SourceError, match="colunas repetidas: 'Produto'"):
            make_source(client).read()


class TestErrors:
    def test_worksheet_not_found_lists_available_tabs(self) -> None:
        client, _ = sheet_with([HEADER], title="Página1")

        with pytest.raises(SourceError, match=r"Aba 'Vendas' não encontrada.*'Página1'"):
            make_source(client).read()

    @pytest.mark.parametrize(
        ("error", "expected"),
        [
            (SpreadsheetNotFound(), f"não encontrada.*compartilhada com {ACCOUNT}"),
            (PermissionError(), f"{ACCOUNT} não tem acesso.*Leitor"),
            (api_error(403, "The caller does not have permission"), f"{ACCOUNT} não tem acesso"),
            (
                api_error(403, "Google Sheets API has not been used in project 123"),
                "Sheets API não está ativada",
            ),
            (api_error(400, "Unable to parse range: Vendas!ZZZZ1"), "Intervalo inválido"),
            (api_error(429, "Quota exceeded"), "Limite de requisições"),
            (api_error(503, "The service is currently unavailable"), "indisponível \\(erro 503\\)"),
            (api_error(404, "Requested entity was not found"), "API do Google Sheets \\(404\\)"),
            (RefreshError("invalid_grant"), "recusou a chave"),  # type: ignore[no-untyped-call]
            (TransportError("dns"), "Não foi possível conectar"),  # type: ignore[no-untyped-call]
            (requests.ConnectionError("down"), "Não foi possível conectar"),
        ],
    )
    def test_api_errors_become_pt_br_messages(self, error: Exception, expected: str) -> None:
        with pytest.raises(SourceError, match=expected):
            make_source(FakeClient(error=error)).read()


class TestConnect:
    def test_missing_key_file(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError, match="credenciais do Google não encontrado"):
            connect(tmp_path / "nao-existe.json")

    @pytest.mark.parametrize("content", ["isto não é json", '{"type": "service_account"}'])
    def test_invalid_key_file(self, tmp_path: Path, content: str) -> None:
        key = tmp_path / "sa.json"
        key.write_text(content, encoding="utf-8")

        with pytest.raises(ConfigError, match="não é uma chave JSON de conta de serviço"):
            connect(key)

    def test_default_connector_is_looked_up_at_read_time(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client, _ = sheet_with([HEADER])
        seen: list[Path] = []

        def fake_connect(path: Path) -> SheetsConnection:
            seen.append(path)
            return SheetsConnection(client=client, account_email=ACCOUNT)

        monkeypatch.setattr(google_sheets, "connect", fake_connect)
        source = GoogleSheetsSource(
            source_id="loja",
            spreadsheet_id=SHEET_ID,
            worksheet="Vendas",
            credentials_path=Path("sa.json"),
            date_header="Data",
        )

        assert list(source.read().columns) == HEADER
        assert seen == [Path("sa.json")]


class TestHelpers:
    @pytest.mark.parametrize(
        ("range_", "row"), [(None, 1), ("A:F", 1), ("A1:F", 1), ("B3:G500", 3), ("AA12", 12)]
    )
    def test_header_row_of(self, range_: str | None, row: int) -> None:
        assert header_row_of(range_) == row

    def test_serial_to_iso(self) -> None:
        assert serial_to_iso(45658) == "2025-01-01"
        assert serial_to_iso(45658.99) == "2025-01-01"
        assert serial_to_iso(1e12) is None

    @pytest.mark.parametrize(
        ("value", "is_date", "expected"),
        [
            (None, False, ""),
            ("  texto ", False, "  texto "),
            (2, False, "2"),
            (2.0, False, "2"),
            (89.9, False, "89.9"),
            (0.1 + 0.2, False, "0.3"),
            (1234567.5, False, "1234567.5"),
            (True, False, "VERDADEIRO"),
            (45658, True, "2025-01-01"),
            ("05/11/2026", True, "05/11/2026"),
            (1e12, True, "1000000000000"),  # out of range: left for the validator
        ],
    )
    def test_cell_to_text(self, value: Any, is_date: bool, expected: str) -> None:
        assert cell_to_text(value, is_date=is_date) == expected
