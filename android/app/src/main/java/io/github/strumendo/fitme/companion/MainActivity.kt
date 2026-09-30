package io.github.strumendo.fitme.companion

import android.os.Bundle
import android.util.Log
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {
    private lateinit var settings: Settings
    private lateinit var reader: SamsungHealthReader

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        settings = Settings(this)
        reader = SamsungHealthReader(this)
        setContent {
            MaterialTheme {
                Surface(Modifier.fillMaxSize()) { Screen() }
            }
        }
    }

    @Composable
    private fun Screen() {
        val scope = rememberCoroutineScope()
        var url by remember { mutableStateOf(settings.receiverUrl) }
        var token by remember { mutableStateOf(settings.token) }
        var periodic by remember { mutableStateOf(settings.periodicSync) }
        var granted by remember { mutableStateOf<Boolean?>(null) }
        var busy by remember { mutableStateOf(false) }
        var message by remember { mutableStateOf(settings.lastResult) }

        LaunchedEffect(Unit) {
            granted = runCatching { reader.hasPermissions() }.getOrDefault(false)
        }

        // Runs one action with the buttons disabled; failures become the status line.
        fun run(action: suspend () -> Unit) {
            busy = true
            scope.launch {
                try {
                    action()
                } catch (e: Exception) {
                    Log.e(TAG, "action failed", e)
                    if (!reader.tryResolve(this@MainActivity, e)) {
                        message = "Erro: ${e.message}"
                    }
                } finally {
                    busy = false
                }
            }
        }

        Column(
            Modifier
                .padding(20.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text("fitme sync", style = MaterialTheme.typography.headlineSmall)

            Text("Samsung Health", style = MaterialTheme.typography.titleMedium)
            Text(
                when (granted) {
                    null -> "Checando permissões…"
                    true -> "Permissões de leitura concedidas."
                    false -> "Sem permissão de leitura. Ative o developer mode no " +
                        "Samsung Health antes (ver README)."
                }
            )
            if (granted == false) {
                Button(enabled = !busy, onClick = {
                    run { granted = reader.requestPermissions(this@MainActivity) }
                }) { Text("Pedir permissões") }
            }

            HorizontalDivider()
            Text("Receiver", style = MaterialTheme.typography.titleMedium)
            OutlinedTextField(
                value = url,
                onValueChange = { url = it },
                label = { Text("URL (ex.: http://192.168.0.10:8765)") },
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri),
                modifier = Modifier.fillMaxWidth(),
            )
            OutlinedTextField(
                value = token,
                onValueChange = { token = it },
                label = { Text("FITME_SYNC_TOKEN") },
                singleLine = true,
                visualTransformation = PasswordVisualTransformation(),
                modifier = Modifier.fillMaxWidth(),
            )
            OutlinedButton(enabled = !busy, onClick = {
                settings.receiverUrl = url
                settings.token = token
                message = "Configuração salva."
            }) { Text("Salvar") }

            Row(verticalAlignment = Alignment.CenterVertically) {
                Switch(checked = periodic, onCheckedChange = { on ->
                    periodic = on
                    settings.periodicSync = on
                    if (on) SyncWorker.schedule(this@MainActivity)
                    else SyncWorker.cancel(this@MainActivity)
                })
                Text("  Sync automático (6h, só Wi-Fi)")
            }

            HorizontalDivider()
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                Button(enabled = !busy && granted == true, onClick = {
                    run {
                        SyncRunner(this@MainActivity, settings).syncNow()
                        message = settings.lastResult
                    }
                }) { Text("Sync agora") }
                OutlinedButton(enabled = !busy && granted == true, onClick = {
                    run {
                        val intent = SyncRunner(this@MainActivity, settings).exportIntent()
                        message = settings.lastResult
                        startActivity(intent)
                    }
                }) { Text("Exportar JSON") }
            }
            if (busy) Text("Trabalhando…")
            if (message.isNotBlank()) Text(message, style = MaterialTheme.typography.bodySmall)
        }
    }

    private companion object {
        const val TAG = "MainActivity"
    }
}
