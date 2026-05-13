# CLAUDE.md — src/fitme

Regras de quem mexe nos módulos Python do `src/fitme/`. O `CLAUDE.md` da raiz
é a fonte de verdade do projeto inteiro; este arquivo só cobre o que é
específico desta subárvore (DB, ingest, Garmin wrappers, queries).

## O que vive aqui

```
src/fitme/
  config.py         # Carrega .env num Settings dataclass.
  garmin.py         # get_client() + wrappers finos sobre garminconnect.
  login.py          # Login interativo único (lida com MFA).
  logging_config.py # setup() — chamado uma vez por entry point.
  db.py             # connect() context manager — abre SQLite + roda migrações.
  db_schema.py      # SCHEMA_VERSION + migrações forward escritas à mão.
  queries.py        # Read helpers por tabela (devolvem dict, sem pandas).
  repository.py     # Write helpers (insert/update/delete) das tabelas manuais.
  analysis.py       # Transforms pandas usadas pelas pages.
  ingest.py         # CLI + funções ingest_* idempotentes.
  export.py         # CLI + funções de export CSV / snapshot SQLite.
  openfoodfacts.py  # Cliente fino sobre a API pública do Open Food Facts.
```

## Data flow

O Garmin Connect **não** é chamado em cada render da dashboard. O modelo é:

1. **Ingest** (manual, via CLI) puxa dados do Garmin pra SQLite local em
   `data/fitme.db`. Cada métrica é upserted por data — re-rodar é seguro.
2. **Dashboard** lê do DB via `fitme.queries`. Quando uma data não tem linha,
   a UI mostra um banner com botão "Fetch from Garmin for <date>" que
   dispara um ingest ad-hoc só pra aquele dia.
3. O payload Garmin completo fica gravado na coluna `raw_json` de cada
   tabela, pra versões futuras de schema poderem backfillar campos novos
   sem precisar bater de novo na API.

## Schema — versão atual e tabelas

`SCHEMA_VERSION` atual: **3**.

| Tabela | Chave | Fonte | Notas |
| --- | --- | --- | --- |
| `daily_summary` | `date` | `get_user_summary` | passos, distância, calorias, minutos ativos, andares |
| `heart_rate` | `date` | `get_heart_rates` | resting / max / min / avg |
| `sleep` | `date` | `get_sleep_data` | total + deep / light / REM / awake em segundos |
| `weight` | `date` | `get_body_composition` | peso + body fat / water / muscle / bone |
| `body_battery` | `date` | `get_body_battery` | charged, drained, highest, lowest (derivados do array intraday) |
| `stress` | `date` | `get_stress_data` | avg / max + rest / low / medium / high em segundos |
| `hrv` | `date` | `get_hrv_data` | last-night avg, weekly avg, status |
| `activities` | `activity_id` | `get_activities_by_date` | range-ingested, coluna `date` denormalizada de `startTimeLocal` |
| `training_plan` | `plan_id` | manual (UI) | template semanal versionado por `effective_from`; UNIQUE(`effective_from`, `weekday`, `slot`) |
| `training_log` | `log_id` | manual (UI) | sessão registrada à mão; `garmin_activity_id` opcional referencia `activities.activity_id` |
| `food_log` | `food_id` | manual (UI) | entrada por refeição com kcal + macros (protein/carbs/fat) |

## Schema migrations — disciplina

- Toda mudança de schema passa por `db_schema.py`. **Não fazer `ALTER` ad-hoc.**
- Bumpa `SCHEMA_VERSION` e adiciona uma função `_migrate_vN(conn)`.
- Registra no dict `_MIGRATIONS`.
- Sem down-migrations. Sem ORM.
- `db.connect()` lê `schema_version`, compara com `SCHEMA_VERSION`, e aplica
  as migrações que faltam em cada conexão.

## Ingest pattern

Existem dois sabores de métrica, definidos em tuplas no topo do `ingest.py`:

- **`PER_DAY_METRICS`** — uma chamada Garmin por dia. Função tem assinatura
  `ingest_<metric>(client, conn, day: date) -> bool`. Registrada em
  `INGESTERS`. O `ingest_range` itera dia a dia.
- **`RANGE_METRICS`** — uma chamada Garmin cobre a janela inteira (ex.:
  `activities`). Função tem assinatura
  `ingest_<metric>(client, conn, start: date, end: date) -> int` (devolve
  número de linhas escritas). Chamada uma vez por execução, após o loop
  por dia.

Em ambos os casos:
- Upsert via `INSERT OR REPLACE`, chaveado por `date` (ou `activity_id` em
  activities).
- Coluna `raw_json` sempre populada com o payload bruto da API
  (`json.dumps(payload)`).
- Coluna `fetched_at` sempre populada via `_now_iso()`.
- Falhas de fetch são caçadas com `logger.exception(...)` e devolvem
  `False` / `0` — nunca propagam pro CLI.
- Quando o payload existe mas vem vazio (ex.: HRV sem device support),
  loga `logger.info("no <metric> data for %s", day)` e devolve `False`.

## CLI — adicionando uma métrica nova ao `--metrics`

1. Adiciona o nome à tupla certa (`PER_DAY_METRICS` ou `RANGE_METRICS`).
2. Garante que está em `METRICS` (que é o default e o que `all` expande).
3. Se for per-day, registra em `INGESTERS`.
4. `_parse_metrics` já valida contra `METRICS` — não precisa mexer.

## Queries — convenção

- `queries.py` devolve **`dict`** (ou `list[dict]`, ou `None`). **Nunca** importa
  pandas aqui.
- Single-day: `get_<table>(conn, day) -> dict | None`.
- Range: `<table>_range(conn, start, end) -> list[dict]`.
- Filtros adicionais (ex.: `activities_range(..., activity_type=...)`) viram
  parâmetros nomeados opcionais.
- Pandas vive em `analysis.py` e nas pages. `queries` continua testável sem
  pandas no loop.

## Repository (writes) — convenção

`repository.py` é o dual write-side do `queries.py`. Páginas Streamlit **não**
escrevem direto via SQL — chamam funções daqui.

- Funções são `insert_<table>`, `update_<table>(id, ...)`, `delete_<table>(id)`.
  `training_plan` usa `upsert_training_plan_slot(...)` porque a UNIQUE
  constraint em (`effective_from`, `weekday`, `slot`) torna o save idempotente.
- Argumentos opcionais ficam keyword-only com default `None` (forms da UI
  passam ou não passam macros / notes; SQL guarda `NULL`).
- `created_at` / `updated_at` são preenchidos via `_now_iso()` (mesmo formato
  UTC ISO-8601 do `ingest.py`).
- Sem pandas, sem Garmin client aqui — só `sqlite3.Connection`. Testável em
  isolamento.

## Garmin wrappers

- Tudo que toca o cliente Garmin entra em `garmin.py` como função fina que
  recebe o `Garmin` client. Padrão: `def <metric>(client, day_or_range) -> payload`.
- Páginas Streamlit **não** chamam métodos do `garminconnect.Garmin`
  diretamente — passam pelo wrapper. Isso centraliza caching / retry /
  logging quando a gente quiser adicionar.

## Open Food Facts wrappers

- `openfoodfacts.py` é o equivalente do `garmin.py` pra API pública do OFF.
  Usa stdlib `urllib.request` (sem dep nova).
- API pública: `search(query, lang="pt", page_size=10)` e
  `lookup_barcode(code)`. Ambas devolvem dicts normalizados — chaves
  `code`, `name`, `brand`, `kcal_per_100g`, `protein_per_100g`,
  `carbs_per_100g`, `fat_per_100g`, `image_url`.
- Falhas (timeout, sem rede, JSON ruim) viram `[]` / `None` — nunca
  propagam exceção pra UI. Log via `logger.warning` / `logger.exception`.
- Caching é responsabilidade da UI (`@st.cache_data(ttl=86_400)` na
  `5_Food.py`). Mantém o módulo testável sem Streamlit.
- User-Agent identifica o app (`fitme/0.1`). OFF pede isso em clientes.

## Commands de domínio

Comandos básicos de dev (`uv sync`, `streamlit run`, lint) ficam no root
`CLAUDE.md`. Aqui vão os específicos deste pacote.

| Tarefa | Comando |
| --- | --- |
| Login Garmin único (lida com MFA, cacheia tokens) | `uv run python -m fitme.login` |
| Ingest últimos 30 dias | `uv run python -m fitme.ingest --since 30d` |
| Ingest range específico | `uv run python -m fitme.ingest --from 2026-04-01 --to 2026-04-30` |
| Ingest um dia só | `uv run python -m fitme.ingest --date 2026-05-10` |
| Ingest subset de métricas | `uv run python -m fitme.ingest --since 7d --metrics summary,sleep` |
| Ingest tudo (todas as 8 métricas) | `uv run python -m fitme.ingest --since 30d --metrics all` |
| Export CSV (todas as tabelas) | `uv run python -m fitme.export csv` |
| Export CSV com `raw_json` | `uv run python -m fitme.export csv --include-raw` |
| Export subset de tabelas | `uv run python -m fitme.export csv --tables training_log,food_log` |
| Snapshot SQLite consistente | `uv run python -m fitme.export sqlite` |

Nomes válidos pra `--metrics`: `summary`, `heart_rate`, `sleep`, `weight`,
`body_battery`, `stress`, `hrv`, `activities`, ou `all`.

Outputs do `fitme.export` caem em `data/exports/<utc-iso>/` (CSV) ou
`data/exports/fitme-<utc-iso>.db` (snapshot) por default. Override com
`--to`. O `data/` inteiro já é gitignored.

## Environment variables

| Var | Default | Pra que serve |
| --- | --- | --- |
| `GARMIN_EMAIL` | — | Login Garmin Connect. Necessário no primeiro auth; depois usa token cacheado. |
| `GARMIN_PASSWORD` | — | Idem. |
| `GARMINTOKENS` | `~/.garminconnect` | Onde a lib `garminconnect` cacheia tokens OAuth. |

`LOG_LEVEL` e `FITME_DB_PATH` são globais — documentadas no root.

## Logging — pattern detalhado

Regra "nunca usar `print()`" está no root. Aqui ficam os detalhes:

- Cada módulo declara seu logger no topo:
  ```python
  import logging
  logger = logging.getLogger(__name__)
  ```
- Cada entry point (`app.py`, `src/fitme/login.py`, CLIs futuros) chama
  `fitme.logging_config.setup()` **uma vez** antes de qualquer outro código.
  Configura formato + nível (override via `LOG_LEVEL`) e abafa o logger do
  `garminconnect` pra WARNING.
- Usa formatação lazy `%` (`logger.info("Got %s", x)`), não f-string, pra
  mensagem não ser construída quando o nível tiver filtrado.
- Pra exceptions onde o stacktrace importa, usa `logger.exception(...)`
  (só dentro de `except`); pra falhas esperadas usa `logger.warning` /
  `logger.error` com mensagem curta.
- Chamadas de UI do Streamlit (`st.error`, `st.warning`, `st.info`) são
  **saída de UI, não log** — são OK. Muitas vezes vale fazer os dois: loga
  o detalhe técnico, mostra mensagem limpa pro usuário.
- Pra tracing ad-hoc, sobe pra DEBUG via `LOG_LEVEL=DEBUG` no `.env` e usa
  `logger.debug(...)`. Sem `console.log`-style prints, mesmo em dev.

## Garmin auth flow

1. Primeira vez: copia `.env.example` → `.env`, preenche `GARMIN_EMAIL` /
   `GARMIN_PASSWORD`, roda `uv run python -m fitme.login`. Lida com MFA
   interativamente e cacheia tokens OAuth em `$GARMINTOKENS`
   (default `~/.garminconnect/`).
2. Runs seguintes: `fitme.garmin.get_client()` restaura tokens cached em
   silêncio — sem senha, sem MFA, até o refresh token expirar.
3. **Streamlit não consegue rodar o prompt interativo de MFA**, então a
   dashboard depende dos tokens cached. Se `get_client()` levantar
   `GarminAuthError`, a UI mostra mensagem pedindo pra rodar `fitme.login`
   no terminal.

Não adiciona tratamento de senha no `app.py` — auth fica em `garmin.py` e
`login.py`.

## Referência cruzada

- Roadmap e plano por fase: [`docs/plans/`](../../docs/plans/README.md).
- Convenções de páginas Streamlit: [`pages/CLAUDE.md`](../../pages/CLAUDE.md).
- Regras gerais do projeto (logging, git authorship, env vars): root
  [`CLAUDE.md`](../../CLAUDE.md).
