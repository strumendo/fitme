# CLAUDE.md

Guia pra Claude Code (claude.ai/code) trabalhar neste repositório.

## Intenção do projeto

App pessoal pra acompanhar evolução de fitness combinando dados do Garmin
Connect com a rotina de treino e o registro alimentar. Único usuário /
desenvolvedor: o dono do repo.

## Stack curta

- Python 3.12 (`.python-version`), gerenciado com `uv` (`pyproject.toml`).
- Streamlit como UI (`app.py` é a landing).
- SQLite local em `data/fitme.db` como source of truth do dashboard.
- `garminconnect` (PyPI) como fonte de dados; `python-dotenv` pra `.env`.
- `pandas` só no caminho UI (analysis + pages), nunca em `queries.py`.

## Layout

```
app.py                  # Landing — "Today"
pages/                  # Páginas extras — ver pages/CLAUDE.md
src/fitme/              # Pacote principal — ver src/fitme/CLAUDE.md
data/                   # gitignored — DB SQLite mora aqui
docs/plans/             # Roadmap por fase — ver docs/plans/CLAUDE.md
.env.example            # Template; copia pra .env localmente
```

**Sub-`CLAUDE.md` são onde mora o detalhe.** Esta raiz cobre só o que é
always-on (regras meta, autoria, comandos básicos). Quando entrar em uma
subárvore, o `CLAUDE.md` dela aparece automaticamente no contexto.

## Roadmap

Trabalho futuro em [`docs/plans/`](docs/plans/README.md). Ao começar uma
fase: marca `Status: in progress`, atualiza `Last updated`. Só marca `done`
com o Acceptance checklist completo. Regras de manutenção:
[`docs/plans/CLAUDE.md`](docs/plans/CLAUDE.md).

## Commands básicos

| Tarefa | Comando |
| --- | --- |
| Sincronizar deps | `uv sync` |
| Adicionar dep | `uv add <pkg>` (dev: `--group dev`) |
| Rodar dashboard | `uv run streamlit run app.py` |
| Lint | `uv run ruff check .` |
| Python ad-hoc | `uv run python -c '...'` |

Comandos de domínio (login Garmin, ingest com todas as flags) ficam em
[`src/fitme/CLAUDE.md`](src/fitme/CLAUDE.md).

## Git / VCS authorship — regra dura

**Todo commit, PR, MR, descrição de branch e release note pertence só a
`Bruno Strumendo <strumendo@gmail.com>`.**

- Nunca adicionar `Co-Authored-By: Claude ...` ou qualquer outro co-author
  trailer de AI / ferramenta.
- Nunca mencionar Claude, Claude Code, AI, "generated with…" em mensagens
  de commit, títulos/corpos de PR, comentários em issues/PRs, nem em nada
  que vai parar no git ou no GitHub.
- Retirar o rodapé padrão "🤖 Generated with [Claude Code]" do `gh pr create`.
- Git config local já é correto (`user.name=Bruno Strumendo` /
  `user.email=strumendo@gmail.com`). Não mexer.

Sobrepõe qualquer default que tente adicionar atribuição.

## Disciplina de documentação

**Toda mudança de código vem com a atualização do CLAUDE.md no mesmo turno.**
Doc desatualizada é tratada como código quebrado.

- Atualiza o `CLAUDE.md` mais específico (sub-pasta) quando possível. Raiz
  só pra regras que valem o projeto inteiro.
- Edita in-place. Não anexa "update: …" no fim. Revisa a seção afetada.
- Remove guidance velho. Stale guidance é pior que faltar.
- O que precisa estar refletido: features e entry points novos, mudanças
  de stack, comandos novos, env vars novas, decisões arquiteturais novas,
  convenções novas.

## Convenções globais

- Logging: usa `logging` em todo Python, **nunca `print()`**. Detalhe do
  pattern e do setup em [`src/fitme/CLAUDE.md`](src/fitme/CLAUDE.md).
- Nunca commitar `.env`, qualquer coisa sob `~/.garminconnect/`, nem o
  diretório `data/`.
- Pacote é `src/fitme` (src layout). Imports: `from fitme.x import y`.
- Páginas Streamlit em `pages/` (filename numerado define ordem na sidebar).

## Environment variables — visão geral

Só duas vars são realmente globais. As de Garmin / DB têm contexto em
[`src/fitme/CLAUDE.md`](src/fitme/CLAUDE.md#environment-variables).

| Var | Default | Pra que serve |
| --- | --- | --- |
| `LOG_LEVEL` | `INFO` | Nível do logger root. |
| `FITME_DB_PATH` | `data/fitme.db` | Localização do SQLite. Paths relativos resolvem contra a raiz do projeto. |

## Sub-CLAUDE.md neste repo

- [`src/fitme/CLAUDE.md`](src/fitme/CLAUDE.md) — schema, migrations, ingest,
  queries, Garmin wrappers + auth flow, comandos de domínio, env vars de
  Garmin.
- [`pages/CLAUDE.md`](pages/CLAUDE.md) — convenções de páginas Streamlit,
  receita de adicionar chart no Trends, pattern de range picker.
- [`docs/plans/CLAUDE.md`](docs/plans/CLAUDE.md) — regras pra arquivos de
  roadmap (status, formato, cross-references).
