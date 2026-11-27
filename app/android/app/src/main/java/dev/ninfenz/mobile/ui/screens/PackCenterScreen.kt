package dev.ninfenz.mobile.ui.screens

import androidx.compose.ui.unit.dp

import androidx.compose.foundation.layout.size
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.ui.platform.LocalDensity

import dev.ninfenz.mobile.ui.design.NfType

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
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
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import dev.ninfenz.mobile.data.UriIo
import dev.ninfenz.mobile.data.PackEntry
import dev.ninfenz.mobile.data.PackZipInstaller
import dev.ninfenz.mobile.data.PackTrustStore
import dev.ninfenz.mobile.data.ProjectEntry
import dev.ninfenz.mobile.data.PackVerifier
import dev.ninfenz.mobile.ui.components.NfCard
import dev.ninfenz.mobile.ui.components.NfEmptyState
import dev.ninfenz.mobile.ui.components.NfErrorCard
import dev.ninfenz.mobile.ui.components.NfSectionHeader
import dev.ninfenz.mobile.ui.components.NfStatusChip
import dev.ninfenz.mobile.ui.components.NfTopAppBar
import dev.ninfenz.mobile.ui.theme.NfSpacing
import java.io.File

private fun formatInstalledAt(at: Long): String = if (at <= 0) {
    "-"
} else {
    java.text.SimpleDateFormat("yyyy-MM-dd HH:mm", java.util.Locale.getDefault()).format(java.util.Date(at))
}

/** W5 Pack 中心：已装列表 + 逐 Pack 校验 + 详情/更新入口（diff/冲突/回滚仍在 PackUpdate）。 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PackCenterScreen(
    packs: List<PackEntry>,
    projects: List<ProjectEntry> = emptyList(),
    onUninstall: (PackEntry) -> Unit = {},
    onBack: () -> Unit,
    onOpenPack: (PackEntry) -> Unit,
    onUpdatePlan: () -> Unit,
    onLoadSample: () -> Unit,
    onNewPackDraft: () -> Unit = {},
    refreshing: Boolean = false,
    onRefresh: () -> Unit = {}
) {
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    val audit = dev.ninfenz.mobile.data.FeatureGate.auditEnabled()
    val trust = remember { PackTrustStore(context.filesDir).load() }
    var verifyingId by remember { mutableStateOf<String?>(null) }
    var results by remember { mutableStateOf<Map<String, String>>(emptyMap()) }
    var errors by remember { mutableStateOf<Map<String, String>>(emptyMap()) }
    var pendingUninstall by remember { mutableStateOf<PackEntry?>(null) }
    var uninstallErrors by remember { mutableStateOf<Map<String, String>>(emptyMap()) }
    var packQuery by remember { mutableStateOf("") }

    val zipPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        if (uri == null) return@rememberLauncherForActivityResult
        scope.launch {
            val result = runCatching {
                val temp = File(File(context.cacheDir, "pack-install").apply { mkdirs() }, "pack.zip")
                withContext(Dispatchers.IO) {
                    UriIo.copyTo(context, uri, temp)
                    PackZipInstaller.install(temp, context.filesDir).also { temp.delete() }
                }
            }
            result.onSuccess {
                if (it.ok) {
                    android.widget.Toast.makeText(
                        context,
                        context.getString(dev.ninfenz.mobile.R.string.packcenter_install_zip_done, it.id, it.version),
                        android.widget.Toast.LENGTH_SHORT
                    ).show()
                    onRefresh()
                } else {
                    android.widget.Toast.makeText(
                        context,
                        context.getString(dev.ninfenz.mobile.R.string.packcenter_install_zip_failed, it.message),
                        android.widget.Toast.LENGTH_LONG
                    ).show()
                }
            }.onFailure {
                android.widget.Toast.makeText(
                    context,
                    context.getString(dev.ninfenz.mobile.R.string.packcenter_install_zip_failed, it.message ?: it.javaClass.simpleName),
                    android.widget.Toast.LENGTH_LONG
                ).show()
            }
        }
    }

    fun verifyPackLocal(pack: PackEntry) {
                                        verifyingId = pack.id
                                        scope.launch {
                                            val response = PackVerifier().verify(pack)
                                            val verdict = response.resultObject()?.get("verdict")?.toString()?.trim('"')
                                            if (response.ok) {
                                                results = results + (pack.id to (context.getString(dev.ninfenz.mobile.R.string.packcenter_verify_pass, verdict ?: "pass")))
                                            } else {
                                                val err = response.error
                                                errors = errors + (pack.id to ("[" + (err?.code ?: "NF-VAL-001") + "] " + (err?.message ?: context.getString(dev.ninfenz.mobile.R.string.validate_failed)) + context.getString(dev.ninfenz.mobile.R.string.error_fix_suffix) + (err?.fix ?: context.getString(dev.ninfenz.mobile.R.string.view_diagnostics))))
                                            }
                                            verifyingId = null
                                        }
    }
    fun requestUninstallLocal(pack: PackEntry) {
                                        val inUse = projects.count {
                                            it.project.refs.basePackId == pack.id && it.project.refs.basePackVersion == pack.version
                                        }
                                        if (inUse > 0) {
                                            uninstallErrors = uninstallErrors + (pack.id to context.resources.getQuantityString(dev.ninfenz.mobile.R.plurals.packcenter_uninstall_in_use, inUse, inUse))
                                        } else {
                                            uninstallErrors = uninstallErrors - pack.id
                                            pendingUninstall = pack
                                        }
    }

    Column(modifier = Modifier.fillMaxSize()) {
        NfTopAppBar(
            title = stringResource(dev.ninfenz.mobile.R.string.packcenter_title),
            onBack = onBack,
            actions = {
                val compact = LocalDensity.current.fontScale >= 1.4f
                val installZip = { zipPicker.launch(arrayOf("application/zip", "application/octet-stream", "*/*")) }
                if (audit) TextButton(onClick = onNewPackDraft) { Text("New Pack") }
                if (compact) {
                    IconButton(onClick = installZip, modifier = Modifier.size(48.dp)) {
                        Icon(Icons.Filled.Add, contentDescription = stringResource(dev.ninfenz.mobile.R.string.packcenter_install_zip))
                    }
                    if (audit) IconButton(onClick = onUpdatePlan, modifier = Modifier.size(48.dp)) {
                        Icon(Icons.Filled.Refresh, contentDescription = stringResource(dev.ninfenz.mobile.R.string.packcenter_update_plan))
                    }
                } else {
                    TextButton(onClick = installZip) {
                        Text(stringResource(dev.ninfenz.mobile.R.string.packcenter_install_zip))
                    }
                    if (audit) TextButton(onClick = onUpdatePlan) { Text(stringResource(dev.ninfenz.mobile.R.string.packcenter_update_plan)) }
                }
            }
        )
        if (packs.isEmpty()) {
            NfEmptyState(
                icon = Icons.Filled.Add,
                title = stringResource(dev.ninfenz.mobile.R.string.packcenter_empty_title),
                message = stringResource(dev.ninfenz.mobile.R.string.packcenter_empty_body),
                actionLabel = stringResource(dev.ninfenz.mobile.R.string.packcenter_load_sample),
                onAction = onLoadSample,
                secondaryLabel = stringResource(dev.ninfenz.mobile.R.string.packcenter_install_zip),
                onSecondary = { zipPicker.launch(arrayOf("application/zip", "application/octet-stream", "*/*")) }
            )
        } else {
            PullToRefreshBox(isRefreshing = refreshing, onRefresh = onRefresh, modifier = Modifier.fillMaxSize()) {
            LazyColumn(
                contentPadding = androidx.compose.foundation.layout.PaddingValues(NfSpacing.page),
                verticalArrangement = Arrangement.spacedBy(NfSpacing.m)
            ) {
                item { NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.packcenter_installed_count, packs.size)) }
                item {
                    androidx.compose.material3.OutlinedTextField(
                        value = packQuery,
                        onValueChange = { packQuery = it },
                        label = { Text(stringResource(dev.ninfenz.mobile.R.string.pack_search)) },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth()
                    )
                }
                val filteredPacks = packs.filter { packQuery.isBlank() || it.title.contains(packQuery, true) || it.id.contains(packQuery, true) }
                items(filteredPacks.size) { index ->
                    val pack = filteredPacks[index]
                    PackCenterCard(
                        PackCenterCardModel(
                            pack = pack,
                            audit = audit,
                            pinned = trust[pack.id + "@" + pack.version]?.tree,
                            verifying = verifyingId == pack.id,
                            result = results[pack.id],
                            error = errors[pack.id],
                            uninstallError = uninstallErrors[pack.id]
                        ),
                        context = context,
                        onOpenPack = onOpenPack,
                        onVerify = { verifyPackLocal(it) },
                        onUninstall = { requestUninstallLocal(it) }
                    )
                }
            }
            }
        }
        pendingUninstall?.let { pack ->
            AlertDialog(
                onDismissRequest = { pendingUninstall = null },
                title = { Text(stringResource(dev.ninfenz.mobile.R.string.packcenter_uninstall_title)) },
                text = {
                    Text(
                        stringResource(
                            dev.ninfenz.mobile.R.string.packcenter_uninstall_body,
                            pack.id,
                            pack.version
                        )
                    )
                },
                confirmButton = {
                    TextButton(
                        modifier = androidx.compose.ui.Modifier.testTag("packcenter_uninstall_confirm"),
                        onClick = {
                            pendingUninstall = null
                            onUninstall(pack)
                        }
                    ) { Text(stringResource(dev.ninfenz.mobile.R.string.packcenter_uninstall_confirm)) }
                },
                dismissButton = {
                    TextButton(onClick = { pendingUninstall = null }) {
                        Text(stringResource(android.R.string.cancel))
                    }
                }
            )
        }
    }
}

internal data class PackCenterCardModel(
    val pack: PackEntry,
    val audit: Boolean,
    val pinned: String?,
    val verifying: Boolean,
    val result: String?,
    val error: String?,
    val uninstallError: String?,
)

@Composable
private fun PackCenterCard(
    model: PackCenterCardModel,
    context: android.content.Context,
    onOpenPack: (PackEntry) -> Unit,
    onVerify: (PackEntry) -> Unit,
    onUninstall: (PackEntry) -> Unit
) {
                    NfCard(modifier = Modifier.fillMaxWidth()) {
                        Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Column(modifier = Modifier.weight(1f)) {
                                    Text(model.pack.title, style = NfType.itemTitle)
                                    Text(
                                        model.pack.id + " · " + model.pack.version + " · " + context.getString(dev.ninfenz.mobile.R.string.pack_item_count, model.pack.itemCount),
                                        style = NfType.meta,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant
                                    )
                                }
                                NfStatusChip(stringResource(dev.ninfenz.mobile.R.string.packcenter_installed))
                            }
                            Text(stringResource(dev.ninfenz.mobile.R.string.packcenter_tree, model.pack.tree.take(16)), style = NfType.meta, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            Text(
                                stringResource(dev.ninfenz.mobile.R.string.packcenter_installed_at, formatInstalledAt(model.pack.installedAt)),
                                style = NfType.meta,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                            val pinned = model.pinned
                            if (model.audit && pinned != null && pinned != model.pack.tree) {
                                Text(
                                    stringResource(dev.ninfenz.mobile.R.string.packcenter_trust_mismatch),
                                    style = NfType.meta,
                                    color = MaterialTheme.colorScheme.error
                                )
                            }
                            Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                                if (model.audit) OutlinedButton(enabled = !model.verifying, onClick = { onVerify(model.pack) }) { Text(if (model.verifying) stringResource(dev.ninfenz.mobile.R.string.packcenter_verifying) else stringResource(dev.ninfenz.mobile.R.string.packcenter_verify)) }
                                Button(onClick = { onOpenPack(model.pack) }) { Text(stringResource(dev.ninfenz.mobile.R.string.packcenter_detail)) }
                                TextButton(onClick = { onUninstall(model.pack) }) { Text(stringResource(dev.ninfenz.mobile.R.string.packcenter_uninstall)) }
                            }
                            model.result?.let { Text(it, style = NfType.meta, color = MaterialTheme.colorScheme.primary) }
                            model.uninstallError?.let { message ->
                                Text(message, style = NfType.meta, color = MaterialTheme.colorScheme.error)
                            }
                            model.error?.let { message ->
                                NfErrorCard("NF-VAL-001", message, context.getString(dev.ninfenz.mobile.R.string.view_diag_or_reinstall))
                            }
                        }
                    }
}
