from pathlib import Path
from typing import Any

import pytest
import yaml

from fechou.config import CsvSourceConfig, GoogleSheetsSourceConfig, load_config, parse_config
from fechou.errors import ConfigError
from tests.conftest import EXAMPLES_DIR


def _base() -> dict[str, Any]:
    return {
        "source": {"id": "loja-demo", "type": "csv", "path": "vendas.csv"},
        "columns": {"date": "Data", "product": "Produto", "quantity": "Qtd", "unit_price": "Preço"},
        "report": {"business_name": "Loja Demo"},
    }


def test_example_config_is_valid() -> None:
    config = load_config(EXAMPLES_DIR / "config.example.yaml")

    assert isinstance(config.source, CsvSourceConfig)
    assert config.source.path == (EXAMPLES_DIR / "vendas_demo.csv").resolve()
    assert config.source.path.exists()
    assert config.columns.mapped()["unit_price"] == "Preço"
    assert config.report.timezone == "America/Sao_Paulo"
    assert config.delivery.email.enabled is True


def test_defaults(tmp_path: Path) -> None:
    config = parse_config(_base(), base_dir=tmp_path)

    assert isinstance(config.source, CsvSourceConfig)
    assert config.source.delimiter == ","
    assert config.source.path == (tmp_path / "vendas.csv").resolve()
    assert config.report.empty_period_policy == "send_empty"
    assert config.delivery.email.enabled is False
    assert config.delivery.telegram.enabled is False
    assert "category" not in config.columns.mapped()


def test_absolute_path_is_kept(tmp_path: Path) -> None:
    data = _base()
    absolute = (tmp_path / "x" / "vendas.csv").resolve()
    data["source"]["path"] = str(absolute)

    config = parse_config(data, base_dir=Path.cwd())

    assert isinstance(config.source, CsvSourceConfig)
    assert config.source.path == absolute


def test_google_sheets_source(tmp_path: Path) -> None:
    data = _base()
    data["source"] = {
        "id": "loja",
        "type": "google_sheets",
        "spreadsheet_id": "abc123",
        "worksheet": "Vendas",
    }

    config = parse_config(data, base_dir=tmp_path)

    assert isinstance(config.source, GoogleSheetsSourceConfig)
    assert config.source.range is None


def _sheets(**fields: str) -> dict[str, object]:
    data = _base()
    data["source"] = {"id": "loja", "type": "google_sheets", "worksheet": "Vendas", **fields}
    return data


def test_google_sheets_accepts_full_url_and_normalizes_range(tmp_path: Path) -> None:
    url = "https://docs.google.com/spreadsheets/d/1AbC-dEf_123/edit?gid=0#gid=0"

    config = parse_config(_sheets(spreadsheet_id=url, range=" b3:g "), base_dir=tmp_path)

    assert isinstance(config.source, GoogleSheetsSourceConfig)
    assert config.source.spreadsheet_id == "1AbC-dEf_123"
    assert config.source.range == "B3:G"


@pytest.mark.parametrize(
    ("fields", "expected"),
    [
        ({"spreadsheet_id": "id com espaço"}, "source.google_sheets.spreadsheet_id: use o ID"),
        (
            {"spreadsheet_id": "abc", "range": "Vendas!A1:F"},
            "source.google_sheets.range: use um intervalo A1 sem o nome da aba",
        ),
        ({"spreadsheet_id": "abc", "range": "A1:F:G"}, "use um intervalo A1"),
    ],
)
def test_google_sheets_invalid_fields(
    tmp_path: Path, fields: dict[str, str], expected: str
) -> None:
    with pytest.raises(ConfigError, match=expected):
        parse_config(_sheets(**fields), base_dir=tmp_path)


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (lambda d: d.pop("columns"), "columns: campo obrigatório ausente"),
        (lambda d: d["columns"].pop("quantity"), "columns.quantity: campo obrigatório ausente"),
        (lambda d: d["source"].update(type="excel"), "tipo inválido"),
        (lambda d: d["source"].update(id="Loja Demo"), "source.csv.id: use só letras minúsculas"),
        (lambda d: d["report"].update(timezone="Brasil/Lua"), "fuso horário desconhecido"),
        (lambda d: d["report"].update(empty_period_policy="ignore"), "opções:"),
        (lambda d: d["report"].update(accent_color="green"), "#RRGGBB"),
        (lambda d: d["report"].update(titel="x"), "report.titel: campo desconhecido"),
        (
            lambda d: d.update(delivery={"email": {"enabled": True}}),
            "e-mail habilitado sem destinatários",
        ),
        (
            lambda d: d.update(delivery={"email": {"to": ["dono-at-exemplo.com"]}}),
            "e-mail inválido: dono-at-exemplo.com",
        ),
        (
            lambda d: d.update(delivery={"email": {"subject": "Semana {inicio}"}}),
            "assunto inválido; use apenas {start}, {end} e {business}",
        ),
    ],
)
def test_invalid_configs_have_pt_br_messages(tmp_path: Path, mutate: Any, expected: str) -> None:
    data = _base()
    mutate(data)

    with pytest.raises(ConfigError) as info:
        parse_config(data, base_dir=tmp_path)

    assert expected in str(info.value)


def test_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="não encontrado"):
        load_config(tmp_path / "config.yaml")


def test_invalid_yaml(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("source: [unclosed", encoding="utf-8")

    with pytest.raises(ConfigError, match="YAML inválido"):
        load_config(path)


def test_yaml_must_be_a_mapping(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(["a", "b"]), encoding="utf-8")

    with pytest.raises(ConfigError, match="mapeamento"):
        load_config(path)
