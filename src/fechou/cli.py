"""Command-line entry point.

Phase 0 only exposes ``--version``; the ``demo``, ``validate``, ``run`` and
``init-config`` commands are added in later phases.
"""

from typing import Annotated

import typer

from fechou import __version__

app = typer.Typer(
    name="fechou",
    help="Fechou: relatório semanal automático a partir de planilhas.",
    no_args_is_help=True,
    add_completion=False,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"fechou {__version__}")
        raise typer.Exit()


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


if __name__ == "__main__":  # pragma: no cover
    app()
