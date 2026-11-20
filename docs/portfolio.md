# Material de portfólio

## Texto curto para o perfil

> Automatizo relatórios de planilhas e envio por e-mail/Telegram.

Versão um pouco mais longa:

> Sua equipe perde tempo toda semana somando a planilha de vendas e montando um resumo? Eu automatizo isso: o relatório em PDF chega pronto no seu e-mail, no dia e hora combinados, com os erros de preenchimento apontados. Funciona com Google Sheets ou CSV, sem servidor.

## Roteiro do GIF (30 a 60 segundos)

Objetivo: mostrar **planilha → comando → PDF → e-mail recebido**, usando só dados fictícios e o Mailpit (nenhum e-mail real).

Preparação:
- Terminal com fonte grande (≥ 16 pt) e janela de cerca de 1280×720.
- `docker compose down -v` antes de gravar, para começar sem histórico.
- Abas abertas: o CSV `examples/vendas_demo.csv` (ou uma cópia importada no Google Sheets) e `http://localhost:8025`.
- Ferramenta sugerida no Windows: [ScreenToGif](https://www.screentogif.com/).

| Tempo | Cena |
|---|---|
| 0–8 s | Planilha de vendas aberta; destacar uma linha com erro (ex.: quantidade `0`) |
| 8–25 s | Terminal: `docker compose up --build`. Mostrar o resumo impresso e "enviado para 1 destinatário(s)" |
| 25–40 s | Navegador em `localhost:8025`: e-mail "Fechamento da semana…" chegando; abrir, mostrar o resumo no corpo |
| 40–55 s | Abrir o PDF anexado: indicadores, gráfico por dia e bloco de avisos com a linha descartada |
| 55–60 s | Terminal: `docker compose up` de novo → "Nada a fazer" (não envia duas vezes) |

Depois, salve como `docs/demo.gif` (de preferência com menos de 10 MB) e adicione ao README, logo abaixo da imagem do relatório.
