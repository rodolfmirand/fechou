# 0002 — Respostas às perguntas em aberto da especificação

- **Status:** aceita
- **Data:** 2026-11-20

## Contexto

A seção 19 do PROJETO.md deixou em aberto o provedor de e-mail, a forma de agendamento e a identidade visual. Também há a questão de como rodar o WeasyPrint, que depende do Pango, no ambiente de desenvolvimento Windows.

## Decisão

1. **E-mail:** SMTP genérico (host, porta, usuário e senha via `.env`). Isso funciona com qualquer provedor, inclusive Gmail com senha de app. Para testes locais e para a demo, o `docker-compose` terá um **Mailpit**, que captura os e-mails sem enviá-los de verdade.
2. **Agendamento:** **GitHub Actions `schedule`**, sem servidor. O cron do Actions usa UTC, e a conversão para America/Sao_Paulo (UTC-3) será documentada no README.
3. **Identidade visual:** mínima e configurável no YAML, só com **cor de destaque** e **logo opcional**.
4. **WeasyPrint no Windows:** instalação local das bibliotecas nativas (Pango via MSYS2), seguindo a documentação oficial do WeasyPrint. O Docker continua sendo o ambiente reprodutível de referência.

## Consequências

- Nenhum provedor fica amarrado ao código, e a demo não depende de conta externa.
- Sem processo contínuo: o agendamento depende do repositório estar no GitHub e de os secrets estarem configurados no Actions.
- A instalação local do Pango é um passo manual documentado no README, feito na Fase 3.
