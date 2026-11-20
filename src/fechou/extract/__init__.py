"""Data sources (ports and adapters)."""

from pathlib import Path

from fechou.config import AppConfig, CsvSourceConfig
from fechou.errors import SourceError
from fechou.extract.base import Source
from fechou.extract.csv_source import CsvSource

__all__ = ["CsvSource", "Source", "build_source"]


def build_source(config: AppConfig) -> Source:
    source = config.source
    if isinstance(source, CsvSourceConfig):
        return CsvSource(
            source_id=source.id,
            path=Path(source.path),
            delimiter=source.delimiter,
            encoding=source.encoding,
        )
    raise SourceError("Fonte do tipo 'google_sheets' ainda não está disponível nesta versão.")
