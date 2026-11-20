"""Source port: every data source returns a raw table of strings."""

from typing import Protocol

import pandas as pd

# A raw table keeps the spreadsheet headers and holds every cell as ``str``
# (empty cells are ""). Row ``i`` (0-based) is spreadsheet line ``i + 2``,
# because line 1 is the header.
RawTable = pd.DataFrame

HEADER_LINE = 1


def line_number(row_index: int) -> int:
    return row_index + HEADER_LINE + 1


class Source(Protocol):
    @property
    def source_id(self) -> str: ...

    @property
    def kind(self) -> str: ...

    def read(self) -> RawTable:
        """Read the whole table. Raises ``SourceError`` on failure."""
        ...
