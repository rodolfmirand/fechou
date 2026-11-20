# Fechou

Relatório semanal automático a partir de planilhas: lê CSV ou Google Sheets, calcula os indicadores da semana, gera um PDF e envia por e-mail ou Telegram.

> 🚧 **Status: em desenvolvimento (Fases 0 a 4 concluídas).** O fluxo completo com CSV já funciona: validação, indicadores, PDF, envio por e-mail (SMTP) com novas tentativas, idempotência e registro das execuções (`fechou run`). Google Sheets, Docker e agendamento ainda são planejados.

![Exemplo de relatório gerado pelo Fechou (dados fictícios)](./docs/exemplo-relatorio.png)

*Relatório gerado por `fechou demo` com dados fictícios ([PDF](./docs/exemplo-relatorio.pdf)).*

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

Requisitos: **Python 3.12** e as bibliotecas do **Pango** (usadas pelo WeasyPrint para gerar o PDF; veja abaixo). As dependências Python ficam no venv do projeto.

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

### Instalação do WeasyPrint (Pango)

Conforme a [documentação do WeasyPrint](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html):

- **Windows:** instale o [MSYS2](https://www.msys2.org/) com as opções padrão (por exemplo, `winget install MSYS2.MSYS2`). Depois, no shell **MSYS2 UCRT64**, rode `pacman -S mingw-w64-ucrt-x86_64-pango`. Se aparecer `cannot load library ...`, defina `WEASYPRINT_DLL_DIRECTORIES=C:\msys64\ucrt64\bin`.
- **Debian/Ubuntu:** `sudo apt install libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libharfbuzz-subset0 fonts-dejavu-core`.
- Para conferir: `python -m weasyprint --info`.

Sem o Pango, `fechou validate` continua funcionando; só a geração do PDF falha, com uma mensagem explicando o motivo. Os testes de PDF são pulados localmente e obrigatórios no CI.

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
fechou init-config [--output config.yaml] [--overwrite]
fechou validate --config config.yaml
fechou demo [--output ./out]
fechou run --config config.yaml [--start AAAA-MM-DD --end AAAA-MM-DD] [--dry-run] [--force] [--output ./out]
```

Primeiros passos com o CSV de demonstração:

```bash
fechou init-config                 # cria config.yaml comentado
cp .env.example .env               # preencha SMTP_* (veja "Envio por e-mail")
fechou validate -c config.yaml     # confere a planilha
fechou run -c config.yaml --start 2026-11-09 --end 2026-11-15 --dry-run   # gera o PDF sem enviar
fechou run -c config.yaml --start 2026-11-09 --end 2026-11-15             # envia
```

**`fechou demo`** gera dados fictícios da semana passada e da anterior (com 4 linhas inválidas de propósito), passa pelo mesmo fluxo de uma execução real (CSV → validação → indicadores → PDF), salva o CSV e o PDF em `./out` e imprime o resumo. **Nada é enviado.**

```text
Relatório semanal de vendas — Loja Demo (dados fictícios)
Período: 09/11/2026 a 15/11/2026

• Faturamento: R$ 15.785,80 (+14,2% vs. período anterior)
• Vendas: 75 (-2,6% vs. período anterior)
• Ticket médio: R$ 210,48
• Itens vendidos: 142
• Produto destaque: Tênis casual (R$ 3.998,40)
• Melhor dia: quarta-feira, 11/11/2026 (R$ 3.742,30)
• Dia mais fraco: terça-feira, 10/11/2026 (R$ 1.033,70)

Atenção: 4 linha(s) descartada(s) por erro de preenchimento.
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

### `fechou run`

Executa o fluxo completo: **período → já enviado? → ler → validar → calcular → PDF → enviar → registrar**.

- **Período padrão:** a semana passada (segunda a domingo, no fuso do relatório). Com `--start` e `--end` (sempre juntos), qualquer intervalo.
- **Idempotência:** se o relatório daquela fonte e período já foi enviado, o comando encerra com "Nada a fazer" (código 0) **sem ler a planilha**. `--force` reenvia.
- **`--dry-run`:** faz tudo, exceto enviar. Mostra o resumo e salva o PDF. Não precisa de SMTP configurado e não conta como enviado.
- **Falhas de rede:** até 3 novas tentativas (esperas de 2 s, 4 s e 8 s). Erros definitivos, como senha errada ou destinatário recusado, não são repetidos.
- **Período sem vendas:** com `empty_period_policy: send_empty`, envia um relatório "Sem movimento"; com `skip`, só registra.
- O PDF de cada execução fica salvo em `OUTPUT_DIR` (padrão `./out`).

| Código de saída | Significado |
|---|---|
| `0` | Enviado, simulação concluída ou nada a fazer |
| `1` | Erro de configuração ou de dados (nada foi enviado) |
| `2` | Falha na entrega depois das novas tentativas |

Cada execução é gravada na tabela `runs` do SQLite (`DATABASE_PATH`, padrão `./data/fechou.db`), com período, status, contagem de linhas, destinatários e erro. Os logs saem em JSON no stderr, com um `run_id` por execução, e trazem só contagens e status, nunca linhas da planilha nem e-mails.

### Envio por e-mail

Funciona com qualquer servidor SMTP. Configure no `.env` (modelo em [`.env.example`](./.env.example)):

| Variável | Exemplo | Observação |
|---|---|---|
| `SMTP_HOST` / `SMTP_PORT` | `smtp.gmail.com` / `587` | |
| `SMTP_SECURITY` | `starttls` | `starttls` (587), `ssl` (465) ou `none` (só para servidor de teste local) |
| `SMTP_USER` / `SMTP_PASSWORD` | | No Gmail, use uma **senha de app**, nunca a senha da conta |
| `SMTP_FROM` | `Fechou <relatorios@exemplo.com>` | Remetente |

Os destinatários e o assunto ficam no `config.yaml` (`delivery.email`). O assunto aceita `{start}`, `{end}` e `{business}`.

Para testar sem enviar e-mails de verdade, aponte para um servidor SMTP de testes local (por exemplo, o Mailpit) com `SMTP_SECURITY=none`. Um `docker-compose` com Mailpit está planejado para a Fase 6.

### Configuração

Gere um modelo com `fechou init-config` ou copie [`examples/config.example.yaml`](./examples/config.example.yaml) e ajuste. Caminhos relativos são resolvidos a partir da pasta do arquivo de configuração. A seção `columns` liga os nomes internos (`date`, `product`, `category`, `quantity`, `unit_price`, `seller`) aos nomes das colunas da sua planilha. `category` e `seller` são opcionais.

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

O PDF de exemplo em `docs/` (data fixa, 16/11/2026) é regenerado com `python scripts/generate_sample_report.py`.

### Período e indicadores

- **Período padrão:** a última semana completa (segunda a domingo) no fuso do relatório (`America/Sao_Paulo` por padrão). Ela é comparada com a semana imediatamente anterior. Com `--start/--end` no `fechou run`, a comparação é com o mesmo número de dias imediatamente antes.
- **Indicadores:** faturamento, número de vendas, itens vendidos, ticket médio, top 5 produtos, faturamento por categoria e por vendedor, faturamento por dia, melhor e pior dia, e variação de faturamento e de vendas em relação ao período anterior ("—" quando o anterior é zero).
- Valores monetários são calculados sem `float` (centavos inteiros). As regras de arredondamento e desempate estão em [`docs/decisions/0004-period-and-metrics-rules.md`](./docs/decisions/0004-period-and-metrics-rules.md).

### Planejado

- Fonte `google_sheets` (Fase 5). Hoje, uma configuração com esse tipo é aceita, mas a leitura informa que ainda não está disponível.
- Docker, `docker compose` com Mailpit e agendamento (Fase 6).
- Telegram (opcional).

## Roadmap

- [x] Fase 0: estrutura do projeto, lint, testes e CI
- [x] Fase 1: modelos, leitura de CSV, validação e dados de demonstração
- [x] Fase 2: cálculo de período e indicadores
- [x] Fase 3: relatório em PDF e comando `demo`
- [x] Fase 4: entrega por e-mail, idempotência e registro de execuções
- [ ] Fase 5: integração com Google Sheets
- [ ] Fase 6: Docker, agendamento e documentação final

## Limitações previstas

- Sem interface web nem múltiplos usuários.
- Duas execuções **simultâneas** do mesmo período podem enviar em dobro. Com um único agendador isso não ocorre (veja a decisão 0006).
- Suporte a `.xlsx` fica como item opcional.
- Números de "tempo economizado" que aparecerem aqui serão **estimativas de demonstração**, não resultados medidos em clientes.

## Decisões técnicas

Registradas em [`docs/decisions/`](./docs/decisions/).

## Licença

[MIT](./LICENSE).
