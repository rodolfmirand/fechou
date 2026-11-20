"""Data sources (ports and adapters)."""

from pathlib import Path

from fechou.config import AppConfig, CsvSourceConfig
from fechou.errors import ConfigError
from fechou.extract.base import Source
from fechou.extract.csv_source import CsvSource
from fechou.extract.google_sheets import GoogleSheetsSource

__all__ = ["CsvSource", "GoogleSheetsSource", "Source", "build_source"]


def build_source(config: AppConfig, credentials_path: Path | None = None) -> Source:
    """Build the configured source. ``credentials_path`` is only used by Google Sheets.

    Raises ``ConfigError`` early (before any read) when Sheets has no credentials.
    """
    source = config.source
    if isinstance(source, CsvSourceConfig):
        return CsvSource(
            source_id=source.id,
            path=Path(source.path),
            delimiter=source.delimiter,
            encoding=source.encoding,
        )
    if credentials_path is None:
        raise ConfigError(
            "A fonte 'google_sheets' precisa da chave da conta de serviço: defina "
            "GOOGLE_APPLICATION_CREDENTIALS no .env (veja .env.example)."
        )
    return GoogleSheetsSource(
        source_id=source.id,
        spreadsheet_id=source.spreadsheet_id,
        worksheet=source.worksheet,
        range=source.range,
        credentials_path=credentials_path,
        date_header=config.columns.date,
    )
