# Fechou

Relatório semanal automático a partir de planilhas: lê CSV ou Google Sheets, calcula os indicadores da semana, gera um PDF e envia por e-mail ou Telegram.

> 🚧 **Status: em desenvolvimento (Fases 0 e 1 concluídas).** Já existem a leitura de CSV, a validação da planilha (`fechou validate`) e os dados de demonstração. Relatório, PDF e entrega ainda são planejados.

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
| Configuração | YAML (PyYAML) |
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

### Já funciona

```text
fechou --version
fechou validate --config examples/config.example.yaml
```

O `validate` lê a planilha, aplica as regras de validação e lista as linhas descartadas com o motivo, sem gerar nem enviar nada. Ele sai com código `0` quando tudo é válido e `1` quando há linhas inválidas ou erro de configuração. Exemplo com o CSV de demonstração, que tem 6 linhas quebradas de propósito:

```text
Fonte: loja-demo (csv)
Linhas lidas: 785
Válidas: 779
Inválidas: 6

Linhas com problema (serão descartadas do relatório):
  - linha 15: Produto: campo obrigatório vazio
  - linha 27: Qtd: deve ser um número inteiro maior que zero (valor: '0')
  - linha 111: Preço: valor numérico inválido 'abc'
  ...
```

### Configuração

Copie [`examples/config.example.yaml`](./examples/config.example.yaml) e ajuste. Caminhos relativos são resolvidos a partir da pasta do arquivo de configuração. A seção `columns` liga os nomes internos (`date`, `product`, `category`, `quantity`, `unit_price`, `seller`) aos nomes das colunas da sua planilha. `category` e `seller` são opcionais.

Formatos aceitos nas células:

| Campo | Aceita | Rejeita |
|---|---|---|
| Data | `12/11/2026`, `2026-11-12` | `31/02/2026`, `12-11-2026` |
| Quantidade | inteiro > 0 | `0`, `-1`, `2,5` |
| Preço | `49,90`, `49.90`, `R$ 1.234,56`, `1,234.56` | negativos, texto, mais de 2 casas (`1.234` é ambíguo) |

### Dados de demonstração

O arquivo `examples/vendas_demo.csv` é **fictício** e reprodutível (semente fixa). Para regenerá-lo:

```bash
python scripts/generate_demo_data.py [--start 2026-09-07] [--end 2026-11-15] [--seed 42] [--invalid 6]
```

### Planejado

Os comandos abaixo ainda **não existem**. Esta seção será atualizada ao longo da implementação.

```text
fechou demo [--output ./out]
fechou run --config config.yaml [--start AAAA-MM-DD --end AAAA-MM-DD] [--dry-run] [--force]
fechou init-config [--output config.yaml]
```

## Roadmap

- [x] Fase 0: estrutura do projeto, lint, testes e CI
- [x] Fase 1: modelos, leitura de CSV, validação e dados de demonstração
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
