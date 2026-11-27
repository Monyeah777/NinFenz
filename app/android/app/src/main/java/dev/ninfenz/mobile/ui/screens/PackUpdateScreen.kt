package dev.ninfenz.mobile.ui.screens

import dev.ninfenz.mobile.util.orNullLogged
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import dev.ninfenz.mobile.core.CoreError
import dev.ninfenz.mobile.core.CoreResponse
import dev.ninfenz.mobile.core.J
import dev.ninfenz.mobile.data.Capability
import dev.ninfenz.mobile.data.CapabilityRegistry
import dev.ninfenz.mobile.data.FileAccess
import dev.ninfenz.mobile.data.LibraryStore
import dev.ninfenz.mobile.data.BackupRestoreService
import dev.ninfenz.mobile.data.BackupService
import dev.ninfenz.mobile.data.PackEntry
import dev.ninfenz.mobile.data.PackStore
import dev.ninfenz.mobile.data.PackZipLoader
import dev.ninfenz.mobile.model.ConflictBoard
import dev.ninfenz.mobile.model.PackUpdate
import dev.ninfenz.mobile.model.PackUpdateModel
import dev.ninfenz.mobile.ui.safeCall
import dev.ninfenz.mobile.ui.components.CardBox
import dev.ninfenz.mobile.ui.components.EmptyState
import dev.ninfenz.mobile.ui.components.ErrorNotice
import dev.ninfenz.mobile.ui.components.KeyValue
import dev.ninfenz.mobile.ui.components.MonoText
import dev.ninfenz.mobile.ui.components.NfScaffold
import dev.ninfenz.mobile.ui.components.Notice
import dev.ninfenz.mobile.ui.rememberCapabilityRevision
import dev.ninfenz.mobile.ui.components.Tone
import dev.ninfenz.mobile.ui.design.NfType
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import java.io.File

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun PackUpdateScreen(store: LibraryStore, onBack: () -> Unit, onOpenProject: (String) -> Unit = {}) {
    val context = LocalContext.current
    val capabilityRevision = rememberCapabilityRevision()
    val scope = rememberCoroutineScope()
    val s = remember { PackUpdateState(context, scope, store) }
    LaunchedEffect(Unit) { s.load() }
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        s.onPlanPicked(uri)
    }
    val zipPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        s.onZipPicked(uri)
    }
    NfScaffold(title = stringResource(dev.ninfenz.mobile.R.string.packupdate_title), onBack = onBack) {
        if (capabilityRevision >= 0 && CapabilityRegistry.isEnabled(Capability.MATRIX)) {
            PackUpdateMatrixCard(s, onOpenProject)
        }
        PackUpdatePlanCard(s, onOpenProject,
            onPickZip = { zipPicker.launch(arrayOf("application/zip", "application/octet-stream", "*/*")) },
            onPickPlan = { picker.launch(arrayOf("application/json", "text/plain")) })
        s.error?.let { ErrorNotice(it) }
        val u = s.update
        if (u != null) {
            PackUpdateChangesCard(s, u)
            PackUpdateConflictsCard(s, u)
            PackUpdateApplyCard(s, u)
        }
    }

    if (s.showRollbackBackup) {
        val backup = s.preUpdateBackup
        AlertDialog(
            onDismissRequest = { s.showRollbackBackup = false },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.packupdate_restore_backup)) },
            text = { Text(stringResource(dev.ninfenz.mobile.R.string.packupdate_restore_backup_body)) },
            confirmButton = {
                TextButton(
                    enabled = backup != null && !s.busy,
                    onClick = { s.showRollbackBackup = false; backup?.let { s.restoreBackup(it) } }
                ) { Text(stringResource(dev.ninfenz.mobile.R.string.packupdate_restore_backup_confirm)) }
            },
            dismissButton = {
                TextButton(onClick = { s.showRollbackBackup = false }) {
                    Text(stringResource(android.R.string.cancel))
                }
            }
        )
    }
}
