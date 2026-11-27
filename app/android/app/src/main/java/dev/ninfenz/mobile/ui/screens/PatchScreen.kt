package dev.ninfenz.mobile.ui.screens

import dev.ninfenz.mobile.util.orNullLogged
import dev.ninfenz.mobile.ui.design.NfType

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
    var history by remember { mutableStateOf<List<String>>(emptyList()) }
    var validation by remember { mutableStateOf<String?>(null) }
    var validationIssues by remember { mutableStateOf<List<dev.ninfenz.mobile.model.ReportIssue>>(emptyList()) }

    Column(Modifier.fillMaxSize()) {
        NfTopAppBar(title = stringResource(R.string.patch_title), onBack = onBack)
        Column(
            Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(NfSpacing.page),
            verticalArrangement = Arrangement.spacedBy(NfSpacing.s)
        ) {
            Text(stringResource(R.string.patch_md_hint), style = NfType.meta)
            OutlinedTextField(
                value = markdown,
                onValueChange = { markdown = it },
                modifier = Modifier.fillMaxWidth(),
                minLines = 5,
                textStyle = NfType.meta
            )
            Text(stringResource(R.string.patch_json_hint), style = NfType.meta)
            OutlinedTextField(
                value = json,
                onValueChange = { json = it },
                modifier = Modifier.fillMaxWidth(),
                minLines = 5,
                textStyle = NfType.meta
            )
            error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            PatchActionButtons(json, markdown, entries, history, projectId, filesDir,
                onEntriesChange = { entries = it }, onError = { error = it }, onMarkdownChange = { markdown = it },
                onHistoryChange = { history = it }, onResult = { result = it }, onValidation = { validation = it },
                onValidationIssues = { validationIssues = it })
            PatchEntryRows(entries = entries, onEntriesChange = { entries = it })
            PatchResultSection(
                result = result,
                validation = validation,
                validationIssues = validationIssues,
                history = history,
                store = store,
                projectId = projectId,
                filesDir = filesDir,
                onMarkdownChange = { markdown = it },
                onHistoryChange = { history = it },
                onResult = { result = it },
                onError = { error = it }
            )
        }
    }
}

@Composable
private fun PatchEntryRows(
    entries: List<Pair<NfPatchModel.Op, Boolean>>,
    onEntriesChange: (List<Pair<NfPatchModel.Op, Boolean>>) -> Unit
) {
    entries.forEachIndexed { index, (op, accepted) ->
        Row(verticalAlignment = Alignment.CenterVertically) {
            Checkbox(checked = accepted, onCheckedChange = { on ->
                onEntriesChange(entries.toMutableList().also { it[index] = op to on })
            })
            Text(
                op.kind + " · " + (op.blockId ?: op.slot ?: "") + " · " + (op.text ?: ""),
                style = NfType.meta,
                modifier = Modifier.weight(1f)
            )
        }
    }
}

@Composable
private fun PatchResultSection(
    result: NfPatchModel.Result?,
    validation: String?,
    validationIssues: List<dev.ninfenz.mobile.model.ReportIssue>,
    history: List<String>,
    store: DeliveryDraftStore?,
    projectId: String?,
    filesDir: File,
    onMarkdownChange: (String) -> Unit,
    onHistoryChange: (List<String>) -> Unit,
    onResult: (NfPatchModel.Result?) -> Unit,
    onError: (String?) -> Unit
) {
    result?.let { r ->
        PatchResultDetails(
            r = r,
            validation = validation,
            validationIssues = validationIssues
        )
        PatchResultActions(
            r = r,
            history = history,
            store = store,
            projectId = projectId,
            filesDir = filesDir,
            onMarkdownChange = onMarkdownChange,
            onHistoryChange = onHistoryChange,
            onResult = onResult,
            onError = onError
        )
    }
}

@Composable
private fun PatchActionButtons(
    json: String,
    markdown: String,
    entries: List<Pair<NfPatchModel.Op, Boolean>>,
    history: List<String>,
    projectId: String?,
    filesDir: File,
    onEntriesChange: (List<Pair<NfPatchModel.Op, Boolean>>) -> Unit,
    onError: (String?) -> Unit,
    onMarkdownChange: (String) -> Unit,
    onHistoryChange: (List<String>) -> Unit,
    onResult: (NfPatchModel.Result?) -> Unit,
    onValidation: (String?) -> Unit,
    onValidationIssues: (List<dev.ninfenz.mobile.model.ReportIssue>) -> Unit
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
        Button(onClick = {
            onError(null)
            onResult(null)
            try {
                val patch = NfPatchModel.parse(json)
                onEntriesChange(patch.ops.map { it to true })
            } catch (t: Throwable) {
                onEntriesChange(emptyList())
                onError(t.message ?: t.javaClass.simpleName)
            }
        }) { Text(stringResource(R.string.patch_parse)) }
        OutlinedButton(
            enabled = entries.isNotEmpty(),
            onClick = {
                onError(null)
                val selected = entries.filter { it.second }.map { it.first }
                if (selected.isEmpty()) {
                    onError(context.getString(R.string.patch_none_selected))
                } else {
                    onHistoryChange(history + markdown)
                    val applied = NfPatchModel.apply(markdown, NfPatchModel.Patch(selected))
                    onResult(applied)
                    onValidation(null)
                    onValidationIssues(emptyList())
                    val issues = mutableListOf<dev.ninfenz.mobile.model.ReportIssue>()
                    if (projectId != null) {
                        scope.launch {
                            onValidation(validatePatch(context, projectId, filesDir, applied, issues))
                            onValidationIssues(issues)
                        }
                    }
                }
            }
        ) { Text(stringResource(R.string.patch_apply)) }
    }
}

private suspend fun validatePatch(
    context: android.content.Context,
    projectId: String,
    filesDir: File,
    applied: NfPatchModel.Result,
    issues: MutableList<dev.ninfenz.mobile.model.ReportIssue>
): String = withContext(Dispatchers.IO) {
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
        if (checked.ok) {
            context.getString(R.string.patch_validation_ok)
        } else {
            checked.resultObject()?.let { obj ->
                runCatching { dev.ninfenz.mobile.model.ReportModel.parse(obj) }.orNullLogged("PatchScreen")
                    ?.issues?.take(3)?.let { issues.addAll(it) }
            }
            context.getString(R.string.patch_validation_failed)
        }
    }.getOrElse { context.getString(R.string.patch_validation_failed) }
}

@Composable
private fun PatchResultDetails(
    r: NfPatchModel.Result,
    validation: String?,
    validationIssues: List<dev.ninfenz.mobile.model.ReportIssue>
) {
    Text(stringResource(R.string.patch_result, r.applied, r.rejected.size), style = NfType.itemTitle)
    Text(stringResource(R.string.patch_changes, r.changes.size), style = NfType.meta, color = MaterialTheme.colorScheme.primary)
    validation?.let { Text(it, style = NfType.meta, color = MaterialTheme.colorScheme.secondary) }
    validationIssues.forEach { issue ->
        Text(issue.code + " " + (issue.path ?: "-") + "：" + issue.message, style = NfType.meta, color = MaterialTheme.colorScheme.error)
    }
    r.changes.forEach { c ->
        Text(
            c.op + " · " + (c.before?.take(60) ?: "∅") + " → " + (c.after?.take(60) ?: "∅"),
            style = NfType.meta
        )
    }
    r.rejected.forEach { Text("· " + it, color = MaterialTheme.colorScheme.error, style = NfType.meta) }
    OutlinedTextField(
        value = r.markdown,
        onValueChange = {},
        readOnly = true,
        modifier = Modifier.fillMaxWidth(),
        minLines = 5,
        textStyle = NfType.meta
    )
}

@Composable
private fun PatchResultActions(
    r: NfPatchModel.Result,
    history: List<String>,
    store: DeliveryDraftStore?,
    projectId: String?,
    filesDir: File,
    onMarkdownChange: (String) -> Unit,
    onHistoryChange: (List<String>) -> Unit,
    onResult: (NfPatchModel.Result?) -> Unit,
    onError: (String?) -> Unit
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
        if (history.isNotEmpty()) {
            OutlinedButton(onClick = {
                onMarkdownChange(history.last())
                onHistoryChange(history.dropLast(1))
                onResult(null)
            }) { Text(stringResource(R.string.patch_undo)) }
        }
        OutlinedButton(onClick = {
            val manager = context.getSystemService(Context.CLIPBOARD_SERVICE) as? ClipboardManager
            manager?.setPrimaryClip(ClipData.newPlainText("nf-patch", r.markdown))
            Toast.makeText(context, context.getString(R.string.patch_copied), Toast.LENGTH_SHORT).show()
        }) { Text(stringResource(R.string.patch_copy)) }
        if (store != null && projectId != null) {
            Button(onClick = {
                val rawPlan = store.loadPlan(projectId)
                val allowed = rawPlan?.let { runCatching { dev.ninfenz.mobile.model.PlanModel.parse(it).slots.toSet() }.orNullLogged("PatchScreen") } ?: emptySet()
                val unknown = r.slots.keys.filter { it !in allowed }
                if (unknown.isNotEmpty()) {
                    onError(context.getString(R.string.patch_unknown_slot, unknown.joinToString()))
                } else {
                    store.save(projectId, store.load(projectId) + r.slots, rawPlan, r.markdown)
                    Toast.makeText(context, context.getString(R.string.patch_saved), Toast.LENGTH_SHORT).show()
                    onHistoryChange(emptyList())
                }
            }) { Text(stringResource(R.string.patch_save)) }
            if (r.slots.isNotEmpty()) {
                OutlinedButton(onClick = {
                    scope.launch {
                        val outcome = assembleAndSavePatch(filesDir, store, projectId, r)
                        if (outcome == true) {
                            Toast.makeText(context, context.getString(R.string.patch_saved), Toast.LENGTH_SHORT).show()
                            onHistoryChange(emptyList())
                        } else {
                            onError(context.getString(R.string.patch_assemble_failed, context.getString(R.string.patch_assemble_hint)))
                        }
                    }
                }) { Text(stringResource(R.string.patch_save_assemble)) }
            }
        }
    }
}

private suspend fun assembleAndSavePatch(
    filesDir: File,
    store: DeliveryDraftStore,
    projectId: String,
    r: NfPatchModel.Result
): Boolean? = withContext(Dispatchers.IO) {
    runCatching {
        val entry = LibraryStore(filesDir).loadProjects().projects.firstOrNull { it.project.id == projectId }
            ?: return@runCatching null
        val pack = PackStore(filesDir).scan().packs.firstOrNull {
            it.id == entry.project.refs.basePackId && it.version == entry.project.refs.basePackVersion
        } ?: return@runCatching null
        val art = AuthorArtifactsLoader.load(pack)
        val rawPlan = store.loadPlan(projectId) ?: return@runCatching null
        val merged = store.load(projectId) + r.slots
        val response = safeCall("assemble", buildJsonObject {
            put("plan", rawPlan)
            put("spec", art.specJson)
            put("inputs", buildJsonObject { merged.forEach { (k, v) -> put(k, v) } })
        })
        if (!response.ok) return@runCatching false
        val md = (response.resultObject()?.get("markdown") as? kotlinx.serialization.json.JsonPrimitive)?.content
            ?: return@runCatching false
        store.save(projectId, merged, rawPlan, md)
        true
    }.orNullLogged("PatchScreen")
}
