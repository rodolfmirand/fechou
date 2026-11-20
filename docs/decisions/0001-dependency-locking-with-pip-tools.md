# 0001 — Fixar dependências com pip-tools

- **Status:** aceita
- **Data:** 2026-11-20

## Contexto

As convenções do portfólio exigem dependências fixadas por lockfile. O PROJETO.md não define a ferramenta. As opções avaliadas foram o `uv` (rápido, `uv.lock`, mas exige instalação global) e o `pip-tools` (roda dentro do venv, sem nada global).

## Decisão

- As dependências são declaradas em `pyproject.toml`: as de execução em `[project.dependencies]` e as de desenvolvimento no extra `dev`.
- O `pip-tools` (instalado no venv) compila os lockfiles:
  - `requirements.txt`: só execução (usado no Docker);
  - `requirements-dev.txt`: execução + dev (usado localmente e no CI).
- O ambiente é sincronizado com `pip-sync requirements-dev.txt` e o pacote é instalado com `pip install --no-deps -e .`.
- Não usamos `--generate-hashes` por enquanto, para manter simples a instalação editável do próprio pacote. Dá para reavaliar depois.

## Consequências

- Não é preciso instalar nada globalmente. Basta Python 3.12 e um venv.
- O `pip-compile` resolve para a plataforma em que roda. Compilando no Windows, entram pacotes só do Windows (por exemplo, `colorama`), que são inofensivos no Linux. Se algum pacote exclusivo do Linux for necessário no Docker/CI, será preciso recompilar no Linux (ou dentro do container).
- Toda dependência nova exige editar o `pyproject.toml` e recompilar os dois arquivos (comandos no README).
