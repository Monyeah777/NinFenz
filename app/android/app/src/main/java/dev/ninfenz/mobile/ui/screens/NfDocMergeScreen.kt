package dev.ninfenz.mobile.ui.screens

import dev.ninfenz.mobile.ui.design.NfType

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
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
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
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
    val mergedTitle = stringResource(R.string.nfdoc_merged_title)
    val scope = rememberCoroutineScope()
    val outDir = remember(filesDir) { File(File(filesDir, "exports"), "delivery").apply { mkdirs() } }
    var files by remember { mutableStateOf(outDir.listFiles { f -> f.isFile && f.name.endsWith(".nfdoc.json") }?.sortedBy { it.name }.orEmpty()) }
    var selected by remember { mutableStateOf<Set<File>>(emptySet()) }
    var base by remember { mutableStateOf<File?>(null) }
    var result by remember { mutableStateOf<NfDocMerger.Result?>(null) }
    var saved by remember { mutableStateOf<File?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var editingBlocks by remember { mutableStateOf(false) }

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
            style = NfType.meta,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        base?.let { file ->
            Text(
                stringResource(R.string.nfdoc_merge_base_label, file.name),
                modifier = Modifier.padding(horizontal = NfSpacing.page),
                style = NfType.meta,
                color = MaterialTheme.colorScheme.primary
            )
        }
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
                    Text(file.name, modifier = Modifier.padding(start = NfSpacing.s).weight(1f))
                    TextButton(onClick = {
                        if (base == file) {
                            base = null
                        } else {
                            base = file
                            selected = selected - file
                        }
                    }) {
                        Text(stringResource(if (base == file) R.string.nfdoc_merge_base_clear else R.string.nfdoc_merge_base_set))
                    }
                }
            }
        }
        error?.let {
            Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(horizontal = NfSpacing.page))
        }
        result?.let { merged ->
            Column(Modifier.padding(horizontal = NfSpacing.page, vertical = NfSpacing.s), verticalArrangement = Arrangement.spacedBy(NfSpacing.xs)) {
                Text(pluralStringResource(R.plurals.nfdoc_merge_result, merged.doc.blocks.size, merged.doc.blocks.size, merged.doc.sources.size))
                Text(stringResource(R.string.nfdoc_merge_conflicts, merged.conflicts.size), color = MaterialTheme.colorScheme.primary)
                merged.conflicts.take(8).forEach { c ->
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            c.title + " · " + c.reason,
                            style = NfType.meta,
                            modifier = Modifier.weight(1f)
                        )
                        androidx.compose.material3.TextButton(onClick = {
                            result = merged.copy(doc = NfDocMerger.resolve(merged.doc, c, NfDocMerger.Keep.LEFT))
                            saved = null
                        }) { Text(stringResource(R.string.nfdoc_merge_keep_left)) }
                        androidx.compose.material3.TextButton(onClick = {
                            result = merged.copy(doc = NfDocMerger.resolve(merged.doc, c, NfDocMerger.Keep.RIGHT))
                            saved = null
                        }) { Text(stringResource(R.string.nfdoc_merge_keep_right)) }
                        androidx.compose.material3.TextButton(onClick = {
                            result = merged.copy(doc = NfDocMerger.resolve(merged.doc, c, NfDocMerger.Keep.BOTH))
                            saved = null
                        }) { Text(stringResource(R.string.nfdoc_merge_keep_both)) }
                    }
                }
                androidx.compose.material3.TextButton(onClick = { editingBlocks = !editingBlocks }) {
                    Text(stringResource(if (editingBlocks) R.string.nfdoc_merge_hide_blocks else R.string.nfdoc_merge_edit_blocks))
                }
                if (editingBlocks) {
                    Column(Modifier.heightIn(max = 240.dp).verticalScroll(rememberScrollState())) {
                        merged.doc.blocks.forEachIndexed { index, block ->
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Text(
                                    block.type + " · " + block.text.replace("\n", " ").take(60),
                                    style = NfType.meta,
                                    modifier = Modifier.weight(1f)
                                )
                                androidx.compose.material3.TextButton(
                                    enabled = index > 0,
                                    onClick = {
                                        val blocks = merged.doc.blocks.toMutableList().also {
                                            val item = it.removeAt(index)
                                            it.add(index - 1, item)
                                        }.mapIndexed { i, b -> b.copy(id = "b" + (i + 1)) }
                                        result = merged.copy(doc = merged.doc.copy(blocks = blocks))
                                        saved = null
                                    }
                                ) { Text(stringResource(R.string.preview_block_up)) }
                                androidx.compose.material3.TextButton(
                                    enabled = index < merged.doc.blocks.lastIndex,
                                    onClick = {
                                        val blocks = merged.doc.blocks.toMutableList().also {
                                            val item = it.removeAt(index)
                                            it.add(index + 1, item)
                                        }.mapIndexed { i, b -> b.copy(id = "b" + (i + 1)) }
                                        result = merged.copy(doc = merged.doc.copy(blocks = blocks))
                                        saved = null
                                    }
                                ) { Text(stringResource(R.string.preview_block_down)) }
                                androidx.compose.material3.TextButton(onClick = {
                                    val blocks = merged.doc.blocks.filterIndexed { i, _ -> i != index }
                                        .mapIndexed { i, b -> b.copy(id = "b" + (i + 1)) }
                                    result = merged.copy(doc = merged.doc.copy(blocks = blocks))
                                    saved = null
                                }) { Text(stringResource(R.string.nfdoc_merge_delete_block)) }
                            }
                        }
                    }
                }
                Row(horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
                    Button(onClick = {
                        val current = result ?: return@Button
                        scope.launch {
                            val out = withContext(Dispatchers.IO) {
                                val file = File(outDir, "merged-" + System.nanoTime() + ".nfdoc.json")
                                file.writeText(NfDocModel.toJson(current.doc).toString() + "\n", Charsets.UTF_8)
                                file
                            }
                            saved = out
                            files = outDir.listFiles { f -> f.isFile && f.name.endsWith(".nfdoc.json") }?.sortedBy { it.name }.orEmpty()
                        }
                    }) { Text(stringResource(R.string.nfdoc_merge_save)) }
                    saved?.let { file ->
                        OutlinedButton(onClick = {
                            val intent = ShareExporter.shareFileIntent(context, file, "application/json", file.name)
                            ShareExporter.launchChooser(context, intent, file.name)
                        }) { Text(stringResource(R.string.nfdoc_merge_share)) }
                    }
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
                            if (base != null) {
                                val ordered = selected.sortedBy { it.name }.take(2).map { file ->
                                    NfDocModel.parse(J.parseObject(file.readText(Charsets.UTF_8), NfDocModel.SCHEMA))
                                }
                                val baseDoc = NfDocModel.parse(
                                    J.parseObject(base!!.readText(Charsets.UTF_8), NfDocModel.SCHEMA)
                                )
                                if (ordered.size < 2) error(context.getString(R.string.nfdoc_merge_need_two))
                                NfDocMerger.merge3(baseDoc, ordered[0], ordered[1], mergedTitle)
                            } else {
                                val ordered = docs.sortedBy { it.title }
                                var acc: NfDoc? = null
                                val conflicts = mutableListOf<NfDocMerger.Conflict>()
                                ordered.forEach { doc ->
                                    if (acc == null) acc = doc else {
                                        val r = NfDocMerger.merge(acc!!, doc, mergedTitle)
                                        acc = r.doc
                                        conflicts += r.conflicts
                                    }
                                }
                                val final = acc ?: error("empty")
                                NfDocMerger.Result(final, conflicts)
                            }
                        }
                        result = merged
                        saved = null
                    } catch (t: Throwable) {
                        error = context.getString(R.string.nfdoc_merge_failed, t.message ?: t.javaClass.simpleName)
                    }
                }
            }
        ) { Text(stringResource(R.string.nfdoc_merge_action)) }
    }
}
