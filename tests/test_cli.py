from typer.testing import CliRunner

from fechou import __version__
from fechou.cli import app

runner = CliRunner()


def test_version_flag_prints_version() -> None:
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == f"fechou {__version__}"


def test_help_is_in_portuguese() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "relatório semanal" in result.stdout
