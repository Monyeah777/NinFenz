package dev.ninfenz.mobile.ui.components

import android.graphics.BitmapFactory
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import dev.ninfenz.mobile.data.PdfMarkdown
import dev.ninfenz.mobile.ui.theme.NfSpacing

/** 轻量 Markdown 渲染：标题/段落/列表/引用/代码/表格/规则/内嵌图片，供交付预览使用。 */
@Composable
fun MarkdownPreview(
    markdown: String,
    modifier: Modifier = Modifier,
    limitBlocks: Int? = null
) {
    val all = remember(markdown) { PdfMarkdown.blocks(markdown) }
    val blocks = if (limitBlocks != null) all.take(limitBlocks) else all
    Column(modifier = modifier, verticalArrangement = Arrangement.spacedBy(NfSpacing.s)) {
        var i = 0
        while (i < blocks.size) {
            val block = blocks[i]
            if (block.table) {
                val rows = mutableListOf<PdfMarkdown.Block>()
                while (i < blocks.size && blocks[i].table) {
                    rows.add(blocks[i])
                    i++
                }
                MarkdownTable(rows)
            } else {
                MarkdownBlock(block)
                i++
            }
        }
        if (limitBlocks != null && all.size > blocks.size) {
            Text(
                pluralStringResource(dev.ninfenz.mobile.R.plurals.preview_more, all.size - blocks.size, all.size - blocks.size),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}

@Composable
private fun MarkdownBlock(block: PdfMarkdown.Block) {
    when {
        block.rule -> HorizontalDivider()
        block.image != null -> {
            val bitmap = remember(block.image) {
                runCatching { BitmapFactory.decodeByteArray(block.image, 0, block.image.size) }.getOrNull()
            }
            if (bitmap != null) {
                Image(
                    bitmap = bitmap.asImageBitmap(),
                    contentDescription = block.text.ifBlank { stringResource(dev.ninfenz.mobile.R.string.preview_image) },
                    modifier = Modifier.fillMaxWidth().heightIn(max = 260.dp),
                    contentScale = ContentScale.Fit
                )
            }
        }
        block.level > 0 -> Text(
            text = annotated(block),
            style = when (block.level) {
                1 -> MaterialTheme.typography.headlineSmall
                2 -> MaterialTheme.typography.titleLarge
                3 -> MaterialTheme.typography.titleMedium
                else -> MaterialTheme.typography.titleSmall
            },
            fontWeight = FontWeight.SemiBold,
            modifier = Modifier.padding(top = if (block.level == 1) NfSpacing.s else 0.dp)
        )
        block.code -> Box(
            modifier = Modifier
                .fillMaxWidth()
                .background(MaterialTheme.colorScheme.surfaceVariant, RoundedCornerShape(8.dp))
                .padding(NfSpacing.s)
        ) {
            Text(block.text, fontFamily = FontFamily.Monospace, style = MaterialTheme.typography.bodySmall)
        }
        block.quote -> Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)
        ) {
            Box(
                modifier = Modifier
                    .width(3.dp)
                    .heightIn(min = 20.dp)
                    .background(MaterialTheme.colorScheme.primary, RoundedCornerShape(2.dp))
            )
            Text(
                text = annotated(block),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
        block.bullet -> Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(NfSpacing.s)
        ) {
            Text("•", style = MaterialTheme.typography.bodyLarge)
            Text(annotated(block), style = MaterialTheme.typography.bodyLarge)
        }
        else -> Text(annotated(block), style = MaterialTheme.typography.bodyLarge)
    }
}

@Composable
private fun MarkdownTable(rows: List<PdfMarkdown.Block>) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(MaterialTheme.colorScheme.surfaceVariant, RoundedCornerShape(8.dp))
            .padding(NfSpacing.xs)
    ) {
        rows.forEachIndexed { index, row ->
            val header = row.tableHeader
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(
                        if (header) MaterialTheme.colorScheme.secondaryContainer else MaterialTheme.colorScheme.surfaceVariant
                    )
                    .padding(vertical = 4.dp, horizontal = 6.dp),
                horizontalArrangement = Arrangement.spacedBy(6.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                row.cells.forEach { cell ->
                    Text(
                        cell,
                        modifier = Modifier.weight(1f),
                        style = MaterialTheme.typography.bodySmall,
                        fontWeight = if (header) FontWeight.SemiBold else FontWeight.Normal
                    )
                }
            }
            if (index < rows.lastIndex) HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
        }
    }
}

private fun annotated(block: PdfMarkdown.Block): AnnotatedString {
    if (block.spans.isEmpty()) return AnnotatedString(block.text)
    return buildAnnotatedString {
        block.spans.forEach { span ->
            withStyle(
                SpanStyle(
                    fontWeight = if (span.bold) FontWeight.SemiBold else null,
                    fontStyle = if (span.italic) FontStyle.Italic else null,
                    fontFamily = if (span.code) FontFamily.Monospace else null,
                    background = if (span.code) androidx.compose.ui.graphics.Color(0x1A6750A4) else androidx.compose.ui.graphics.Color.Unspecified
                )
            ) { append(span.text) }
        }
    }
}
