package dev.ninfenz.mobile.ui.screens

import dev.ninfenz.mobile.util.orNullLogged
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.TextButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import dev.ninfenz.mobile.data.ExportProfileStore
import dev.ninfenz.mobile.model.Project
import dev.ninfenz.mobile.share.ShareExporter
import dev.ninfenz.mobile.ui.components.NfCollapsibleSection
import dev.ninfenz.mobile.ui.components.MarkdownPreview
import dev.ninfenz.mobile.ui.theme.NfSpacing
import dev.ninfenz.mobile.ui.design.NfType

internal class DeliveryPreviewArgs(
    val markdown: String?,
    val project: Project,
    val sampleStore: dev.ninfenz.mobile.data.PromptSampleStore,
    val copyMarkdown: (String) -> Unit,
    val onShowVersions: () -> Unit,
    val onEditPreview: (String) -> Unit,
    val onFullPreview: () -> Unit
)

@Composable
internal fun DeliveryPreviewSection(a: DeliveryPreviewArgs) {
    val context = androidx.compose.ui.platform.LocalContext.current
    NfCollapsibleSection(title = stringResource(dev.ninfenz.mobile.R.string.delivery_preview), initiallyExpanded = true) {
        TextButton(onClick = a.onShowVersions) {
            Text(stringResource(dev.ninfenz.mobile.R.string.delivery_versions))
        }
        val md = a.markdown
        if (md == null) {
            Text(stringResource(dev.ninfenz.mobile.R.string.delivery_not_assembled), style = NfType.meta, modifier = Modifier.padding(horizontal = NfSpacing.page))
        } else {
            Column(modifier = Modifier.padding(horizontal = NfSpacing.page)) {
                MarkdownPreview(md, limitBlocks = 8)
                Row {
                    TextButton(onClick = { a.onEditPreview(md) }) {
                        Text(stringResource(dev.ninfenz.mobile.R.string.preview_edit))
                    }
                    TextButton(onClick = a.onFullPreview) {
                        Text(stringResource(dev.ninfenz.mobile.R.string.preview_full))
                    }
                    TextButton(onClick = { a.copyMarkdown(md) }) {
                        Text(stringResource(dev.ninfenz.mobile.R.string.preview_copy))
                    }
                    TextButton(onClick = {
                        val safe = dev.ninfenz.mobile.data.ShareRedactor.redact(md)
                        val intent = ShareExporter.shareMarkdown(context, "nf-redacted", safe)
                        ShareExporter.launchChooser(context, intent, context.getString(dev.ninfenz.mobile.R.string.preview_share_redacted))
                    }) { Text(stringResource(dev.ninfenz.mobile.R.string.preview_share_redacted)) }
                    TextButton(onClick = {
                        val saved = runCatching { a.sampleStore.save("delivery-" + a.project.id, md) }.orNullLogged("DeliveryScreen")
                        android.widget.Toast.makeText(
                            context,
                            if (saved != null) context.getString(dev.ninfenz.mobile.R.string.delivery_save_sample) + ": " + saved.name
                            else context.getString(dev.ninfenz.mobile.R.string.delivery_save_sample),
                            android.widget.Toast.LENGTH_SHORT
                        ).show()
                    }) {
                        Text(stringResource(dev.ninfenz.mobile.R.string.delivery_save_sample))
                    }
                    TextButton(onClick = {
                        val intent = ShareExporter.shareMarkdown(context, "nf-" + a.project.id, md)
                        ShareExporter.launchChooser(context, intent, context.getString(dev.ninfenz.mobile.R.string.delivery_share_md))
                    }) {
                        Text(stringResource(dev.ninfenz.mobile.R.string.delivery_share_md))
                    }
                }
            }
        }
    }
}

@Composable
internal fun ExportProfileRow(
    profile: dev.ninfenz.mobile.data.ExportProfileStore.Profile,
    onApply: (dev.ninfenz.mobile.data.ExportProfileStore.Profile) -> Unit,
    onRemove: (dev.ninfenz.mobile.data.ExportProfileStore.Profile) -> Unit
) {
    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
        Text(profile.name, style = NfType.meta)
        Row {
            TextButton(onClick = { onApply(profile) }) {
                Text(stringResource(dev.ninfenz.mobile.R.string.export_profile_apply))
            }
            if (!profile.id.startsWith("ext:")) {
                TextButton(onClick = { onRemove(profile) }) {
                    Text(stringResource(dev.ninfenz.mobile.R.string.inbox_remove))
                }
            }
        }
    }
}

@Composable
internal fun PreviewSuggestionApplyButton(slotId: String, text: String, onApply: (String, String) -> Unit) {
    TextButton(onClick = { onApply(slotId, text) }) {
        Text(stringResource(dev.ninfenz.mobile.R.string.preview_suggest_apply))
    }
}
