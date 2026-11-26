package dev.ninfenz.mobile.ui.screens

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import dev.ninfenz.mobile.R
import dev.ninfenz.mobile.core.ModelException
import dev.ninfenz.mobile.data.ExtensionStore
import dev.ninfenz.mobile.data.ExtensionTrustStore
import dev.ninfenz.mobile.core.J
import dev.ninfenz.mobile.data.FileAccess
import dev.ninfenz.mobile.ui.components.CardBox
import dev.ninfenz.mobile.ui.components.EmptyState
import dev.ninfenz.mobile.ui.components.NfScaffold
import dev.ninfenz.mobile.ui.design.NfType
import dev.ninfenz.mobile.ui.safeCall
import dev.ninfenz.mobile.ui.theme.NfSpacing
import kotlinx.coroutines.launch
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

/** 本地声明式扩展中心：导入、启停、删除；不执行扩展代码。 */
@Composable
fun ExtensionCenterScreen(onBack: () -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val store = remember { ExtensionStore(context.filesDir) }
    val trustStore = remember { ExtensionTrustStore(context.filesDir) }
    var trustNonce by remember { mutableStateOf(0) }
    var items by remember { mutableStateOf(store.load()) }
    var error by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }

    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        if (uri == null) return@rememberLauncherForActivityResult
        scope.launch {
            busy = true
            error = null
            try {
                val text = FileAccess.readText(context, uri)
                store.install(text)
                items = store.load()
            } catch (e: Exception) {
                error = (e as? ModelException)?.message ?: (e.message ?: e.javaClass.simpleName)
            } finally {
                busy = false
            }
        }
    }

    NfScaffold(title = stringResource(R.string.extensions_title), onBack = onBack) {
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
            OutlinedButton(enabled = !busy, onClick = { picker.launch(arrayOf("application/json", "text/plain")) }) {
                Text(stringResource(R.string.extensions_import))
            }
            TextButton(enabled = !busy, onClick = {
                val text = store.starterJson(context)
                if (text == null) {
                    error = context.getString(R.string.extensions_starter_missing)
                } else {
                    runCatching { store.install(text) }
                        .onFailure { error = it.message ?: it.javaClass.simpleName }
                    items = store.load()
                }
            }) { Text(stringResource(R.string.extensions_load_starter)) }
        }
        error?.let { Text(it, style = NfType.meta, color = MaterialTheme.colorScheme.error) }
        if (items.isEmpty()) {
            EmptyState(stringResource(R.string.extensions_empty))
        } else {
            LazyColumn(verticalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                items(items, key = { it.id }) { ext ->
                    val digest = store.manifestDigest(ext.id)
                    val trusted = trustNonce.let { digest != null && trustStore.isTrusted(ext.id, digest) }
                    CardBox(title = ext.id) {
                        Text(ext.type, style = NfType.meta, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Text(
                            (if (ext.signed) stringResource(R.string.extensions_signed) else stringResource(R.string.extensions_unsigned)) +
                                " · " + pluralStringResource(R.plurals.extensions_contributions, ext.contributions.size, ext.contributions.size),
                            style = NfType.meta
                        )
                        if (ext.signed) {
                            if (trusted) {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Text(stringResource(R.string.extensions_trusted), style = NfType.meta, color = MaterialTheme.colorScheme.primary, modifier = Modifier.weight(1f))
                                    TextButton(onClick = { trustStore.revoke(ext.id); trustNonce++ }) {
                                        Text(stringResource(R.string.extensions_trust_revoke))
                                    }
                                }
                            } else {
                                TextButton(onClick = {
                                    scope.launch {
                                        val raw = store.rawManifest(ext.id)
                                        val digestNow = digest
                                        if (raw == null || digestNow == null) return@launch
                                        try {
                                            val response = safeCall("extension-verify", buildJsonObject {
                                                put("manifest", J.parseObject(raw, "nf-extension/1"))
                                                put("strict", true)
                                            })
                                            if (response.ok) {
                                                trustStore.trust(ext.id, digestNow)
                                                trustNonce++
                                            } else {
                                                error = response.error?.message ?: context.getString(R.string.extensions_verify_failed)
                                            }
                                        } catch (e: Exception) {
                                            error = e.message ?: context.getString(R.string.extensions_verify_failed)
                                        }
                                    }
                                }) { Text(stringResource(R.string.extensions_trust)) }
                            }
                        }
                        if (ext.targets.isNotEmpty()) Text(ext.targets.joinToString(" · "), style = NfType.meta)
                        if (ext.warnings.isNotEmpty()) {
                            Text(ext.warnings.joinToString("; "), style = NfType.meta, color = MaterialTheme.colorScheme.error)
                        }
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(stringResource(R.string.extensions_enabled), style = NfType.meta, modifier = Modifier.weight(1f))
                            Switch(
                                checked = ext.enabled,
                                onCheckedChange = { on -> store.setEnabled(ext.id, on); items = store.load() }
                            )
                        }
                        TextButton(onClick = { store.remove(ext.id); items = store.load() }) {
                            Text(stringResource(R.string.extensions_delete))
                        }
                    }
                }
            }
        }
    }
}
