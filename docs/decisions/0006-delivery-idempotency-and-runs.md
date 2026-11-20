# 0006 — Entrega, tentativas, idempotência e registro de execuções

- **Status:** aceita
- **Data:** 2026-11-20

## Contexto

Os requisitos RF-09 a RF-11 e RF-14, além da seção 8.2, pedem envio por SMTP com tentativas, registro de cada execução em SQLite e que o mesmo período não seja enviado duas vezes. Alguns pontos ficaram em aberto: quantas tentativas, quais erros merecem nova tentativa, como o `--dry-run` e o `--force` interagem com a idempotência, e o que registrar.

## Decisão

**Configuração e segredos**
- O `.env` é lido com `pydantic-settings` (`env_ignore_empty`: `SMTP_USER=` conta como não definido). O ambiente tem prioridade sobre o arquivo.
- O SMTP é validado **antes de ler qualquer dado** (fail fast). Uma execução sem `SMTP_HOST`/`SMTP_FROM` termina com código 1 e não grava nada.
- Variáveis novas em relação à seção 12: `SMTP_SECURITY` (`starttls` | `ssl` | `none`), `SMTP_TIMEOUT` e `OUTPUT_DIR`.
- A senha é `SecretStr` e nunca aparece em `repr`, logs ou mensagens de erro.

**Tentativas (RF-14)**
- "Reexecuta até 3 vezes" foi interpretado literalmente: **1 tentativa + 3 novas tentativas**, com esperas de 2 s, 4 s e 8 s (cerca de 14 s no pior caso).
- Só erros **transitórios** geram nova tentativa: falha de conexão, timeout, desconexão e respostas SMTP 4xx.
- Erros **permanentes** falham na hora: usuário/senha, remetente ou destinatário recusado, respostas 5xx, TLS incompatível.

**Idempotência (RF-11)**
- Chave `run_key = source_id:AAAA-MM-DD:AAAA-MM-DD`. A verificação acontece **antes** de ler a planilha, então uma reexecução não faz trabalho à toa.
- Um índice único parcial (`status = 'success' AND forced = 0`) garante no banco no máximo um envio regular por chave. Envios com `--force` são gravados com `forced = 1`.
- `--dry-run` **ignora** a idempotência, salva o PDF e é registrado com o status extra `dry_run`. Esse status nunca conta como "enviado" e não bloqueia a execução real.
- Falha de entrega fica registrada como `delivery_failed` e **não** conta como enviado, então a próxima execução agendada tenta de novo.

**Registro (tabela `runs`)**
- Segue a seção 9.3, com três colunas a mais: `run_id` (correlação com os logs), `forced` e o status `dry_run`.
- `error_message` é truncado em 500 caracteres e contém só a mensagem pt-BR (sem traceback nem dados da planilha).
- Uma execução "pulada" grava `skipped` com o motivo (`already sent` ou `empty period`).

**Logs**
- JSON, uma linha por evento, em stderr, com `run_id`. Eventos: `run_started`, `source_read`, `report_rendered`, `delivery_retry`, `delivered`, `delivery_failed`, `run_finished`.
- Só contagens, chaves e status. **Nunca** linhas da planilha nem endereços de e-mail.

**Outros**
- O PDF também é salvo em `OUTPUT_DIR` nas execuções reais, como arquivo local do que foi enviado.
- `init-config` gera um `config.yaml` comentado a partir de um template empacotado e não sobrescreve um arquivo existente sem `--overwrite`.
- O assunto do e-mail aceita `{start}`, `{end}` e `{business}`. Um template inválido é rejeitado ao carregar a configuração.

## Consequências

- **Concorrência:** duas execuções simultâneas do mesmo período podem enviar duas vezes, porque o índice único só barra a segunda *gravação*. Com um único agendador isso não acontece; se mudar, será preciso um "claim" antes do envio.
- **Enviado mas não registrado:** se o SQLite falhar depois do envio, a CLI avisa explicitamente (código 1) que a próxima execução pode reenviar.
- **Vários canais:** se um canal falhar e outro não, a execução fica `delivery_failed` e a próxima reenvia para todos. Isso só importa quando houver Telegram.
- **LGPD:** a tabela `runs` guarda os e-mails dos destinatários, por ser registro de auditoria do envio. Não há outros dados pessoais; o banco fica fora do Git (`/data/`).
- Teste manual feito com um servidor SMTP local (`aiosmtpd`): envio, pulo na segunda execução, `--force` e falha de conexão (código 2 após 3 novas tentativas) se comportaram como esperado.
