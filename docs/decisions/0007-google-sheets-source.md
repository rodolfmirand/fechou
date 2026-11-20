# 0007 — Leitura do Google Sheets

- **Status:** aceita
- **Data:** 2026-11-20

## Contexto

O RF-02 pede a leitura do Google Sheets com conta de serviço, aba e intervalo configuráveis. A stack prevê `gspread` e `google-auth`, e a seção 18 da spec manda seguir a documentação atual se ela divergir. Versões usadas: gspread 6.2.1 e google-auth 2.62.2.

## Decisão

**Autenticação**
- A chave JSON da conta de serviço vem de `GOOGLE_APPLICATION_CREDENTIALS`, como na seção 12. A variável é exigida **antes** de qualquer leitura (fail fast em `validate` e `run`). Só é lida quando a fonte é `google_sheets`, então o modo CSV não depende do `.env`.
- O escopo é **somente leitura** (`spreadsheets.readonly`). A documentação do gspread mostra escopos de leitura e escrita, mas o Fechou nunca escreve.
- A planilha é aberta pelo ID (`open_by_key`), que usa só a Sheets API. Por isso a Drive API, que a documentação do gspread manda ativar, não é necessária. Ela só seria usada por `open()` (busca por título).
- `spreadsheet_id` aceita o ID ou a URL completa, porque o usuário costuma copiar a URL.

**Valores sem formatação**
- As células são lidas com `UNFORMATTED_VALUE` + `SERIAL_NUMBER`, e não com o padrão `FORMATTED_VALUE`. Com o valor formatado, uma planilha em inglês mostraria `11/5/2026` para 5 de novembro, e o parser (dd/mm) leria 11 de maio **sem erro**, gerando números errados em silêncio.
- Na coluna de data, um número é tratado como data serial (dias desde 30/12/1899) e convertido para `AAAA-MM-DD`; a hora, se houver, é descartada. Em outras colunas, números viram texto com até 9 casas, o que elimina ruído binário de fórmulas (`98.89000000000001` → `98.89`) sem notação científica.
- Células digitadas como texto chegam como estão e passam pelas mesmas regras do CSV (ADR 0003).

**Intervalo e numeração de linhas**
- `range` é um intervalo A1 **sem** o nome da aba (`A1:F`, `B3:G500`); a aba fica em `worksheet`. Um intervalo com `!` é rejeitado ao carregar a configuração.
- A primeira linha não vazia do intervalo é o cabeçalho. Os avisos citam a linha real da planilha: a tabela bruta carrega `attrs["header_line"]`, que considera o início do intervalo e as linhas em branco do topo.
- Linhas mais curtas (a API omite células vazias no fim) são completadas. Colunas sem cabeçalho viram `Unnamed: N`, como no CSV. Cabeçalhos repetidos são erro.

**Erros e novas tentativas**
- Respostas 408, 429 e 5xx geram até 3 novas tentativas, com esperas de 2, 4 e 8 s (o `BackOffHTTPClient` do gspread, limitado a 8 s), na mesma política da entrega.
- Cada falha vira uma mensagem pt-BR com a ação a tomar: planilha não encontrada, sem acesso (cita o `client_email` a compartilhar), aba inexistente (lista as abas), API desativada, intervalo inválido, chave recusada e sem conexão.
- Na prática o gspread 6 transforma um 403 ao abrir a planilha em `PermissionError`, não no `SpreadsheetNotFound` que a documentação cita para planilha não compartilhada. Os dois casos são tratados.

## Divergências da documentação atual

- **gspread:** pede para ativar Drive **e** Sheets API e usa escopos de escrita. Aqui só a Sheets API e somente leitura (motivos acima). O caminho padrão da chave no gspread (`~/.config/gspread/service_account.json`) não é usado, porque a spec define `GOOGLE_APPLICATION_CREDENTIALS`.
- **Google Cloud:** a chave é criada em *IAM e administrador > Contas de serviço > (conta) > Chaves > Adicionar chave*, não mais em *APIs e serviços > Credenciais*, como diz a documentação do gspread.
- **Política de organização:** em organizações criadas a partir de 3 de maio de 2024, a restrição `iam.disableServiceAccountKeyCreation` vem ativa por padrão e impede criar chaves. Contas Google pessoais (sem organização) não são afetadas. O README explica o caso.

## Consequências

- Testes automatizados usam um cliente falso. Um teste manual também roda o **gspread real** com a camada HTTP simulada, e confirma os parâmetros da requisição, o mapeamento de 403/404 e as esperas de 2, 4 e 8 s. Ainda falta validar contra uma planilha real.
- Formatos personalizados de data exibidos como texto, como `qua, 5 nov`, só funcionam se a célula for de fato uma data; se for texto, a linha é descartada com aviso.
- A chave JSON é um segredo de longa duração. Ela fica em `secrets/`, fora do Git e da imagem Docker (Fase 6), e pode ser revogada no console.
