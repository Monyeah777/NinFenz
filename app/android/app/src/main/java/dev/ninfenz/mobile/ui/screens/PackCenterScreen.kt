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
import androidx.compose.ui.res.stringResource
import kotlinx.coroutines.launch
import dev.ninfenz.mobile.data.PackEntry
import dev.ninfenz.mobile.data.PackTrustStore
import dev.ninfenz.mobile.data.PackVerifier
import dev.ninfenz.mobile.ui.components.NfCard
import dev.ninfenz.mobile.ui.components.NfEmptyState
import dev.ninfenz.mobile.ui.components.NfErrorCard
import dev.ninfenz.mobile.ui.components.NfSectionHeader
import dev.ninfenz.mobile.ui.components.NfStatusChip
import dev.ninfenz.mobile.ui.components.NfTopAppBar
import dev.ninfenz.mobile.ui.theme.NfSpacing

/** W5 Pack 中心：已装列表 + 逐 Pack 校验 + 详情/更新入口（diff/冲突/回滚仍在 PackUpdate）。 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PackCenterScreen(
    packs: List<PackEntry>,
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

    Column(modifier = Modifier.fillMaxSize()) {
        NfTopAppBar(
            title = stringResource(dev.ninfenz.mobile.R.string.packcenter_title),
            onBack = onBack,
            actions = {
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
                            }
                            results[pack.id]?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.primary) }
                            errors[pack.id]?.let { message ->
                                NfErrorCard("NF-VAL-001", message, context.getString(dev.ninfenz.mobile.R.string.view_diag_or_reinstall))
                            }
                        }
                    }
                }
            }
            }
        }
    }
}
