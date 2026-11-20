"""CSV source (used by demo mode and for local files)."""

import re
import warnings
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from fechou.errors import SourceError
from fechou.extract.base import RawTable

_FIELD_COUNT_RE = re.compile(r"Expected (\d+) fields in line (\d+), saw (\d+)")


def _describe(error: pd.errors.ParserError) -> str:
    match = _FIELD_COUNT_RE.search(str(error))
    if match:
        expected, line, seen = match.groups()
        return f"a linha {line} tem {seen} campos, mas o cabeçalho tem {expected}"
    return str(error).strip()


@dataclass(frozen=True, slots=True)
class CsvSource:
    source_id: str
    path: Path
    delimiter: str = ","
    encoding: str = "utf-8-sig"
    kind: str = "csv"

    def read(self) -> RawTable:
        try:
            with warnings.catch_warnings():
                # With index_col=False pandas only *warns* (and drops data) when a
                # row has more fields than the header; treat that as malformed.
                warnings.simplefilter("error", pd.errors.ParserWarning)
                table = pd.read_csv(
                    self.path,
                    sep=self.delimiter,
                    encoding=self.encoding,
                    dtype=str,
                    keep_default_na=False,
                    # Never infer an index from extra leading fields (silent shift).
                    index_col=False,
                    # Keep blank lines so row indexes still match spreadsheet lines;
                    # the validator ignores fully blank rows.
                    skip_blank_lines=False,
                )
        except FileNotFoundError:
            raise SourceError(f"Arquivo CSV não encontrado: {self.path}") from None
        except pd.errors.EmptyDataError:
            raise SourceError(f"Arquivo CSV vazio: {self.path}") from None
        except UnicodeDecodeError:
            raise SourceError(
                f"Não foi possível ler {self.path} como {self.encoding}. "
                "Salve o arquivo em UTF-8 ou ajuste 'encoding' na configuração."
            ) from None
        except pd.errors.ParserWarning:
            raise SourceError(
                f"CSV malformado em {self.path}: há linha com mais colunas que o cabeçalho. "
                f"Confira o delimitador (atual: '{self.delimiter}')."
            ) from None
        except pd.errors.ParserError as exc:
            raise SourceError(f"CSV malformado em {self.path}: {_describe(exc)}") from None
        except OSError as exc:
            raise SourceError(f"Não foi possível ler {self.path}: {exc.strerror}") from None

        table.columns = pd.Index([str(column).strip() for column in table.columns])
        return table
