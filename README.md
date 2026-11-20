# Fechou

Relatório semanal automático a partir de planilhas: lê CSV ou Google Sheets, calcula os indicadores da semana, gera um PDF e envia por e-mail ou Telegram.

> 🚧 **Status: em desenvolvimento (Fase 0 concluída).** Já existem a estrutura do projeto, o lint, a checagem de tipos, os testes e o CI. As funcionalidades abaixo ainda são planejadas.

## Problema

Pequenos negócios registram vendas numa planilha e, toda semana, alguém gasta tempo calculando totais, montando um resumo e enviando ao dono. É repetitivo, sujeito a erro e costuma ser adiado.

## Solução

O Fechou automatiza o ciclo inteiro: **ler → validar → calcular → gerar PDF → entregar → registrar**, em horário agendado e sem intervenção manual.

## Funcionalidades planejadas

- Leitura de CSV (modo demo) e de Google Sheets (conta de serviço)
- Validação por linha, com bloco de avisos no relatório para dados inválidos
- Indicadores: faturamento, nº de vendas, ticket médio, top produtos, por categoria e por vendedor, variação vs. semana anterior
- Relatório em PDF formatado em pt-BR
- Entrega por e-mail (SMTP) e, opcionalmente, Telegram
- Execução por linha de comando e agendada
- Idempotência: não reenvia o mesmo período, salvo com `--force`
- Modo `demo` que roda sem credenciais e sem enviar nada

## Stack planejada

| Camada | Tecnologia |
|---|---|
| Linguagem | Python 3.12 |
| CLI | Typer |
| Dados | pandas, Pydantic v2 |
| Google Sheets | gspread |
| Relatório | Jinja2 + WeasyPrint |
| Persistência | SQLite |
| Qualidade | pytest, ruff, mypy |
| Infra | Docker, GitHub Actions |

## Desenvolvimento

Requisitos: **Python 3.12**. Nada é instalado globalmente; tudo fica no venv do projeto.

```powershell
# Windows (PowerShell)
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install "pip-tools>=7.4"
.\.venv\Scripts\pip-sync requirements-dev.txt
.\.venv\Scripts\python -m pip install --no-deps -e .
```

```bash
# Linux/macOS
python3.12 -m venv .venv
.venv/bin/python -m pip install "pip-tools>=7.4"
.venv/bin/pip-sync requirements-dev.txt
.venv/bin/python -m pip install --no-deps -e .
```

Checagens (as mesmas que rodam no CI):

```bash
ruff check .
ruff format --check .
mypy
pytest
```

### Dependências

As dependências são declaradas no `pyproject.toml` e fixadas com **pip-tools** em `requirements.txt` (execução) e `requirements-dev.txt` (desenvolvimento). Ao alterar dependências:

```bash
pip-compile --strip-extras -o requirements.txt pyproject.toml
pip-compile --strip-extras --extra dev -o requirements-dev.txt pyproject.toml
pip-sync requirements-dev.txt && pip install --no-deps -e .
```

Detalhes em [`docs/decisions/0001-dependency-locking-with-pip-tools.md`](./docs/decisions/0001-dependency-locking-with-pip-tools.md).

## Como usar

Já funciona:

```text
fechou --version
fechou --help
```

Os comandos abaixo são o **desenho planejado** e ainda não existem. Esta seção será atualizada ao longo da implementação.

```text
fechou demo
fechou validate --config config.yaml
fechou run --config config.yaml [--dry-run] [--force]
```

## Roadmap

- [x] Fase 0: estrutura do projeto, lint, testes e CI
- [ ] Fase 1: modelos, leitura de CSV, validação e dados de demonstração
- [ ] Fase 2: cálculo de período e indicadores
- [ ] Fase 3: relatório em PDF e comando `demo`
- [ ] Fase 4: entrega por e-mail, idempotência e registro de execuções
- [ ] Fase 5: integração com Google Sheets
- [ ] Fase 6: Docker, agendamento e documentação final

## Limitações previstas

- Sem interface web nem múltiplos usuários.
- Suporte a `.xlsx` fica como item opcional.
- Números de "tempo economizado" que aparecerem aqui serão **estimativas de demonstração**, não resultados medidos em clientes.

## Decisões técnicas

Registradas em [`docs/decisions/`](./docs/decisions/).

## Licença

[MIT](./LICENSE).
