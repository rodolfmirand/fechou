"""Source port: every data source returns a raw table of strings."""

from typing import Protocol

import pandas as pd

# A raw table keeps the spreadsheet headers and holds every cell as ``str``
# (empty cells are ""). Row ``i`` (0-based) is spreadsheet line
# ``header_line + 1 + i``. The header is on line 1 unless the source stores
# another line in ``table.attrs[HEADER_LINE_ATTR]`` (e.g. a Sheets range "A3:F").
RawTable = pd.DataFrame

HEADER_LINE = 1
HEADER_LINE_ATTR = "header_line"


def header_line(table: RawTable) -> int:
    return int(table.attrs.get(HEADER_LINE_ATTR, HEADER_LINE))


def line_number(row_index: int, header: int = HEADER_LINE) -> int:
    return row_index + header + 1


class Source(Protocol):
    @property
    def source_id(self) -> str: ...

    @property
    def kind(self) -> str: ...

    def read(self) -> RawTable:
        """Read the whole table. Raises ``SourceError`` on failure."""
        ...
