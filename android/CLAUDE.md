# CLAUDE.md — android

Regras pro app Android companion (fase 10). O `CLAUDE.md` da raiz continua
valendo; aqui só o que é específico desta subárvore. Setup e uso:
[`README.md`](README.md).

## O que vive aqui

```
android/
  settings.gradle.kts, build.gradle.kts, gradle/libs.versions.toml  # versões só no catalog
  app/libs/            # .aar do Samsung Health Data SDK — gitignored, baixado à mão
  app/src/main/java/io/github/strumendo/fitme/companion/
    Payload.kt              # Contrato do payload (espelho do samsung.py) + isoWithOffset()
    SamsungHealthReader.kt  # ÚNICO arquivo que importa o SDK Samsung
    SyncWindow.kt           # Janela de leitura por tipo (delta + margem / backfill)
    FitmeClient.kt          # OkHttp: GET /samsung/status, POST /samsung/sync
    SyncRunner.kt           # Orquestra status → leitura → POST, e o export JSON
    SyncWorker.kt           # WorkManager periódico (6h, Wi-Fi)
    Settings.kt             # SharedPreferences: URL, token, sync automático, último resultado
    MainActivity.kt         # Tela única em Compose
  app/src/test/...          # Testes JVM do que não depende do SDK
```

## Não compila no ambiente de dev do fitme

Aqui não tem JDK, Android SDK nem o `.aar`. Build, testes e execução rodam
no Android Studio com um celular Samsung real (sem emulador). Quem mexe
aqui sem poder compilar tem que:

- conferir nomes da API do SDK na referência oficial
  (`developer.samsung.com/health/data/api-reference/`), não de memória;
- dizer no PR o que não foi compilado nem testado.

## Convenções

- **SDK isolado.** Só o `SamsungHealthReader.kt` importa
  `com.samsung.android.sdk.health.data`. O resto trabalha com os tipos de
  `Payload.kt`, então dá pra testar na JVM e trocar a fonte (Health Connect)
  sem mexer no resto.
- **Contrato espelhado.** `Payload.kt` e `src/fitme/samsung.py` descrevem o
  mesmo JSON. Mudar um sem o outro quebra o ingest em silêncio: registro sem
  campo obrigatório é pulado e campo novo cai só no `raw_json`. Mudança
  incompatível bumpa `schema_version` dos dois lados.
- **Horário com offset.** Todo `start_time` / `end_time` passa por
  `isoWithOffset()` (ISO-8601 com segundos e o offset do registro), porque o
  fitme tira a `date` local daí. Agregados diários mandam só `date`.
- **Unidades já convertidas no app.** `Duration` vira segundos (`*_s`),
  enums viram `.name` (`LUNCH`, `RUNNING`), BMR `Int` vira float. Detalhes
  do SDK: `MUSCLE_MASS` é %, `TOTAL_BODY_WATER` é litro, água é mL. A FC
  média diária é calculada dos pontos brutos, porque o SDK só agrega
  MIN / MAX.
- **Paginação.** Leitura bruta passa por `readAll`, que segue o `pageToken`.
- **Erros.** Rede (`IOException`) → o worker faz retry. HTTP de erro →
  `ReceiverException`. Samsung Health ausente, velho ou desativado →
  `tryResolve` chama o `resolve(activity)` do SDK.
- **Log** com `android.util.Log` (tag = nome da classe), nunca `println`.
- **UI em PT-BR informal**, código em inglês.
- **Versões** de libs e plugins só no `gradle/libs.versions.toml`.
