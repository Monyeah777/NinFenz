package dev.ninfenz.mobile.ui.screens

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.widget.Toast
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import dev.ninfenz.mobile.R
import dev.ninfenz.mobile.data.AuthorArtifactsLoader
import dev.ninfenz.mobile.data.DeliveryDraftStore
import dev.ninfenz.mobile.data.LibraryStore
import dev.ninfenz.mobile.data.PackStore
import dev.ninfenz.mobile.model.NfPatchModel
import dev.ninfenz.mobile.ui.components.NfTopAppBar
import dev.ninfenz.mobile.ui.safeCall
import dev.ninfenz.mobile.ui.theme.NfSpacing
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import java.io.File
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

@Composable
fun PatchScreen(filesDir: File, projectId: String?, onBack: () -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val store = remember(projectId) { projectId?.let { DeliveryDraftStore(filesDir) } }
    var markdown by remember(projectId) { mutableStateOf(projectId?.let { store?.loadMarkdown(it) } ?: "") }
    var json by remember { mutableStateOf("") }
    var entries by remember { mutableStateOf<List<Pair<NfPatchModel.Op, Boolean>>>(emptyList()) }
    var result by remember { mutableStateOf<NfPatchModel.Result?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var beforeApply by remember { mutableStateOf<String?>(null) }
    var validation by remember { mutableStateOf<String?>(null) }

    Column(Modifier.fillMaxSize()) {
        NfTopAppBar(title = stringResource(R.string.patch_title), onBack = onBack)
        Column(
            Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(NfSpacing.page),
            verticalArrangement = Arrangement.spacedBy(NfSpacing.s)
        ) {
            Text(stringResource(R.string.patch_md_hint), style = MaterialTheme.typography.bodySmall)
            OutlinedTextField(
                value = markdown,
                onValueChange = { markdown = it },
                modifier = Modifier.fillMaxWidth(),
                minLines = 5,
                textStyle = MaterialTheme.typography.bodySmall
            )
            Text(stringResource(R.string.patch_json_hint), style = MaterialTheme.typography.bodySmall)
            OutlinedTextField(
                value = json,
                onValueChange = { json = it },
                modifier = Modifier.fillMaxWidth(),
                minLines = 5,
                textStyle = MaterialTheme.typography.bodySmall
            )
            error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                Button(onClick = {
                    error = null
                    result = null
                    try {
                        val patch = NfPatchModel.parse(json)
                        entries = patch.ops.map { it to true }
                    } catch (t: Throwable) {
                        entries = emptyList()
                        error = t.message ?: t.javaClass.simpleName
                    }
                }) { Text(stringResource(R.string.patch_parse)) }
                OutlinedButton(
                    enabled = entries.isNotEmpty(),
                    onClick = {
                        error = null
                        val selected = entries.filter { it.second }.map { it.first }
                        if (selected.isEmpty()) {
                            error = context.getString(R.string.patch_none_selected)
                        } else {
                            beforeApply = markdown
                            val applied = NfPatchModel.apply(markdown, NfPatchModel.Patch(selected))
                            result = applied
                            validation = null
                            if (projectId != null) {
                                scope.launch {
                                    validation = withContext(Dispatchers.IO) {
                                        runCatching {
                                            val entry = LibraryStore(filesDir).loadProjects().projects.firstOrNull { it.project.id == projectId }
                                                ?: return@runCatching context.getString(R.string.patch_validation_failed)
                                            val pack = PackStore(filesDir).scan().packs.firstOrNull {
                                                it.id == entry.project.refs.basePackId && it.version == entry.project.refs.basePackVersion
                                            } ?: return@runCatching context.getString(R.string.patch_validation_failed)
                                            val art = AuthorArtifactsLoader.load(pack)
                                            val compiled = safeCall("graph-compile", buildJsonObject {
                                                put("graph", art.graphJson)
                                                put("spec", art.specJson)
                                            })
                                            val plan = compiled.resultObject() ?: return@runCatching context.getString(R.string.patch_validation_failed)
                                            val checked = safeCall("validate", buildJsonObject {
                                                put("markdown", applied.markdown)
                                                put("spec", art.specJson)
                                                put("plan", plan)
                                                put("level", "L1")
                                            })
                                            if (checked.ok) context.getString(R.string.patch_validation_ok)
                                            else context.getString(R.string.patch_validation_failed)
                                        }.getOrElse { context.getString(R.string.patch_validation_failed) }
                                    }
                                }
                            }
                        }
                    }
                ) { Text(stringResource(R.string.patch_apply)) }
            }
            entries.forEachIndexed { index, (op, accepted) ->
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Checkbox(checked = accepted, onCheckedChange = { on ->
                        entries = entries.toMutableList().also { it[index] = op to on }
                    })
                    Text(
                        op.kind + " · " + (op.blockId ?: op.slot ?: "") + " · " + (op.text ?: ""),
                        style = MaterialTheme.typography.bodySmall,
                        modifier = Modifier.weight(1f)
                    )
                }
            }
            result?.let { r ->
                Text(stringResource(R.string.patch_result, r.applied, r.rejected.size), style = MaterialTheme.typography.titleSmall)
                Text(stringResource(R.string.patch_changes, r.changes.size), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.primary)
                validation?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.secondary) }
                r.changes.forEach { c ->
                    Text(
                        c.op + " · " + (c.before?.take(60) ?: "∅") + " → " + (c.after?.take(60) ?: "∅"),
                        style = MaterialTheme.typography.bodySmall
                    )
                }
                r.rejected.forEach { Text("· " + it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }
                OutlinedTextField(
                    value = r.markdown,
                    onValueChange = {},
                    readOnly = true,
                    modifier = Modifier.fillMaxWidth(),
                    minLines = 5,
                    textStyle = MaterialTheme.typography.bodySmall
                )
                Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                    if (beforeApply != null) {
                        OutlinedButton(onClick = {
                            markdown = beforeApply!!
                            beforeApply = null
                            result = null
                        }) { Text(stringResource(R.string.patch_undo)) }
                    }
                    OutlinedButton(onClick = {
                        val manager = context.getSystemService(Context.CLIPBOARD_SERVICE) as? ClipboardManager
                        manager?.setPrimaryClip(ClipData.newPlainText("nf-patch", r.markdown))
                        Toast.makeText(context, context.getString(R.string.patch_copied), Toast.LENGTH_SHORT).show()
                    }) { Text(stringResource(R.string.patch_copy)) }
                    if (store != null && projectId != null) {
                        Button(onClick = {
                            store.save(projectId, store.load(projectId), store.loadPlan(projectId), r.markdown)
                            Toast.makeText(context, context.getString(R.string.patch_saved), Toast.LENGTH_SHORT).show()
                            beforeApply = null
                        }) { Text(stringResource(R.string.patch_save)) }
                    }
                }
            }
        }
    }
}
