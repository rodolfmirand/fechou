# 0008 — Docker, demonstração com Mailpit e agendamento

- **Status:** aceita
- **Data:** 2026-11-20

## Contexto

A Fase 6 pede um Dockerfile reprodutível, que resolva o Pango do WeasyPrint; um `docker compose up` que rode o fluxo de demonstração; e agendamento semanal. A decisão 0002 escolheu o GitHub Actions `schedule` e disse que a conversão para UTC seria documentada.

## Decisão

**Imagem**
- Base `python:3.12.16-slim-trixie`, com a versão fixada (hoje `3.12-slim` aponta para Debian trixie).
- Dois estágios. O de build instala o `requirements.txt` travado e o pacote (`--no-deps`) num venv. O final só copia o venv e instala o que a documentação do WeasyPrint 70 pede no Debian (`libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0`), mais `fonts-dejavu-core`, a fonte do template.
- Usuário sem privilégios (UID 1000). `ENTRYPOINT ["fechou"]` com `CMD ["demo"]`: `docker run fechou` roda a demonstração sem credenciais.
- O `.dockerignore` deixa de fora `.env`, `secrets/`, `config.yaml`, `data/`, `out/`, testes e docs. A imagem não carrega segredos nem dados.
- Tamanho: cerca de 640 MB, quase todo de pandas/numpy, Babel, fontTools e cryptography (dependência do google-auth). Não foi otimizado. Trocar de base (por exemplo, para Alpine) complicaria o Pango e as wheels.

**`docker compose up`**
- Dois serviços: o Mailpit (`axllent/mailpit:v1.34`, com interface em `localhost:8025`) e o Fechou, que roda `fechou run` sobre o CSV de exemplo com período fixo (09–15/11/2026), já que o CSV não acompanha a data atual.
- O Fechou espera o Mailpit ficar saudável (`service_healthy`; a imagem do Mailpit traz healthcheck `mailpit readyz`).
- O compose **não carrega `.env`**: as variáveis SMTP apontam para o Mailpit, então a demonstração nunca envia e-mail real.
- O histórico (`/app/data`) fica num volume nomeado. Rodar de novo mostra a idempotência ("Nada a fazer"), e `docker compose down -v` zera tudo. Usei volumes nomeados, e não pastas do host, para evitar problemas de permissão do UID 1000 no Linux; o PDF pode ser baixado no próprio Mailpit.

**Agendamento (GitHub Actions)**
- `.github/workflows/weekly-report.yml` roda às segundas, 08:00, com `timezone: America/Sao_Paulo`.
  - **Divergência da spec:** a seção 6 diz que o cron do Actions usa UTC. A documentação atual do GitHub aceita uma chave opcional `timezone` (IANA). Usei a chave, que também acompanharia um eventual retorno do horário de verão, e documentei no README o equivalente em UTC (`0 11 * * 1`).
- O workflow fica **desligado** até a variável de repositório `FECHOU_ENABLED` ser `true`, para não falhar no repositório de portfólio nem em forks.
- A configuração (`FECHOU_CONFIG`), a chave do Google e o SMTP vêm de *secrets*. Os arquivos são escritos com `umask 077` no runner e nunca entram em artefatos.
- O `workflow_dispatch` aceita período, simulação e reenvio.
- `concurrency` com `cancel-in-progress: false` impede duas execuções simultâneas, o que resolve no Actions a limitação de concorrência da decisão 0006.
- **Histórico entre execuções.** O runner é efêmero, então o SQLite é restaurado e salvo no cache do Actions, com uma chave por execução e `restore-keys` pelo prefixo. Alternativas descartadas:
  - Artefatos são visíveis para quem lê o repositório, e a tabela `runs` tem os e-mails dos destinatários.
  - Commitar o banco tem o mesmo problema e ainda polui o histórico.

  Limite: o GitHub apaga caches sem uso há 7 dias. Com execução semanal, o histórico pode se perder. O impacto é pequeno: cada semana é um período novo, e só um reenvio manual de uma semana antiga deixaria de ser bloqueado.
- O CI ganhou um job que constrói a imagem e roda `fechou demo` dentro dela, para o Dockerfile não quebrar em silêncio.

## Consequências

- Testado localmente:
  - `docker build`;
  - `fechou demo` dentro da imagem, com os mesmos números do ambiente local;
  - `docker compose up`, com e-mail recebido no Mailpit e PDF anexado;
  - segunda execução com "Nada a fazer";
  - `docker compose run --rm fechou demo`.
- Não testado: os workflows no GitHub, porque o repositório ainda não foi publicado. A sintaxe YAML e o `docker compose config` foram validados; o `actionlint` não foi rodado.
- Execuções agendadas no GitHub podem atrasar ou ser descartadas sob carga, e repositórios públicos sem atividade por 60 dias têm o agendamento desativado. Ambos estão documentados no README. Se a pontualidade for crítica, a alternativa é cron ou um container sempre ligado.
