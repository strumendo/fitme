# CLAUDE.md — pages

Regras pra quem mexe nas páginas Streamlit (`app.py` + `pages/*.py`).
Root [`CLAUDE.md`](../CLAUDE.md) continua sendo a fonte geral; este arquivo
cobre só o que é específico da camada de UI.

## O que vive aqui

```
app.py                  # Landing — "Today" (raiz do projeto, não desta pasta).
pages/
  2_Trends.py           # Charts multi-dia + period deltas.
  3_Activities.py       # Lista de atividades com filtros por tipo/data.
  4_Training.py         # Editor de plano semanal + log de sessão + plan vs actual.
```

Streamlit auto-descobre arquivos sob `pages/` e os ordena pelo prefixo
numérico do filename — `2_Trends.py` aparece como segundo item na sidebar.

## Convenção das páginas

- **Cabeçalho padrão** (todas as páginas começam assim):
  ```python
  from fitme.logging_config import setup as setup_logging
  setup_logging()
  logger = logging.getLogger(__name__)

  st.set_page_config(page_title="fitme — <nome>", page_icon=":<icon>:", layout="wide")
  st.title("<Nome>")
  ```
- **Pages são orquestração fina** — carrega via `queries.*`, transforma via
  `analysis.*`, renderiza via `st.*`. Nada de SQL inline, nada de chamada
  direta ao `garminconnect.Garmin`.
- Conexão ao DB sempre via `with connect() as conn:`. Não persistir o
  `conn` entre reruns (Streamlit reexecuta o script todo).
- Mensagens de UI (`st.error`, `st.warning`, `st.info`) são saída de UI —
  separadas de log. Quando faz sentido, faz os dois: loga o detalhe técnico
  e mostra mensagem limpa pro usuário.

## Receita — adicionar um chart novo na Trends

1. Adiciona `<tabela>_range(conn, start, end) -> list[dict]` em
   `src/fitme/queries.py` se ainda não existir.
2. Na página, converte com `analysis.to_dataframe(rows, value_cols, start, end)` —
   isso reindexa contra o range completo, fazendo dias faltantes aparecerem
   como gaps no chart em vez de zeros.
3. Calcula period deltas com `analysis.period_delta(df, col, days)` e passa
   pro `st.metric`.
4. Overlay de rolling mean 7d via `analysis.rolling(df, window=7)` é
   opcional via `st.toggle`. Default ON pra séries ruidosas (peso, resting
   HR, body battery, stress, HRV); default OFF pro resto.
5. `queries.py` continua dict-based — **não importar pandas lá**, mesmo
   que tente facilitar.

## Receita — adicionar uma página nova

1. Cria `pages/<N>_<Nome>.py`. O `<N>` define a ordem na sidebar (começa em
   2 porque o app.py é a landing).
2. Aplica o cabeçalho padrão.
3. Decide se a página é só leitura (Trends, Activities) ou se tem forms de
   escrita (futuras: Training, Food). Páginas de escrita devem usar
   `st.form` + `st.form_submit_button` pra submissão atômica e validar antes
   de chamar o `repository` (ver fase 4).
4. Atualiza este `CLAUDE.md` se a página introduzir um padrão novo
   (ex.: edit-in-place via `st.data_editor`, filtros multi-select, etc.).
5. Atualiza a seção "Layout" do root `CLAUDE.md` listando o novo arquivo.

## Páginas com escrita — pattern (training, food)

Páginas que mutam estado seguem essa receita:

- Forms via `st.form(...)` + `st.form_submit_button(...)` pra submissão atômica.
  Valida (`activity_type` não pode ser vazio, etc.) antes de chamar o
  `repository`.
- Mutação só via `fitme.repository.*` — nada de `conn.execute("INSERT ...")`
  na página.
- Depois de sucesso, `st.success(...)` curto + `st.rerun()` pra refletir o
  estado novo no próximo render.
- Pra delete inline numa lista, usa `key=f"del_<table>_{id}"` no
  `st.button(...)` pra cada linha ter uma chave única.
- Lê com `queries.*`; cada bloco abre seu próprio `with connect() as conn:`
  (não tenta passar a connection entre seções — Streamlit não persiste).

## Range pickers — pattern compartilhado

Trends e Activities usam o mesmo padrão de seletor de range:

```python
TODAY = date.today()
DEFAULT_DAYS = 30

def _set_range(days: int) -> None:
    st.session_state["<page>_range"] = (TODAY - timedelta(days=days - 1), TODAY)

if "<page>_range" not in st.session_state:
    st.session_state["<page>_range"] = (TODAY - timedelta(days=DEFAULT_DAYS - 1), TODAY)

c7, c30, c90, _ = st.columns([1, 1, 1, 7])
c7.button("7d", on_click=_set_range, args=(7,), use_container_width=True)
# ...
range_value = st.date_input("Date range", value=..., max_value=TODAY, key="<page>_range")
```

Cada página usa a sua própria key em `session_state` (`trends_range`,
`activities_range`, etc.) pra não se atropelarem.

## Referência cruzada

- DB / queries / ingest / Garmin: [`src/fitme/CLAUDE.md`](../src/fitme/CLAUDE.md).
- Roadmap: [`docs/plans/`](../docs/plans/README.md).
- Regras gerais (logging, git authorship, env vars, commands): root
  [`CLAUDE.md`](../CLAUDE.md).
