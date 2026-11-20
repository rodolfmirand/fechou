# 0005 — Geração do relatório (HTML → PDF)

- **Status:** aceita
- **Data:** 2026-11-20

## Contexto

O RF-08 pede um PDF em pt-BR gerado a partir de um template HTML (Jinja2 + WeasyPrint). O WeasyPrint depende do Pango, uma biblioteca nativa, que não está disponível em toda máquina. O relatório também precisa de um resumo em texto (corpo do e-mail e Telegram, RF-09) e de um bloco de avisos (RF-04).

## Decisão

1. **Camadas:** `pipeline.build_report_data` monta um `ReportData` imutável, sem formatação. `render/formatting.py` (Babel, `pt_BR`) formata moeda, datas, dias da semana e percentuais. `render/pdf.py` gera o HTML, o PDF e o resumo em texto. O template não faz contas, só exibe.
2. **WeasyPrint é importado sob demanda** dentro de `html_to_pdf`. Assim, `fechou validate` funciona sem Pango, e a ausência dele vira uma `RenderError` em pt-BR em vez de um traceback.
3. **Windows:** segue a documentação atual do WeasyPrint 70, com o Pango do **MSYS2 UCRT64** (`mingw-w64-ucrt-x86_64-pango`). O WeasyPrint encontrou as DLLs sem `WEASYPRINT_DLL_DIRECTORIES`. A documentação antiga citava `mingw-w64-x86_64-pango` (MINGW64), que não é mais o caminho indicado.
4. **Avisos por período:** `InvalidRow` guarda a data quando a célula de data é válida. O relatório mostra apenas as linhas inválidas do período atual e do anterior (as duas afetam os números exibidos), mais as que têm data ilegível. No máximo 30 itens; o restante é indicado com "e mais N", e o `fechou validate` mostra a lista completa.
5. **Layout:** A4 e uma página no caso comum (cartões de indicadores, faturamento diário em barras feitas só com HTML/CSS, top 5, categoria e vendedor lado a lado, avisos). Não há biblioteca de gráficos: as barras são `div`s com altura calculada no Python. Rodapé com data de geração e "Página X de Y".
6. **Identidade visual mínima:** `accent_color` (#RRGGBB validado) e `logo_path` opcional, embutido via URI `file://`.
7. **Moeda com NBSP** entre `R$` e o valor, como define o CLDR, para nunca quebrar a linha no meio do valor. No resumo em texto o NBSP vira espaço comum.
8. **Console resiliente:** a CLI reconfigura stdout/stderr com `errors="replace"`. Em pipes cp1252 do Windows (agendador, redirecionamento), um caractere não codificável derrubava o comando *depois* de gerar o PDF.
9. **Teste "golden" do PDF:** não compara bytes. Verifica o cabeçalho `%PDF-`, o número de páginas e textos-chave extraídos com `pypdf`. Localmente o teste é pulado se o Pango faltar; no CI, `FECHOU_REQUIRE_PDF=1` transforma isso em falha.
10. **`fechou demo`** usa o mesmo caminho da execução real (gera CSV → `CsvSource` → validação → métricas → PDF), com 4 linhas inválidas de propósito, e nunca envia nada.

## Consequências

- O visual depende das fontes do sistema: DejaVu Sans no Linux/Docker e Segoe UI no Windows. No Docker, a fonte será instalada explicitamente na Fase 6.
- O PNG de exemplo em `docs/` foi gerado a partir do PDF com uma ferramenta externa (`pypdfium2`, fora do projeto). O PDF em si é reprodutível com `scripts/generate_sample_report.py`.
