package dev.ninfenz.mobile.ui.screens

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
    refreshing: Boolean = false,
    onRefresh: () -> Unit = {}
) {
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    val trust = remember { PackTrustStore(context.filesDir).load() }
    var verifyingId by remember { mutableStateOf<String?>(null) }
    var results by remember { mutableStateOf<Map<String, String>>(emptyMap()) }
    var errors by remember { mutableStateOf<Map<String, String>>(emptyMap()) }
    var pendingUninstall by remember { mutableStateOf<PackEntry?>(null) }
    var uninstallErrors by remember { mutableStateOf<Map<String, String>>(emptyMap()) }

    val zipPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        if (uri == null) return@rememberLauncherForActivityResult
        scope.launch {
            val result = runCatching {
                val temp = File(File(context.cacheDir, "pack-install").apply { mkdirs() }, "pack.zip")
                withContext(Dispatchers.IO) {
                    context.contentResolver.openInputStream(uri)?.use { input ->
                        temp.outputStream().use { output -> input.copyTo(output) }
                    }
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

    Column(modifier = Modifier.fillMaxSize()) {
        NfTopAppBar(
            title = stringResource(dev.ninfenz.mobile.R.string.packcenter_title),
            onBack = onBack,
            actions = {
                TextButton(onClick = { zipPicker.launch(arrayOf("application/zip", "application/octet-stream", "*/*")) }) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.packcenter_install_zip))
                }
                TextButton(onClick = onUpdatePlan) { Text(stringResource(dev.ninfenz.mobile.R.string.packcenter_update_plan)) }
            }
        )
        if (packs.isEmpty()) {
            NfEmptyState(
                icon = Icons.Filled.Add,
                title = stringResource(dev.ninfenz.mobile.R.string.packcenter_empty_title),
                message = stringResource(dev.ninfenz.mobile.R.string.packcenter_empty_body),
                actionLabel = stringResource(dev.ninfenz.mobile.R.string.packcenter_load_sample),
                onAction = onLoadSample
            )
        } else {
            PullToRefreshBox(isRefreshing = refreshing, onRefresh = onRefresh, modifier = Modifier.fillMaxSize()) {
            LazyColumn(
                contentPadding = androidx.compose.foundation.layout.PaddingValues(NfSpacing.page),
                verticalArrangement = Arrangement.spacedBy(NfSpacing.m)
            ) {
                item { NfSectionHeader(stringResource(dev.ninfenz.mobile.R.string.packcenter_installed_count, packs.size)) }
                items(packs.size) { index ->
                    val pack = packs[index]
                    NfCard(modifier = Modifier.fillMaxWidth()) {
                        Column(verticalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Column(modifier = Modifier.weight(1f)) {
                                    Text(pack.title, style = MaterialTheme.typography.titleMedium)
                                    Text(
                                        pack.id + " · " + pack.version + " · " + context.getString(dev.ninfenz.mobile.R.string.pack_item_count, pack.itemCount),
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant
                                    )
                                }
                                NfStatusChip(stringResource(dev.ninfenz.mobile.R.string.packcenter_installed))
                            }
                            Text(stringResource(dev.ninfenz.mobile.R.string.packcenter_tree, pack.tree.take(16)), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            Text(
                                stringResource(dev.ninfenz.mobile.R.string.packcenter_installed_at, formatInstalledAt(pack.installedAt)),
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                            val pinned = trust[pack.id + "@" + pack.version]?.tree
                            if (pinned != null && pinned != pack.tree) {
                                Text(
                                    stringResource(dev.ninfenz.mobile.R.string.packcenter_trust_mismatch),
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.error
                                )
                            }
                            Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                                OutlinedButton(
                                    enabled = verifyingId == null,
                                    onClick = {
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
                                ) { Text(if (verifyingId == pack.id) stringResource(dev.ninfenz.mobile.R.string.packcenter_verifying) else stringResource(dev.ninfenz.mobile.R.string.packcenter_verify)) }
                                Button(onClick = { onOpenPack(pack) }) { Text(stringResource(dev.ninfenz.mobile.R.string.packcenter_detail)) }
                                TextButton(
                                    onClick = {
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
                                ) { Text(stringResource(dev.ninfenz.mobile.R.string.packcenter_uninstall)) }
                            }
                            results[pack.id]?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.primary) }
                            uninstallErrors[pack.id]?.let { message ->
                                Text(message, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
                            }
                            errors[pack.id]?.let { message ->
                                NfErrorCard("NF-VAL-001", message, context.getString(dev.ninfenz.mobile.R.string.view_diag_or_reinstall))
                            }
                        }
                    }
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
