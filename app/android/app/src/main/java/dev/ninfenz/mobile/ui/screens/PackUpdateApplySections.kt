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

@Composable
internal fun PackUpdateApplyCard(s: PackUpdateState, u: PackUpdate) {
    CardBox(title = stringResource(dev.ninfenz.mobile.R.string.packupdate_apply_rollback)) {
        val base = s.selected?.dir ?: s.packDir(u.from.id, u.from.version)
        val target = s.newRoot ?: s.packDir(u.to.id, u.to.version)
        KeyValue(stringResource(dev.ninfenz.mobile.R.string.packupdate_base_dir), if (base.exists()) stringResource(dev.ninfenz.mobile.R.string.packupdate_present) else stringResource(dev.ninfenz.mobile.R.string.packupdate_missing, base.absolutePath))
        KeyValue(stringResource(dev.ninfenz.mobile.R.string.packupdate_new_dir), if (target.exists()) stringResource(dev.ninfenz.mobile.R.string.packupdate_present) else stringResource(dev.ninfenz.mobile.R.string.packupdate_missing, target.absolutePath))
        PackUpdateApplyActions(s, u, base, target)
        PackUpdateApplyHints(s)
    }
}

@Composable
internal fun PackUpdateApplyActions(s: PackUpdateState, u: PackUpdate, base: File, target: File) {
                Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(
                        enabled = !s.busy && base.exists() && target.exists() && u.conflicts.all { (s.decisions[it.id] ?: it.defaultOption) != "defer" },
                        onClick = { s.applyUpdate(u, base, target) }
                    ) { Text(if (s.busy) stringResource(dev.ninfenz.mobile.R.string.packupdate_applying) else stringResource(dev.ninfenz.mobile.R.string.packupdate_apply)) }

                    OutlinedButton(
                        enabled = !s.busy && (s.installedUpdateTarget != null || s.preUpdateBackup != null),
                        onClick = {
                            val target = s.installedUpdateTarget
                            if (target != null) s.rollbackUpdate(target) else s.showRollbackBackup = true
                        }
                    ) { Text(if (s.busy) stringResource(dev.ninfenz.mobile.R.string.packupdate_rolling) else stringResource(dev.ninfenz.mobile.R.string.packupdate_rollback)) }
                    if (s.preUpdateBackup == null) {
                        Text(
                            stringResource(dev.ninfenz.mobile.R.string.packupdate_rollback_no_backup),
                            style = NfType.meta,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }
}

@Composable
internal fun PackUpdateApplyHints(s: PackUpdateState) {
                s.resultText?.let { MonoText(it) }
                s.preUpdateBackup?.let {
                    Text(
                        stringResource(dev.ninfenz.mobile.R.string.packupdate_pre_backup, it.absolutePath),
                        style = NfType.meta
                    )
                    TextButton(enabled = !s.busy, onClick = { s.showRollbackBackup = true }) {
                        Text(stringResource(dev.ninfenz.mobile.R.string.packupdate_restore_backup))
                    }
                }
                s.backupRollbackMessage?.let { Text(it, style = NfType.meta) }
                Notice(stringResource(dev.ninfenz.mobile.R.string.packupdate_notice), Tone.INFO)
}

