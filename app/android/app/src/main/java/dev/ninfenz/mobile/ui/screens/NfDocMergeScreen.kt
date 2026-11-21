package dev.ninfenz.mobile.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
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
import dev.ninfenz.mobile.R
import dev.ninfenz.mobile.core.J
import dev.ninfenz.mobile.model.NfDoc
import dev.ninfenz.mobile.model.NfDocMerger
import dev.ninfenz.mobile.model.NfDocModel
import dev.ninfenz.mobile.share.ShareExporter
import dev.ninfenz.mobile.ui.components.NfTopAppBar
import dev.ninfenz.mobile.ui.theme.NfSpacing
import java.io.File
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

@Composable
fun NfDocMergeScreen(filesDir: File, onBack: () -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val outDir = remember(filesDir) { File(File(filesDir, "exports"), "delivery").apply { mkdirs() } }
    var files by remember { mutableStateOf(outDir.listFiles { f -> f.isFile && f.name.endsWith(".nfdoc.json") }?.sortedBy { it.name }.orEmpty()) }
    var selected by remember { mutableStateOf<Set<File>>(emptySet()) }
    var result by remember { mutableStateOf<NfDocMerger.Result?>(null) }
    var saved by remember { mutableStateOf<File?>(null) }
    var error by remember { mutableStateOf<String?>(null) }

    Column(Modifier.fillMaxSize()) {
        NfTopAppBar(title = stringResource(R.string.nfdoc_merge_title), onBack = onBack)
        if (files.size < 2) {
            Text(
                stringResource(R.string.nfdoc_merge_empty, files.size),
                modifier = Modifier.padding(NfSpacing.page),
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            return@Column
        }
        Text(
            stringResource(R.string.nfdoc_merge_hint),
            modifier = Modifier.padding(horizontal = NfSpacing.page),
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        LazyColumn(Modifier.weight(1f).fillMaxWidth()) {
            items(files, key = { it.absolutePath }) { file ->
                Row(
                    Modifier.fillMaxWidth().padding(horizontal = NfSpacing.page, vertical = NfSpacing.xs),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Checkbox(
                        checked = file in selected,
                        onCheckedChange = { on ->
                            selected = if (on) selected + file else selected - file
                        }
                    )
                    Text(file.name, modifier = Modifier.padding(start = NfSpacing.s))
                }
            }
        }
        error?.let {
            Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(horizontal = NfSpacing.page))
        }
        result?.let { merged ->
            Column(Modifier.padding(horizontal = NfSpacing.page, vertical = NfSpacing.s), verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                Text(stringResource(R.string.nfdoc_merge_result, merged.doc.blocks.size, merged.doc.sources.size))
                Text(stringResource(R.string.nfdoc_merge_conflicts, merged.conflicts.size), color = MaterialTheme.colorScheme.primary)
                merged.conflicts.take(5).forEach { c ->
                    Text("· " + c.title + " · " + c.reason, style = MaterialTheme.typography.bodySmall)
                }
                saved?.let { file ->
                    OutlinedButton(onClick = {
                        val intent = ShareExporter.shareFileIntent(context, file, "application/json", file.name)
                        ShareExporter.launchChooser(context, intent, file.name)
                    }) { Text(stringResource(R.string.nfdoc_merge_share)) }
                }
            }
        }
        Button(
            enabled = selected.size >= 2,
            modifier = Modifier.padding(NfSpacing.page),
            onClick = {
                error = null
                scope.launch {
                    try {
                        val merged = withContext(Dispatchers.IO) {
                            val docs = selected.map { file ->
                                NfDocModel.parse(J.parseObject(file.readText(Charsets.UTF_8), NfDocModel.SCHEMA))
                            }
                            val ordered = docs.sortedBy { it.title }
                            var acc: NfDoc? = null
                            val conflicts = mutableListOf<NfDocMerger.Conflict>()
                            ordered.forEach { doc ->
                                if (acc == null) acc = doc else {
                                    val r = NfDocMerger.merge(acc!!, doc, "合并文档")
                                    acc = r.doc
                                    conflicts += r.conflicts
                                }
                            }
                            val final = acc ?: error("empty")
                            val out = File(outDir, "merged-" + System.nanoTime() + ".nfdoc.json")
                            out.writeText(NfDocModel.toJson(final).toString() + "\n", Charsets.UTF_8)
                            NfDocMerger.Result(final, conflicts) to out
                        }
                        result = merged.first
                        saved = merged.second
                        files = outDir.listFiles { f -> f.isFile && f.name.endsWith(".nfdoc.json") }?.sortedBy { it.name }.orEmpty()
                    } catch (t: Throwable) {
                        error = context.getString(R.string.nfdoc_merge_failed, t.message ?: t.javaClass.simpleName)
                    }
                }
            }
        ) { Text(stringResource(R.string.nfdoc_merge_action)) }
    }
}
