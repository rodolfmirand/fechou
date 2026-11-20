"""Command-line entry point. User-facing text is pt-BR."""

from pathlib import Path
from typing import Annotated

import typer

from fechou import __version__
from fechou.config import load_config
from fechou.errors import FechouError
from fechou.extract import build_source
from fechou.transform.validate import validate_rows

EXIT_OK = 0
EXIT_DATA_OR_CONFIG = 1
EXIT_DELIVERY = 2

MAX_LISTED_PROBLEMS = 50

app = typer.Typer(
    name="fechou",
    help="Fechou: relatório semanal automático a partir de planilhas.",
    no_args_is_help=True,
    add_completion=False,
)

ConfigOption = Annotated[
    Path,
    typer.Option(
        "--config",
        "-c",
        help="Arquivo de configuração YAML.",
        dir_okay=False,
    ),
]


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"fechou {__version__}")
        raise typer.Exit()


def _fail(error: FechouError) -> typer.Exit:
    typer.echo(f"Erro: {error}", err=True)
    return typer.Exit(EXIT_DATA_OR_CONFIG)


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            help="Mostra a versão e sai.",
            callback=_version_callback,
            is_eager=True,
        ),
    ] = False,
) -> None:
    """Fechou: relatório semanal automático a partir de planilhas."""


@app.command()
def validate(config: ConfigOption = Path("config.yaml")) -> None:
    """Valida a planilha e lista as linhas com problema, sem gerar nem enviar nada.

    Sai com código 0 se todas as linhas forem válidas e 1 se houver linhas
    inválidas ou erro de configuração/leitura.
    """
    try:
        app_config = load_config(config)
        source = build_source(app_config)
        result = validate_rows(source.read(), app_config.columns)
    except FechouError as error:
        raise _fail(error) from None

    typer.echo(f"Fonte: {source.source_id} ({source.kind})")
    typer.echo(f"Linhas lidas: {result.total}")
    typer.echo(f"Válidas: {len(result.valid)}")
    typer.echo(f"Inválidas: {len(result.invalid)}")

    if not result.invalid:
        typer.echo("\nNenhum problema encontrado.")
        return

    typer.echo("\nLinhas com problema (serão descartadas do relatório):")
    for row in result.invalid[:MAX_LISTED_PROBLEMS]:
        typer.echo(f"  - {row.describe()}")
    remaining = len(result.invalid) - MAX_LISTED_PROBLEMS
    if remaining > 0:
        typer.echo(f"  ... e mais {remaining} linha(s).")
    raise typer.Exit(EXIT_DATA_OR_CONFIG)


if __name__ == "__main__":  # pragma: no cover
    app()
