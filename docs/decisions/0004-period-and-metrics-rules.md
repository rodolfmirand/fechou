# 0004 — Regras de período e de indicadores

- **Status:** aceita
- **Data:** 2026-11-20

## Contexto

O PROJETO.md (RF-05, RF-06, RF-07 e seção 9.2) define os indicadores, mas deixa em aberto detalhes que mudam o número final: arredondamento, empates, dias sem venda, valores ausentes e o "período anterior" quando o usuário passa `--start` e `--end`.

## Decisão

**Período**
- Os períodos são intervalos **inclusivos** de datas (`Period(start, end)`).
- Padrão: a última semana **completa** de segunda a domingo antes da semana do "agora", com o "agora" convertido para o fuso do relatório. Um disparo às 02:00 UTC de segunda ainda é domingo em São Paulo, portanto a semana corrente ainda não fechou.
- O relógio é injetável (`Clock`: `SystemClock`, `FixedClock`). A lógica de período nunca lê a hora real diretamente.
- **Período anterior** = mesmo número de dias, terminando no dia antes do início. Para `--start/--end` de 10 dias, compara com os 10 dias anteriores.

**Indicadores**
- O dinheiro é somado em **centavos inteiros** (`int64` no pandas) e convertido de volta para `Decimal`. Não há `float` em valores monetários.
- O ticket médio é arredondado para centavos com `ROUND_HALF_UP`. Sem vendas, fica `None` (exibido como "—").
- A variação percentual é guardada como fração com 4 casas (`0.1250` = +12,5%). Fica `None` quando o período anterior é zero (RF-07).
- Rankings (top 5 produtos, por categoria, por vendedor) ordenam por **faturamento** decrescente. Empate é desfeito pelo nome, em ordem alfabética, para o resultado ser determinístico.
- Categoria ou vendedor vazio numa linha vira o grupo "Sem categoria"/"Sem vendedor". Se **nenhuma** linha do período tem a informação, a seção é omitida (lista vazia).
- **Melhor e pior dia**: a data do calendário com maior e menor faturamento. **Dias sem venda contam** (R$ 0,00), e empate fica com a data mais antiga. Para semanas, isso equivale ao dia da semana; para períodos maiores, mostra a data concreta.

## Consequências

- Todas as funções de cálculo são puras (recebem `SaleRow`s e `Period`, devolvem dataclasses imutáveis) e cobertas por testes, inclusive os casos de virada de ano, ano bissexto, fuso e divisão por zero.
- Se a loja fecha aos domingos, o "pior dia" será sempre domingo com R$ 0,00. Isso é verdadeiro, mas pouco informativo. Se incomodar, uma opção futura é ignorar dias sem venda no cálculo do pior dia.
- Medido localmente: as métricas de ~50 mil linhas são calculadas em ~0,1 s.
