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
import android.content.Context
import kotlinx.coroutines.CoroutineScope

internal class PackUpdateState(
    val context: Context,
    val scope: CoroutineScope,
    val store: LibraryStore,
) {
    var update by mutableStateOf<PackUpdate?>(null)
    var rawUpdate by mutableStateOf<JsonObject?>(null)
    var error by mutableStateOf<CoreError?>(null)
    var decisions by mutableStateOf<Map<String, String>>(emptyMap())
    var resultText by mutableStateOf<String?>(null)
    var busy by mutableStateOf(false)
    var packs by mutableStateOf<List<PackEntry>>(emptyList())
    var matrixProjects by mutableStateOf<List<dev.ninfenz.mobile.data.ProjectEntry>>(emptyList())
    var selected by mutableStateOf<PackEntry?>(null)
    var newRoot by mutableStateOf<File?>(null)
    var diffBusy by mutableStateOf(false)
    var preUpdateBackup by mutableStateOf<File?>(null)
    var installedUpdateTarget by mutableStateOf<File?>(null)
    var showRollbackBackup by mutableStateOf(false)
    var backupRollbackMessage by mutableStateOf<String?>(null)

    suspend fun load() {
        packs = withContext(Dispatchers.IO) { PackStore(context.filesDir).scan().packs }
        matrixProjects = withContext(Dispatchers.IO) { store.loadProjects().projects }
        selected = packs.firstOrNull()
    }

    fun runDiff(oldPack: PackEntry?, root: File?) {
        if (oldPack == null || root == null || diffBusy) return
        scope.launch {
            diffBusy = true
            error = null
            try {
                val payload = buildJsonObject {
                    put("old_root", oldPack.dir.absolutePath)
                    put("new_root", root.absolutePath)
                }
                val response = safeCall("pack-diff", payload)
                val obj = response.resultObject()
                if (response.ok && obj != null) {
                    val parsed = PackUpdateModel.parse(obj)
                    update = parsed
                    rawUpdate = obj
                    decisions = parsed.conflicts.associate { it.id to it.defaultOption }
                    resultText = null
                } else {
                    error = response.error
                }
            } catch (e: Exception) {
                error = CoreResponse.failure(
                    "NF-PCK-001",
                    context.getString(dev.ninfenz.mobile.R.string.pack_update_diff_failed, e.message ?: e.javaClass.simpleName),
                    context.getString(dev.ninfenz.mobile.R.string.pack_update_diff_failed_fix),
                    1
                ).error
            } finally {
                diffBusy = false
            }
        }
    }

    fun packDir(id: String, version: String): File {
        return File(File(File(context.filesDir, "library/packs"), id), version)
    }

    fun onPlanPicked(uri: Uri?) {
        if (uri == null) return
        scope.launch {
            try {
                val text = FileAccess.readText(context, uri)
                val obj = J.parseObject(text, "nf-pack-update/1")
                val parsed = PackUpdateModel.parse(obj)
                update = parsed
                rawUpdate = obj
                decisions = parsed.conflicts.associate { it.id to it.defaultOption }
                error = null
                resultText = null
            } catch (e: Exception) {
                error = CoreResponse.failure(
                    "NF-PCK-001",
                    context.getString(dev.ninfenz.mobile.R.string.pack_update_plan_failed, e.message ?: e.javaClass.simpleName),
                    context.getString(dev.ninfenz.mobile.R.string.pack_update_plan_failed_fix),
                    1
                ).error
            }
        }
    }

    fun onZipPicked(uri: Uri?) {
        if (uri == null) return
        scope.launch {
            error = null
            try {
                val meta = FileAccess.meta(context, uri)
                val zip = FileAccess.copyToCache(context, uri, meta.name)
                val dest = File(context.cacheDir, "new-pack")
                val root = withContext(Dispatchers.IO) { PackZipLoader.extract(zip, dest) }
                newRoot = root
                runDiff(selected, root)
            } catch (e: Exception) {
                error = CoreResponse.failure(
                    "NF-PCK-002",
                    context.getString(dev.ninfenz.mobile.R.string.pack_update_extract_failed, e.message ?: e.javaClass.simpleName),
                    context.getString(dev.ninfenz.mobile.R.string.pack_update_extract_failed_fix),
                    1
                ).error
            }
        }
    }

    fun applyUpdate(u: PackUpdate, base: File, target: File) {
                            val raw = rawUpdate ?: return
                            scope.launch {
                                busy = true
                                error = null
                                resultText = null
                                try {
                                    preUpdateBackup = withContext(Dispatchers.IO) {
                                        BackupService.create(context.filesDir).file
                                    }
                                    val outDir = File(context.filesDir, "library/applied").apply { mkdirs() }
                                    val payload = buildJsonObject {
                                        put("update", raw)
                                        put("base_root", base.absolutePath)
                                        put("new_root", target.absolutePath)
                                        put("decisions", buildJsonObject {
                                            for ((k, v) in decisions) put(k, v)
                                        })
                                        put("out_dir", outDir.absolutePath)
                                    }
                                    val response = safeCall("pack-merge", payload)
                                    if (response.ok) {
                                        val installed = withContext(Dispatchers.IO) {
                                            runCatching {
                                                val target = packDir(u.to.id, u.to.version)
                                                if (target.exists()) target.deleteRecursively()
                                                outDir.copyRecursively(target, overwrite = true)
                                                dev.ninfenz.mobile.data.PackStore(context.filesDir).invalidate()
                                                target
                                            }.orNullLogged("PackUpdateScreen")
                                        }
                                        resultText = response.result?.toString()
                                        if (installed == null || !installed.isDirectory) {
                                            error = CoreResponse.failure(
                                                "NF-PCK-005",
                                                context.getString(dev.ninfenz.mobile.R.string.packupdate_install_fail),
                                                context.getString(dev.ninfenz.mobile.R.string.packupdate_install_fix),
                                                3
                                            ).error
                                        } else {
                                            installedUpdateTarget = installed
                                        }
                                    } else {
                                        error = response.error
                                    }
                                } finally {
                                    busy = false
                                }
                            }
    }

    fun rollbackUpdate(target: File) {
        scope.launch {
                                    busy = true
                                    error = null
                                    val removed = withContext(Dispatchers.IO) {
                                        runCatching {
                                            target.deleteRecursively()
                                            dev.ninfenz.mobile.data.PackStore(context.filesDir).invalidate()
                                        }.isSuccess
                                    }
                                    if (removed) {
                                        installedUpdateTarget = null
                                        resultText = context.getString(dev.ninfenz.mobile.R.string.packupdate_rollback_done, target.name)
                                    } else {
                                        error = CoreResponse.failure(
                                            "NF-PCK-005",
                                            context.getString(dev.ninfenz.mobile.R.string.packupdate_rollback_fail),
                                            context.getString(dev.ninfenz.mobile.R.string.packupdate_install_fix),
                                            3
                                        ).error
                                    }
                                    busy = false
        }
    }

    fun restoreBackup(backup: File) {
        scope.launch {
                                busy = true
                                try {
                                    val restored = withContext(Dispatchers.IO) {
                                        BackupRestoreService.restore(backup, context.filesDir)
                                    }
                                    backupRollbackMessage = context.getString(
                                        dev.ninfenz.mobile.R.string.packupdate_restore_backup_done,
                                        restored.files
                                    )
                                } catch (t: Throwable) {
                                    backupRollbackMessage = context.getString(
                                        dev.ninfenz.mobile.R.string.packupdate_restore_backup_failed,
                                        t.message ?: t.javaClass.simpleName
                                    )
                                } finally {
                                    busy = false
                                }
        }
    }
}

