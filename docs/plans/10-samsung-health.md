# Phase 10 — Samsung Health via companion Android

Status: in progress
Last updated: 2026-09-30

## Goal

Trazer os dados do Samsung Health (composição corporal, nutrição + água,
sono, FC, passos e exercícios) pro `data/fitme.db`, com sync incremental
automático. Como o Samsung Health não tem API web, um **app Android
companion** lê os dados no celular via Samsung Health Data SDK e empurra pro
fitme, que grava em tabelas próprias (`sh_*`) no mesmo esquema do ingest do
Garmin (upsert idempotente + `raw_json`).

## Why now

- O Garmin cobre treino/recovery, mas balança, registro alimentar e relógio
  Galaxy caem no Samsung Health e hoje ficam fora do dashboard.
- O coach de nutrição (fase 9) fica melhor com mais sinal de peso,
  composição e ingestão. O coach de treino (fase 8) ganha com exercícios
  registrados fora do Garmin.

## Decisions (locked)

- **Fonte: Samsung Health Data SDK** (`.aar` v1.1.x, Android 10+, Samsung
  Health ≥ 6.30.2, Java 17, sem emulador). O legado "Samsung Health SDK for
  Android" foi descontinuado em 2025-07-31.
- **Sem parceria Samsung.** Uso pessoal com **Developer mode → "Developer
  Mode for Data Read"** no app Samsung Health (tocar 10x na versão em
  Configurações › Sobre). Só leitura; escrita e distribuição exigiriam
  aprovação de parceiro, e ficam fora de escopo.
- **Tabelas separadas por fonte** (`sh_*`), sem misturar com as tabelas do
  Garmin (`weight`, `sleep`, …). As tabelas do Garmin são chaveadas por
  `date` com `raw_json` do Garmin; misturar fontes quebraria o upsert e o
  backfill. A UI escolhe a fonte (ou combina) na camada de `analysis`.
- **Transporte: payload JSON versionado**, com dois caminhos que usam a
  mesma função de ingest:
  1. **Push HTTP** — `fitme.receiver`, servidor stdlib (`http.server`) na
     LAN, `POST /samsung/sync` com `Authorization: Bearer $FITME_SYNC_TOKEN`.
     O Streamlit não recebe POST, por isso é um processo à parte.
  2. **Arquivo** — o app também exporta o mesmo JSON (share sheet →
     Downloads/Drive), e `python -m fitme.samsung_import <arquivo>` ou um
     upload na página ingere. Serve de fallback quando PC e celular não
     estão na mesma rede.

## Scope

**In:**
- **Contrato do payload** (`schema_version: 1`), um array opcional por
  tipo. Os agregados diários são chaveados por `date`; os demais trazem
  `uid` (Samsung) e `start_time` (+ `end_time` em sono/exercício) em
  ISO-8601 com o offset embutido (`2026-09-28T07:12:00-03:00`). Todos
  trazem `device_group` e os campos do tipo:
  - `steps_daily` — `date`, `steps` (via `DataType.StepsType.TOTAL`
    agrupado DAILY; steps é só aggregate).
  - `heart_rate_daily` — `date`, `min`, `max`, `avg` (aggregates diários
    `HeartRateType.MIN/MAX`; o SDK não agrega média, então o app calcula
    dos pontos brutos de `HEART_RATE`).
  - `sleep` — sessão com `duration_s`, `sleep_score` e totais por estágio
    (`awake_s` / `light_s` / `deep_s` / `rem_s`) em segundos. A `date` é o
    dia em que acordou (`end_time`), igual ao `sleep` do Garmin.
  - `body_composition` — `weight_kg`, `body_fat_pct`,
    `skeletal_muscle_mass_kg`, `muscle_mass_pct`, `bmr_kcal`,
    `total_body_water_l`, `bmi`.
  - `nutrition` — `title`, `meal_type`, `kcal`, `protein_g`, `carbs_g`,
    `fat_g` (+ fibra/açúcar/sódio só no `raw_json`).
  - `water` — `amount_ml`.
  - `exercise` — `exercise_type`, `custom_title`, `duration_s`, `kcal`,
    `distance_m`, `mean_hr`, `max_hr`.
- **Schema v7** — tabelas `sh_steps_daily` / `sh_heart_rate_daily`
  (chave `date`), `sh_sleep`, `sh_body_composition`, `sh_nutrition`,
  `sh_water`, `sh_exercise` (chave `uid`, com `date` local denormalizada).
  Todas com `device_group`, `raw_json`, `fetched_at`. Mais
  `sh_sync_state` (último `synced_at` + `rows` por tipo, pro app pedir só
  o delta).
- **`src/fitme/samsung.py`** — `validate_payload()` e
  `ingest_payload(conn, payload) -> dict[str, int]` (linhas por tipo),
  upsert via `INSERT OR REPLACE`. Sem rede, testável com JSON de fixture.
- **`src/fitme/receiver.py`** — CLI `python -m fitme.receiver --host
  0.0.0.0 --port 8765` (bind default `127.0.0.1`, a LAN é opt-in); valida
  token, tamanho máximo do corpo (10 MB) e JSON, chama
  `samsung.ingest_payload`, devolve contagens. `GET /samsung/status`
  devolve `sh_sync_state` (o app usa pra saber de onde continuar).
- **Queries** — `sh_<tabela>_range(conn, start, end)` seguindo a convenção
  de `queries.py`.
- **UI** — Trends ganha seletor de fonte (Garmin / Samsung) nas métricas
  com sobreposição (peso, sono, FC, passos); Food mostra refeições + água
  do Samsung (só leitura) ao lado do `food_log`; Activities lista
  `sh_exercise` junto das atividades Garmin. Página de sync mostra
  último sync por tipo, instruções de developer mode e upload de arquivo.
- **`android/`** — projeto Gradle Kotlin (minSdk 29, Java 17) com
  `app/libs/` vazio + README explicando baixar o `.aar` da Samsung
  (licença não permite versionar). Telas: pedir permissões, configurar
  URL + token, "Sync agora", "Exportar JSON". `WorkManager` periódico
  (a cada 6h, só em Wi-Fi) usa `sh_sync_state` pra pedir o delta. Export
  JSON cobre sempre os últimos 30 dias.

**Out (deferred):**
- Escrever dados no Samsung Health (exige parceria).
- Health Connect como fonte alternativa (mesmo payload serviria; fica pra
  depois se o SDK Samsung der problema).
- Dados intraday (séries de FC, rota GPS do exercício) — só no `raw_json`.
- Expor o receiver fora da LAN (sem TLS; se precisar, Tailscale).
- Deduplicação automática Garmin × Samsung. A UI deixa escolher a fonte.

## Approach

### Lado Python

- `samsung.py` segue o molde do `ingest.py`: uma função `_upsert_<tipo>`
  por array, erros por registro logados com `logger.warning` e pulados
  (um registro ruim não derruba o lote), `raw_json` = registro original.
- `receiver.py` usa só stdlib (`http.server.ThreadingHTTPServer`), sem
  dependência nova. Token comparado com `hmac.compare_digest`; sem token
  configurado o servidor se recusa a subir.
- O import por arquivo e o receiver chamam a mesma `ingest_payload`.

### Lado Android

- Todo acesso ao SDK fica em `SamsungHealthReader.kt`. O resto do app
  (payload, janela, HTTP, worker, UI) não importa o SDK.
- `HealthDataService.getStore(context)`; permissões
  `Permission.of(DataTypes.X, AccessType.READ)` via
  `getGrantedPermissions` / `requestPermissions` (suspend). Samsung Health
  ausente ou velho vem como `ResolvablePlatformException` →
  `resolve(activity)`.
- Leitura com `DataTypes.X.readDataRequestBuilder` +
  `LocalTimeFilter.of(start, end)`, seguindo `pageToken`. Passos diários
  com `DataType.StepsType.TOTAL.requestBuilder` + `LocalTimeGroup` DAILY;
  FC `HeartRateType.MIN|MAX` usa `LocalDateFilter` + `LocalDateGroup`
  DAILY. `device_group` sai de `dataSource.deviceId` →
  `DeviceManager.getDevice` → `DeviceGroup`.
- Janela de leitura: dia do último `synced_at` menos 2 dias; primeiro sync
  volta 90 dias.
- Gradle segue o codelab da Samsung: `.aar` em `app/libs/` + `gson` +
  plugin `kotlin-parcelize`.
- Serialização com kotlinx.serialization pro contrato acima; POST via
  OkHttp.
- **Não dá pra compilar/testar no ambiente de dev do fitme** (sem Android
  SDK/JDK, e o `.aar` precisa ser baixado à mão). O build e o teste rodam
  no Android Studio, num celular real.

### PR split

1. **PR 1 — contrato + schema + ingest, sem Android (feito).** Schema v7,
   `samsung.py`, `receiver.py`, `samsung_import`, queries, fixture JSON de
   exemplo, docs. Testável com `curl` + fixture.
2. **PR 2 — app Android (código escrito, falta rodar no celular).** Projeto `android/`, permissões, leitura dos 7
   tipos, sync HTTP + export de arquivo, WorkManager.
3. **PR 3 — UI.** Seletor de fonte no Trends, Samsung no Food/Activities,
   página de sync.

## Tasks

1. Contrato do payload documentado + fixture em `docs/samsung-payload.example.json`.
2. Schema v7 (`sh_*` + `sh_sync_state`), migração idempotente.
3. `samsung.validate_payload` / `ingest_payload`.
4. `fitme.receiver` (POST sync, GET status, bearer token, limite de corpo).
5. `fitme.samsung_import` CLI.
6. Queries `sh_*_range`.
7. Projeto `android/` (Gradle, permissões, leitura, serialização, sync,
   export, WorkManager, tela de config).
8. UI: Trends (fonte), Food, Activities, página de sync.
9. Docs no mesmo turno: `src/fitme/CLAUDE.md` (schema v7, módulos, env
   var `FITME_SYNC_TOKEN`, comandos), `pages/CLAUDE.md`, root `CLAUDE.md`
   (layout com `android/`), `.env.example`, README desta pasta.
10. `ruff check .` limpo; `streamlit run app.py` sobe.

## Acceptance

- [x] Migração v7 aplica limpo num DB existente.
- [x] `ingest_payload` com a fixture grava todos os 7 tipos; rodar de novo
      não duplica.
- [x] Receiver rejeita token errado (401), corpo grande (413) e JSON
      inválido (400); aceita o payload válido e devolve contagens.
- [ ] App Android, em celular real com developer mode, pede permissões,
      lê os 7 tipos e sincroniza com o receiver na LAN.
- [ ] Sync incremental: segundo sync só manda o delta desde `sh_sync_state`.
- [ ] Trends mostra peso/sono/FC/passos do Samsung; Food e Activities
      mostram nutrição/água/exercícios do Samsung.
- [ ] Sem regressão: `ruff check` limpo, páginas existentes sobem.

## Open questions

- **Build real.** O código foi escrito com os nomes conferidos na
  referência da API do SDK 1.1.0, mas não foi compilado (sem JDK/SDK no
  ambiente de dev). O primeiro build no Android Studio pode pedir ajustes
  finos, como tipos genéricos dos builders ou getters vs propriedades
  Kotlin.
- **Background.** Não está confirmado que o SDK lê com o app em
  background (WorkManager). Se falhar, o sync automático vira só
  "Sync agora" + export.
- **Registros apagados.** O delta é por janela (`LocalTimeFilter` desde o
  último sync − 2 dias). Registros apagados no Samsung Health não somem do
  fitme (o ingest só faz upsert); `readChanges()` do SDK resolveria isso.
- **Fonte preferida por métrica.** Default Garmin pra sono/FC/passos,
  Samsung pra composição corporal? Decidir no PR 3 com dados reais.
- **Nutrição Samsung × `food_log`.** Só leitura, ou importar pro
  `food_log` pra alimentar o coach de nutrição? v1 é só leitura.

## Cross-phase notes

- Fase 9 (nutrition coach): `nutrition.build_context` pode passar a ler
  `sh_body_composition` / `sh_nutrition` quando o Garmin não tiver o dado.
  Não entra aqui, é follow-up.
- Fase 5 (export/backup) pega as tabelas `sh_*` sozinha via discovery no
  `sqlite_master`.
- Env var nova: `FITME_SYNC_TOKEN` (só o receiver usa).
