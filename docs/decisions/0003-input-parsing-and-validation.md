# 0003 — Leitura e validação da planilha

- **Status:** aceita
- **Data:** 2026-11-20

## Contexto

As planilhas de pequenos negócios misturam formatos (vírgula ou ponto decimal, `R$`, milhar com ponto, datas `dd/mm/aaaa` ou ISO). O RF-04 pede que linhas inválidas sejam descartadas e listadas, sem derrubar a execução. Já o RNF pede menos de 30 s para 50 mil linhas.

## Decisão

1. **Toda fonte devolve uma tabela só de texto** (`dtype=str`, células vazias como `""`). A conversão de tipos fica toda no domínio (`domain/parsing.py` + `SaleRow` com Pydantic v2), e não no pandas, para que CSV e Google Sheets passem pelas mesmas regras.
2. **Números de linha** = índice + 2 (a linha 1 é o cabeçalho). Linhas totalmente em branco são mantidas na leitura e ignoradas na validação, para não deslocar a numeração. Limitação: um campo entre aspas com quebra de linha dentro desloca a numeração.
3. **Valores monetários** viram `Decimal`, nunca `float`. Regras de normalização:
   - aceita `R$`, espaços e espaço não separável;
   - com `,` e `.` juntos, o separador mais à direita é o decimal (`1.234,56` e `1,234.56`);
   - uma vírgula sozinha é decimal (`49,90`); vários pontos sem vírgula indicam milhar (`1.234.567`);
   - **mais de 2 casas decimais é erro**. Assim, `1.234` (mil e duzentos ou 1,234?) vai para o bloco de avisos em vez de ser adivinhado.
4. **Colunas configuradas e ausentes** na planilha são erro fatal (`SchemaError`), com a lista de colunas disponíveis. Colunas opcionais (`category`, `seller`) podem ficar sem mapeamento.
5. **Leitura de CSV com pandas 3:** `index_col=False` e `ParserWarning` tratado como erro. Sem isso, se a primeira linha de dados tiver campos a mais, o pandas transforma esses campos em índice e **desloca os dados em silêncio**.
6. **Caminhos relativos no YAML** são resolvidos a partir da pasta do arquivo de configuração, e não do diretório atual. Por isso, `examples/config.example.yaml` usa `path: vendas_demo.csv`, enquanto a seção 10 do PROJETO.md mostrava `examples/vendas_demo.csv`, que é relativo à raiz.
7. **`fechou validate`** sai com 0 quando tudo é válido e com 1 quando há linhas inválidas ou erro de configuração/leitura, o que facilita o uso em scripts.

## Consequências

- Mensagens de erro por linha em pt-BR usam o nome real da coluna (`Qtd: deve ser um número inteiro…`), o que é útil para quem mantém a planilha.
- Valores na mensagem de erro aparecem truncados (40 caracteres) e só no relatório e no terminal, nunca no log estruturado (seção 13).
- Medido localmente: leitura e validação de 50 mil linhas em ~1,6 s.
