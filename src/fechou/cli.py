"""Command-line entry point. User-facing text is pt-BR."""

import datetime as dt
import io
import sys
import uuid
from importlib.resources import files
from pathlib import Path
from typing import Annotated

import typer

from fechou import __version__
from fechou.clock import SystemClock
from fechou.config import AppConfig, GoogleSheetsSourceConfig, load_config
from fechou.demo import run_demo
from fechou.errors import FechouError
from fechou.extract import Source, build_source
from fechou.logging_setup import configure_logging
from fechou.render.pdf import render_summary_text
from fechou.runner import (
    EXIT_DATA_OR_CONFIG,
    EXIT_DELIVERY,
    EXIT_OK,
    RunOptions,
    build_deliveries,
    execute_run,
)
from fechou.settings import Settings, load_settings
from fechou.storage.runs import RunStore
from fechou.transform.validate import validate_rows

__all__ = ["EXIT_DATA_OR_CONFIG", "EXIT_DELIVERY", "EXIT_OK", "app"]

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


def _safe_console() -> None:
    """Never crash on output encoding (e.g. cp1252 pipes on Windows schedulers).

    Unencodable characters are replaced instead of raising after the work is done.
    """
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(errors="replace")


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
    _safe_console()


def _build_source(app_config: AppConfig, settings: Settings | None = None) -> Source:
    """Only Google Sheets needs the environment (``GOOGLE_APPLICATION_CREDENTIALS``)."""
    if not isinstance(app_config.source, GoogleSheetsSourceConfig):
        return build_source(app_config)
    settings = settings or load_settings()
    return build_source(app_config, settings.google_application_credentials)


@app.command()
def validate(config: ConfigOption = Path("config.yaml")) -> None:
    """Valida a planilha e lista as linhas com problema, sem gerar nem enviar nada.

    Sai com código 0 se todas as linhas forem válidas e 1 se houver linhas
    inválidas ou erro de configuração/leitura.
    """
    try:
        app_config = load_config(config)
        source = _build_source(app_config)
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


@app.command()
def demo(
    output: Annotated[
        Path,
        typer.Option(
            "--output", "-o", help="Pasta onde salvar o PDF e o CSV gerados.", file_okay=False
        ),
    ] = Path("out"),
) -> None:
    """Gera dados fictícios e o relatório em PDF da semana passada, sem enviar nada."""
    try:
        result = run_demo(output, SystemClock())
    except FechouError as error:
        raise _fail(error) from None

    typer.echo(render_summary_text(result.report))
    typer.echo("")
    typer.echo(f"Dados fictícios: {result.csv_path}")
    typer.echo(f"PDF gerado:      {result.pdf_path}")
    typer.echo("Modo demo: nada foi enviado.")


@app.command()
def run(
    config: ConfigOption = Path("config.yaml"),
    start: Annotated[
        dt.datetime | None,
        typer.Option(
            "--start", formats=["%Y-%m-%d"], metavar="AAAA-MM-DD", help="Início do período."
        ),
    ] = None,
    end: Annotated[
        dt.datetime | None,
        typer.Option("--end", formats=["%Y-%m-%d"], metavar="AAAA-MM-DD", help="Fim do período."),
    ] = None,
    force: Annotated[
        bool, typer.Option("--force", help="Reenvia mesmo se o período já foi enviado.")
    ] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Faz tudo, exceto enviar; salva o PDF.")
    ] = False,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output", "-o", help="Pasta do PDF (padrão: OUTPUT_DIR ou ./out).", file_okay=False
        ),
    ] = None,
) -> None:
    """Gera e envia o relatório do período (padrão: semana passada, seg. a dom.).

    Códigos de saída: 0 sucesso ou nada a fazer, 1 erro de dados/configuração,
    2 falha de entrega.
    """
    run_id = uuid.uuid4().hex[:12]
    try:
        settings = load_settings()
        configure_logging(run_id, settings.log_level)
        app_config = load_config(config)
        source = _build_source(app_config, settings)
        deliveries = [] if dry_run else build_deliveries(app_config, settings)
        store = RunStore(settings.database_path)
    except FechouError as error:
        raise _fail(error) from None

    options = RunOptions(
        start=start.date() if start else None,
        end=end.date() if end else None,
        force=force,
        dry_run=dry_run,
        output_dir=output or settings.output_dir,
    )
    try:
        outcome = execute_run(
            app_config,
            options,
            source=source,
            deliveries=deliveries,
            store=store,
            clock=SystemClock(),
            run_id=run_id,
        )
    except FechouError as error:
        raise _fail(error) from None

    if outcome.summary:
        typer.echo(outcome.summary)
        typer.echo("")
    typer.echo(outcome.message, err=outcome.exit_code != EXIT_OK)
    raise typer.Exit(outcome.exit_code)


@app.command("init-config")
def init_config(
    output: Annotated[
        Path, typer.Option("--output", "-o", help="Onde criar o arquivo.", dir_okay=False)
    ] = Path("config.yaml"),
    overwrite: Annotated[
        bool, typer.Option("--overwrite", help="Substitui o arquivo se já existir.")
    ] = False,
) -> None:
    """Cria um config.yaml comentado para você ajustar."""
    if output.exists() and not overwrite:
        typer.echo(f"Erro: {output} já existe. Use --overwrite para substituir.", err=True)
        raise typer.Exit(EXIT_DATA_OR_CONFIG)
    template = files("fechou").joinpath("templates/config.yaml").read_text(encoding="utf-8")
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(template, encoding="utf-8")
    except OSError as exc:
        typer.echo(f"Erro: não foi possível criar {output}: {exc.strerror}", err=True)
        raise typer.Exit(EXIT_DATA_OR_CONFIG) from None
    typer.echo(f"Configuração criada em {output}. Ajuste 'source', 'columns' e 'delivery'.")
    typer.echo("Depois: fechou validate -c " + str(output))


if __name__ == "__main__":  # pragma: no cover
    app()
