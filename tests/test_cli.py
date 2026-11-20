from pathlib import Path

from typer.testing import CliRunner

from fechou import __version__
from fechou.cli import EXIT_DATA_OR_CONFIG, EXIT_OK, app
from tests.conftest import EXAMPLES_DIR

runner = CliRunner()


def test_version_flag_prints_version() -> None:
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == f"fechou {__version__}"


def test_help_is_in_portuguese() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "relatório semanal" in result.stdout


def test_validate_example_lists_invalid_rows() -> None:
    result = runner.invoke(app, ["validate", "--config", str(EXAMPLES_DIR / "config.example.yaml")])

    assert result.exit_code == EXIT_DATA_OR_CONFIG
    assert "Fonte: loja-demo (csv)" in result.stdout
    assert "Inválidas: 6" in result.stdout
    assert "Produto: campo obrigatório vazio" in result.stdout


def _write_config(tmp_path: Path, csv_text: str) -> Path:
    (tmp_path / "vendas.csv").write_text(csv_text, encoding="utf-8")
    config = tmp_path / "config.yaml"
    config.write_text(
        "source: {id: loja, type: csv, path: vendas.csv}\n"
        "columns: {date: Data, product: Produto, quantity: Qtd, unit_price: Preço}\n"
        "report: {business_name: Loja}\n",
        encoding="utf-8",
    )
    return config


def test_validate_clean_file_exits_zero(tmp_path: Path) -> None:
    config = _write_config(tmp_path, 'Data,Produto,Qtd,Preço\n12/11/2026,Boné,1,"44,90"\n')

    result = runner.invoke(app, ["validate", "-c", str(config)])

    assert result.exit_code == EXIT_OK
    assert "Nenhum problema encontrado." in result.stdout


def test_validate_missing_column_is_an_error(tmp_path: Path) -> None:
    config = _write_config(tmp_path, "Data,Produto,Qtd\n12/11/2026,Boné,1\n")

    result = runner.invoke(app, ["validate", "-c", str(config)])

    assert result.exit_code == EXIT_DATA_OR_CONFIG
    assert "Colunas não encontradas na planilha: 'Preço'" in result.stderr


def test_validate_missing_config_file(tmp_path: Path) -> None:
    result = runner.invoke(app, ["validate", "-c", str(tmp_path / "nao-existe.yaml")])

    assert result.exit_code == EXIT_DATA_OR_CONFIG
    assert "Arquivo de configuração não encontrado" in result.stderr
