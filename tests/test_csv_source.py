from pathlib import Path

import pytest

from fechou.config import ColumnMapping
from fechou.errors import SourceError
from fechou.extract.csv_source import CsvSource
from fechou.transform.validate import validate_rows


def _write(path: Path, text: str, encoding: str = "utf-8") -> Path:
    path.write_bytes(text.encode(encoding))
    return path


def test_reads_every_cell_as_text(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "vendas.csv",
        'Data,Produto,Qtd,Preço\n12/11/2026,Boné,002,"44,90"\n13/11/2026,Chinelo,,\n',
    )

    table = CsvSource("loja", path).read()

    assert list(table.columns) == ["Data", "Produto", "Qtd", "Preço"]
    assert table.iloc[0].tolist() == ["12/11/2026", "Boné", "002", "44,90"]
    # Empty cells stay as "" (no NaN), so the validator sees exactly what was typed.
    assert table.iloc[1].tolist() == ["13/11/2026", "Chinelo", "", ""]


def test_custom_delimiter_bom_and_header_whitespace(tmp_path: Path, columns: ColumnMapping) -> None:
    path = _write(
        tmp_path / "excel.csv",
        "Data; Produto ;Categoria;Qtd;Preço;Vendedor\n"
        "12/11/2026;Calça jeans;Vestuário;1;1.159,90;Ana\n",
        encoding="utf-8-sig",
    )

    table = CsvSource("loja", path, delimiter=";").read()
    result = validate_rows(table, columns)

    assert table.columns[0] == "Data"  # BOM stripped
    assert table.columns[1] == "Produto"  # whitespace stripped
    assert len(result.valid) == 1
    assert str(result.valid[0].unit_price) == "1159.90"


def test_blank_lines_keep_spreadsheet_line_numbers(tmp_path: Path, columns: ColumnMapping) -> None:
    path = _write(
        tmp_path / "vendas.csv",
        "Data,Produto,Categoria,Qtd,Preço,Vendedor\n"
        "12/11/2026,Boné,,1,10,\n"
        "\n"
        "12/11/2026,Boné,,0,10,\n",
    )

    result = validate_rows(CsvSource("loja", path).read(), columns)

    assert result.total == 2
    assert result.invalid[0].line == 4


def test_missing_file(tmp_path: Path) -> None:
    with pytest.raises(SourceError, match="não encontrado"):
        CsvSource("loja", tmp_path / "nada.csv").read()


def test_empty_file(tmp_path: Path) -> None:
    path = _write(tmp_path / "vazio.csv", "")
    with pytest.raises(SourceError, match="vazio"):
        CsvSource("loja", path).read()


def test_wrong_encoding(tmp_path: Path) -> None:
    path = _write(tmp_path / "latin1.csv", "Data,Preço\n12/11/2026,1\n", encoding="latin-1")
    with pytest.raises(SourceError, match="UTF-8"):
        CsvSource("loja", path).read()


def test_extra_fields_in_first_row_are_not_silently_shifted(tmp_path: Path) -> None:
    # Default pandas would turn "1,2" into an index and shift the data.
    path = _write(tmp_path / "ruim.csv", "a,b\n1,2,3,4\n")
    with pytest.raises(SourceError, match="mais colunas que o cabeçalho"):
        CsvSource("loja", path).read()


def test_extra_fields_in_later_row(tmp_path: Path) -> None:
    path = _write(tmp_path / "ruim.csv", "a,b\n1,2\n1,2,3,4\n")
    with pytest.raises(SourceError, match="a linha 3 tem 4 campos, mas o cabeçalho tem 2"):
        CsvSource("loja", path).read()


def test_trailing_delimiter_keeps_data_aligned(tmp_path: Path) -> None:
    path = _write(tmp_path / "vendas.csv", "a,b,\n1,2,\n")

    table = CsvSource("loja", path).read()

    assert table.iloc[0].tolist()[:2] == ["1", "2"]
