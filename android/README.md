# fitme sync — app Android companion

Lê os dados do Samsung Health no celular (Samsung Health Data SDK) e manda
pro fitme: por HTTP pro `fitme.receiver` na LAN ou exportando um JSON pro
`fitme.samsung_import`. Contexto e decisões:
[`docs/plans/10-samsung-health.md`](../docs/plans/10-samsung-health.md).

## Requisitos

- Celular Samsung com Android 10+ e Samsung Health 6.30.2+. **O emulador
  não funciona**, o SDK exige aparelho real.
- Android Studio com JDK 17.
- Samsung Health Data SDK `.aar` (v1.1.0 ou mais nova).

## Setup

1. **Baixa o SDK.** Pega o `samsung-health-data-api-<versão>.aar` em
   <https://developer.samsung.com/health/data/overview.html> e copia pra
   `android/app/libs/`. Ele é gitignored porque a licença não permite
   versionar. O Gradle pega qualquer `.aar` dessa pasta.
2. **Ativa o developer mode no Samsung Health.** Sem parceria com a
   Samsung, é o que libera a leitura:
   1. Samsung Health › ⋮ › Configurações › Sobre o Samsung Health.
   2. Toca na linha da versão umas 10 vezes seguidas.
   3. Entra em "Developer mode (Samsung Health Data SDK)" e aceita o aviso.
   4. Liga **Developer Mode for Data Read**.
3. **Abre `android/` no Android Studio.** Não tem `gradlew` versionado. O
   Studio usa o `gradle/wrapper/gradle-wrapper.properties` direto; se quiser
   o script, roda `gradle wrapper` uma vez. Aceitar os upgrades de
   AGP / Kotlin / libs que o Studio sugerir é tranquilo.
4. **Sobe o receiver no PC**, na mesma rede do celular:
   ```bash
   # .env: FITME_SYNC_TOKEN=<token>  (python -c 'import secrets; print(secrets.token_urlsafe(32))')
   uv run python -m fitme.receiver --host 0.0.0.0 --port 8765
   ```
5. **Roda o app no celular.** Toca "Pedir permissões", preenche a URL
   (`http://<ip-do-pc>:8765`) e o mesmo token, "Salvar", "Sync agora".

## Como funciona

- **Sync agora**: `GET /samsung/status` devolve o último `synced_at` de cada
  tipo. O app relê a partir desse dia menos 2 dias (margem pra edições
  tardias) ou dos últimos 90 dias no primeiro sync, e faz o
  `POST /samsung/sync`. O ingest do fitme é idempotente, então reler não
  duplica.
- **Sync automático**: um `WorkManager` periódico faz a mesma coisa a cada
  6h, só em Wi-Fi. Se o receiver não responder (fora de casa, PC
  desligado), tenta de novo depois.
- **Exportar JSON**: gera o payload dos últimos 30 dias e abre o share sheet
  (Drive, Downloads, e-mail). No PC:
  `uv run python -m fitme.samsung_import <arquivo.json>`.

O app fala HTTP puro (`usesCleartextTraffic`), porque o receiver é só pra
LAN. Fora de casa, usa o export ou uma VPN tipo Tailscale.
