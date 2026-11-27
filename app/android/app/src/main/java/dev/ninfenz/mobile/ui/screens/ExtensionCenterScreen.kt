package dev.ninfenz.mobile.ui.screens

import dev.ninfenz.mobile.util.orNullLogged
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
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.text.AnnotatedString
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
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put

/** 本地声明式扩展中心：导入、启停、删除；不执行扩展代码。 */
@Composable
fun ExtensionCenterScreen(onBack: () -> Unit) {
    val context = LocalContext.current
    val clipboard = LocalClipboardManager.current
    val scope = rememberCoroutineScope()
    val store = remember { ExtensionStore(context.filesDir) }
    val trustStore = remember { ExtensionTrustStore(context.filesDir) }
    var trustNonce by remember { mutableStateOf(0) }
    var items by remember { mutableStateOf(store.load()) }
    var error by remember { mutableStateOf<String?>(null) }
    var trustNote by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }

    val picker = rememberExtensionImportPicker(context, scope, store,
        onBusy = { busy = it }, onError = { error = it }, onItems = { items = it })
    val trustPicker = rememberExtensionTrustPicker(context, scope, trustStore,
        onBusy = { busy = it }, onError = { error = it },
        onTrustChanged = { trustNonce += 1 }, onTrustNote = { trustNote = it })

    NfScaffold(title = stringResource(R.string.extensions_title), onBack = onBack) {
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
            OutlinedButton(enabled = !busy, onClick = { picker(arrayOf("application/json", "text/plain")) }) {
                Text(stringResource(R.string.extensions_import))
            }
            TextButton(enabled = !busy, onClick = {
                loadExtensionStarter(context, store, onError = { error = it }, onItems = { items = it })
            }) { Text(stringResource(R.string.extensions_load_starter)) }
        }
        ExtensionTrustRow(
            busy = busy,
            onExport = {
                clipboard.setText(AnnotatedString(trustStore.exportJson()))
                trustNote = context.getString(R.string.extensions_trust_exported)
            },
            onImportTrust = { trustPicker(arrayOf("application/json", "text/plain")) },
            onRevokeAll = {
                trustStore.revokeAll()
                trustNonce += 1
                trustNote = context.getString(R.string.extensions_trust_revoked_all)
            }
        )
        trustNote?.let { Text(it, style = NfType.meta, color = MaterialTheme.colorScheme.primary) }
        error?.let { Text(it, style = NfType.meta, color = MaterialTheme.colorScheme.error) }
        if (items.isEmpty()) {
            EmptyState(stringResource(R.string.extensions_empty))
        } else {
            ExtensionsList(
                items = items,
                store = store,
                trustStore = trustStore,
                trustNonce = trustNonce,
                onTrustNonceChange = { trustNonce = it },
                onItemsChange = { items = it },
                onError = { error = it }
            )
        }
    }
}

@Composable
private fun rememberExtensionImportPicker(
    context: android.content.Context,
    scope: kotlinx.coroutines.CoroutineScope,
    store: ExtensionStore,
    onBusy: (Boolean) -> Unit,
    onError: (String?) -> Unit,
    onItems: (List<ExtensionStore.Installed>) -> Unit
): (Array<String>) -> Unit {
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        if (uri == null) return@rememberLauncherForActivityResult
        scope.launch {
            onBusy(true)
            onError(null)
            try {
                store.install(FileAccess.readText(context, uri))
                onItems(store.load())
            } catch (e: Exception) {
                onError((e as? ModelException)?.message ?: (e.message ?: e.javaClass.simpleName))
            } finally {
                onBusy(false)
            }
        }
    }
    return { input -> picker.launch(input) }
}

@Composable
private fun rememberExtensionTrustPicker(
    context: android.content.Context,
    scope: kotlinx.coroutines.CoroutineScope,
    trustStore: ExtensionTrustStore,
    onBusy: (Boolean) -> Unit,
    onError: (String?) -> Unit,
    onTrustChanged: () -> Unit,
    onTrustNote: (String?) -> Unit
): (Array<String>) -> Unit {
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        if (uri == null) return@rememberLauncherForActivityResult
        scope.launch {
            onBusy(true)
            try {
                trustStore.importJson(FileAccess.readText(context, uri))
                onTrustChanged()
                onTrustNote(context.getString(R.string.extensions_trust_imported))
                onError(null)
            } catch (e: Exception) {
                onError(context.getString(R.string.extensions_trust_invalid, e.message ?: e.javaClass.simpleName))
            } finally {
                onBusy(false)
            }
        }
    }
    return { input -> picker.launch(input) }
}

@Composable
private fun ExtensionTrustRow(
    busy: Boolean,
    onExport: () -> Unit,
    onImportTrust: () -> Unit,
    onRevokeAll: () -> Unit
) {
    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
        TextButton(enabled = !busy, onClick = onExport) { Text(stringResource(R.string.extensions_trust_export)) }
        TextButton(enabled = !busy, onClick = onImportTrust) { Text(stringResource(R.string.extensions_trust_import)) }
        TextButton(enabled = !busy, onClick = onRevokeAll) { Text(stringResource(R.string.extensions_trust_revoke_all)) }
    }
}

private fun loadExtensionStarter(
    context: android.content.Context,
    store: ExtensionStore,
    onError: (String?) -> Unit,
    onItems: (List<ExtensionStore.Installed>) -> Unit
) {
    val text = store.starterJson(context)
    if (text == null) {
        onError(context.getString(R.string.extensions_starter_missing))
    } else {
        runCatching { store.install(text) }.onFailure { onError(it.message ?: it.javaClass.simpleName) }
        onItems(store.load())
    }
}

@Composable
private fun ExtensionsList(
    items: List<ExtensionStore.Installed>,
    store: ExtensionStore,
    trustStore: ExtensionTrustStore,
    trustNonce: Int,
    onTrustNonceChange: (Int) -> Unit,
    onItemsChange: (List<ExtensionStore.Installed>) -> Unit,
    onError: (String?) -> Unit
) {
    LazyColumn(verticalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
        items(items, key = { it.id }) { ext ->
            val digest = store.manifestDigest(ext.id)
            val trustedEntry = trustNonce.let { trustStore.entry(ext.id) }
            val trusted = digest != null && trustedEntry?.digest == digest
            CardBox(title = ext.id) {
                Text(ext.type, style = NfType.meta, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Text(
                    (if (ext.signed) stringResource(R.string.extensions_signed) else stringResource(R.string.extensions_unsigned)) +
                        " · " + pluralStringResource(R.plurals.extensions_contributions, ext.contributions.size, ext.contributions.size),
                    style = NfType.meta
                )
                ExtensionTrustSection(ExtensionTrustSectionArgs(ext, digest, trustedEntry, trusted, store, trustStore, trustNonce, onTrustNonceChange, onError))
                if (ext.targets.isNotEmpty()) Text(ext.targets.joinToString(" · "), style = NfType.meta)
                if (ext.warnings.isNotEmpty()) {
                    Text(ext.warnings.joinToString("; "), style = NfType.meta, color = MaterialTheme.colorScheme.error)
                }
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(stringResource(R.string.extensions_enabled), style = NfType.meta, modifier = Modifier.weight(1f))
                    Switch(
                        checked = ext.enabled,
                        onCheckedChange = { on -> store.setEnabled(ext.id, on); onItemsChange(store.load()) }
                    )
                }
                TextButton(onClick = { store.remove(ext.id); onItemsChange(store.load()) }) {
                    Text(stringResource(R.string.extensions_delete))
                }
            }
        }
    }
}

internal data class ExtensionTrustSectionArgs(
    val ext: ExtensionStore.Installed,
    val digest: String?,
    val trustedEntry: ExtensionTrustStore.Entry?,
    val trusted: Boolean,
    val store: ExtensionStore,
    val trustStore: ExtensionTrustStore,
    val trustNonce: Int,
    val onTrustNonceChange: (Int) -> Unit,
    val onError: (String?) -> Unit,
)

@Composable
private fun ExtensionTrustSection(args: ExtensionTrustSectionArgs) {
    with(args) {
    if (!ext.signed) return
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    if (trusted) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(stringResource(R.string.extensions_trusted), style = NfType.meta, color = MaterialTheme.colorScheme.primary, modifier = Modifier.weight(1f))
            TextButton(onClick = { trustStore.revoke(ext.id); onTrustNonceChange(trustNonce + 1) }) {
                Text(stringResource(R.string.extensions_trust_revoke))
            }
        }
        trustedEntry?.fingerprint?.takeIf { it.isNotBlank() }?.let { fingerprint ->
            Text(
                stringResource(R.string.extensions_trust_fingerprint, fingerprint.take(16)),
                style = NfType.meta,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
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
                        val fingerprint = runCatching {
                            Json.parseToJsonElement(raw).jsonObject["signature"]
                                ?.jsonObject?.get("public_key")?.jsonPrimitive?.content
                        }.orNullLogged("ExtensionCenterScreen")?.let { ExtensionTrustStore.fingerprint(it) }.orEmpty()
                        trustStore.trust(ext.id, digestNow, fingerprint)
                        onTrustNonceChange(trustNonce + 1)
                    } else {
                        onError(response.error?.message ?: context.getString(R.string.extensions_verify_failed))
                    }
                } catch (e: Exception) {
                    onError(e.message ?: context.getString(R.string.extensions_verify_failed))
                }
            }
        }) { Text(stringResource(R.string.extensions_trust)) }
    }

    }
}