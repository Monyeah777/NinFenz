package dev.ninfenz.mobile.ui.screens

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import dev.ninfenz.mobile.data.DeliveryDraftStore
import dev.ninfenz.mobile.data.HandoffService
import dev.ninfenz.mobile.data.ReviewStore
import dev.ninfenz.mobile.model.MarkdownBlocks
import dev.ninfenz.mobile.model.Project
import dev.ninfenz.mobile.share.ShareExporter
import dev.ninfenz.mobile.ui.components.CardBox
import dev.ninfenz.mobile.ui.components.EmptyState
import dev.ninfenz.mobile.ui.components.NfScaffold
import dev.ninfenz.mobile.ui.design.NfType
import dev.ninfenz.mobile.ui.theme.NfSpacing
import java.io.File

@Composable
fun ProjectReviewScreen(project: Project, onBack: () -> Unit) {
    val context = LocalContext.current
    val store = remember { ReviewStore(context.filesDir) }
    val markdown = remember(project.id) { DeliveryDraftStore(context.filesDir).loadMarkdown(project.id) }
    val blocks = remember(markdown) { markdown?.let { MarkdownBlocks.parse(it) }.orEmpty() }
    val projectFile = File(File(context.filesDir, "projects"), project.id + ".nfproject.json")
    val subjectDigest = remember(project.id) {
        ReviewStore.sha256(if (projectFile.isFile) projectFile.readText(Charsets.UTF_8) else project.id)
    }
    var doc by remember(project.id) { mutableStateOf(store.load(project.id, subjectDigest)) }
    var commentBlock by remember { mutableStateOf<Int?>(null) }
    var commentText by remember { mutableStateOf("") }
    var imported by remember { mutableStateOf<HandoffService.Inspect?>(null) }
    val handoffPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        if (uri == null) return@rememberLauncherForActivityResult
        runCatching {
            val temp = File(File(context.cacheDir, "handoff-import").apply { mkdirs() }, "handoff.zip")
            context.contentResolver.openInputStream(uri)?.use { input ->
                temp.outputStream().use { output -> input.copyTo(output) }
            }
            imported = HandoffService.inspect(temp)
        }.onFailure {
            imported = HandoffService.Inspect(false, "", emptyList(), it.message ?: it.javaClass.simpleName)
        }
    }

    NfScaffold(title = stringResource(dev.ninfenz.mobile.R.string.review_blocks_title), onBack = onBack) {
        CardBox(title = null) {
            Text(project.title, style = NfType.itemTitle)
            Text(
                stringResource(dev.ninfenz.mobile.R.string.review_blocks_summary, doc.comments.count { it.status == "unresolved" }, doc.verdict),
                style = NfType.meta,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            TextButton(onClick = {
                runCatching {
                    val projectJson = projectFile.readText(Charsets.UTF_8)
                    val reviewJson = store.fileFor(project.id).takeIf { it.isFile }?.readText(Charsets.UTF_8) ?: "{}"
                    val zip = HandoffService.export(
                        project.id,
                        projectJson,
                        reviewJson,
                        markdown,
                        File(File(context.filesDir, "exports"), "handoff")
                    )
                    val intent = ShareExporter.shareFileIntent(context, zip, "application/zip", project.title + " review")
                    ShareExporter.launchChooser(context, intent, context.getString(dev.ninfenz.mobile.R.string.review_export_handoff))
                }
            }) { Text(stringResource(dev.ninfenz.mobile.R.string.review_export_handoff)) }
            TextButton(onClick = { handoffPicker.launch(arrayOf("application/zip", "*/*")) }) {
                Text(stringResource(dev.ninfenz.mobile.R.string.review_import_handoff))
            }
        }
        if (blocks.isEmpty()) {
            EmptyState(stringResource(dev.ninfenz.mobile.R.string.review_blocks_no_content))
        } else {
            Column(
                modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(NfSpacing.m)
            ) {
                blocks.forEach { block ->
                    val comments = doc.comments.filter { it.blockId == block.id.toString() }
                    CardBox(title = stringResource(dev.ninfenz.mobile.R.string.review_block_title, block.id + 1, block.kind)) {
                        Text(block.text.take(1200), style = NfType.secondary)
                        TextButton(onClick = {
                            commentBlock = block.id
                            commentText = ""
                        }) { Text(stringResource(dev.ninfenz.mobile.R.string.review_add_comment)) }
                        comments.forEach { comment ->
                            Column(modifier = Modifier.fillMaxWidth().padding(top = 4.dp)) {
                                Text(comment.author + " · " + comment.status, style = NfType.meta, color = MaterialTheme.colorScheme.primary)
                                Text(comment.body, style = NfType.secondary)
                                TextButton(onClick = {
                                    doc = store.setStatus(doc, comment.id, if (comment.status == "resolved") "unresolved" else "resolved")
                                }) {
                                    Text(stringResource(if (comment.status == "resolved") dev.ninfenz.mobile.R.string.review_reopen else dev.ninfenz.mobile.R.string.review_resolve))
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    imported?.let { info ->
        AlertDialog(
            onDismissRequest = { imported = null },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.review_import_handoff)) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text(if (info.ok) stringResource(dev.ninfenz.mobile.R.string.review_handoff_ok) else (info.error ?: "invalid"), style = NfType.meta)
                    info.files.forEach { Text("• " + it, style = NfType.meta) }
                }
            },
            confirmButton = { TextButton(onClick = { imported = null }) { Text(stringResource(android.R.string.ok)) } }
        )
    }

    commentBlock?.let { blockId ->
        AlertDialog(
            onDismissRequest = { commentBlock = null },
            title = { Text(stringResource(dev.ninfenz.mobile.R.string.review_add_comment)) },
            text = {
                OutlinedTextField(
                    value = commentText,
                    onValueChange = { commentText = it },
                    label = { Text(stringResource(dev.ninfenz.mobile.R.string.review_comment_hint)) },
                    minLines = 3,
                    modifier = Modifier.fillMaxWidth()
                )
            },
            confirmButton = {
                Button(
                    enabled = commentText.isNotBlank(),
                    onClick = {
                        val block = blocks.firstOrNull { it.id == blockId } ?: return@Button
                        doc = store.add(doc, block.id.toString(), block.text, commentText, "local")
                        commentBlock = null
                    }
                ) { Text(stringResource(android.R.string.ok)) }
            },
            dismissButton = {
                TextButton(onClick = { commentBlock = null }) { Text(stringResource(android.R.string.cancel)) }
            }
        )
    }
}
