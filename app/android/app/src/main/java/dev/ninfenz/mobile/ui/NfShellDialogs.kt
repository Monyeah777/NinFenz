package dev.ninfenz.mobile.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import dev.ninfenz.mobile.data.FeatureGate
import dev.ninfenz.mobile.model.CommandPalette
import dev.ninfenz.mobile.ui.shell.Detail
import dev.ninfenz.mobile.ui.theme.NfSpacing

/** 外壳级对话框：关于、缺 Pack 提示、命令面板。 */
@Composable
internal fun NfShellDialogs(host: NfShellHost) {
    if (host.showAbout) NfAboutDialog(host)
    host.missingPackWarning?.let { (id, version) -> NfMissingPackDialog(host, id, version) }
    if (host.showCommands) NfCommandPaletteDialog(host)
}

@Composable
private fun NfAboutDialog(host: NfShellHost) {
    AlertDialog(
        onDismissRequest = { host.showAbout = false },
        title = { Text(stringResource(dev.ninfenz.mobile.R.string.about_title)) },
        text = {
            Text(
                stringResource(
                    dev.ninfenz.mobile.R.string.about_body,
                    dev.ninfenz.mobile.BuildConfig.VERSION_NAME,
                    dev.ninfenz.mobile.BuildConfig.VERSION_CODE
                )
            )
        },
        confirmButton = {
            TextButton(onClick = { host.showAbout = false }) {
                Text(stringResource(dev.ninfenz.mobile.R.string.action_close))
            }
        }
    )
}

@Composable
private fun NfMissingPackDialog(host: NfShellHost, id: String, version: String) {
    AlertDialog(
        onDismissRequest = { host.missingPackWarning = null },
        title = { Text(stringResource(dev.ninfenz.mobile.R.string.project_import_missing_pack_title)) },
        text = { Text(stringResource(dev.ninfenz.mobile.R.string.project_import_missing_pack_body, id, version)) },
        confirmButton = {
            TextButton(onClick = {
                host.missingPackWarning = null
                host.open(Detail.PackCenter)
            }) {
                Text(stringResource(dev.ninfenz.mobile.R.string.project_import_missing_pack_action))
            }
        },
        dismissButton = {
            TextButton(onClick = { host.missingPackWarning = null }) {
                Text(stringResource(dev.ninfenz.mobile.R.string.action_close))
            }
        }
    )
}

@Composable
private fun NfCommandPaletteDialog(host: NfShellHost) {
    val items = buildList {
        add(CommandPalette.Item("import", stringResource(dev.ninfenz.mobile.R.string.action_import)))
        add(CommandPalette.Item("inbox", stringResource(dev.ninfenz.mobile.R.string.inbox_title)))
        add(CommandPalette.Item("new_project", stringResource(dev.ninfenz.mobile.R.string.new_project_title)))
        add(CommandPalette.Item("search", stringResource(dev.ninfenz.mobile.R.string.search_title)))
        add(CommandPalette.Item("pack_center", stringResource(dev.ninfenz.mobile.R.string.deliver_pack_center_title)))
        if (FeatureGate.auditEnabled()) {
            add(CommandPalette.Item("pack_update", stringResource(dev.ninfenz.mobile.R.string.pack_detail_update)))
            add(CommandPalette.Item("ccos", stringResource(dev.ninfenz.mobile.R.string.ccos_title)))
        }
        add(CommandPalette.Item("settings", stringResource(dev.ninfenz.mobile.R.string.settings_title)))
        add(CommandPalette.Item("error_codes", stringResource(dev.ninfenz.mobile.R.string.error_codes_title)))
        add(CommandPalette.Item("project_import", stringResource(dev.ninfenz.mobile.R.string.project_import_command)))
    }
    CommandPaletteDialog(
        CommandPalette.order(items, host.recentCommands),
        onDismiss = { host.showCommands = false },
        onRun = host::runCommand
    )
}

@Composable
private fun CommandPaletteDialog(
    items: List<CommandPalette.Item>,
    onDismiss: () -> Unit,
    onRun: (String) -> Unit
) {
    var query by rememberSaveable { mutableStateOf("") }
    val filtered = CommandPalette.filter(items, query)
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stringResource(dev.ninfenz.mobile.R.string.commands_title)) },
        text = {
            Column {
                OutlinedTextField(
                    value = query,
                    onValueChange = { query = it },
                    modifier = Modifier.fillMaxWidth(),
                    placeholder = { Text(stringResource(dev.ninfenz.mobile.R.string.commands_placeholder)) },
                    singleLine = true
                )
                if (filtered.isEmpty()) {
                    Text(
                        stringResource(dev.ninfenz.mobile.R.string.commands_no_result),
                        modifier = Modifier.padding(NfSpacing.m)
                    )
                } else {
                    LazyColumn(modifier = Modifier.heightIn(max = 360.dp)) {
                        items(filtered, key = { it.id }) { item ->
                            Text(
                                item.title,
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clickable { onRun(item.id) }
                                    .padding(horizontal = NfSpacing.m, vertical = 12.dp)
                            )
                        }
                    }
                }
            }
        },
        confirmButton = {
            TextButton(onClick = onDismiss) { Text(stringResource(dev.ninfenz.mobile.R.string.action_close)) }
        }
    )
}
