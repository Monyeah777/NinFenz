package dev.ninfenz.mobile.data

import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Paint
import android.graphics.RectF
import android.graphics.Typeface
import android.graphics.pdf.PdfDocument
import java.io.File

/** 基础文本 PDF 导出：A4、自动折行/分页；不依赖外部渲染引擎。 */
object PdfExporter {
    data class Created(val file: File, val pages: Int, val bytes: Long)

    fun export(markdown: String, title: String, outDir: File): Created {
        outDir.mkdirs()
        val target = File(outDir, "result.pdf")
        val pageWidth = 595
        val pageHeight = 842
        val margin = 48f
        val paint = Paint().apply {
            color = Color.BLACK
            textSize = 11f
            isAntiAlias = true
        }
        data class Line(
            val text: String,
            val size: Float,
            val bold: Boolean,
            val mono: Boolean = false,
            val italic: Boolean = false,
            val rule: Boolean = false,
            val cells: List<String> = emptyList(),
            val table: Boolean = false,
            val weights: FloatArray? = null,
            val spans: List<PdfMarkdown.Span> = emptyList(),
            val image: Bitmap? = null,
            val imageWidth: Float = 0f,
            val imageHeight: Float = 0f,
            val weight: Int = 1
        )

        val lineHeight = 16f
        val contentWidth = pageWidth - margin * 2
        val blockList = PdfMarkdown.blocks(markdown)
        val maxCols = blockList.filter { it.table }.maxOfOrNull { it.cells.size } ?: 0
        val colWeights = FloatArray(maxCols) { 1f }
        blockList.forEach { block ->
            if (block.table) {
                block.cells.forEachIndexed { i, cell ->
                    colWeights[i] = maxOf(colWeights[i], cell.length.toFloat().coerceAtMost(40f))
                }
            }
        }
        fun sliceSpans(spans: List<PdfMarkdown.Span>, start: Int, end: Int): List<PdfMarkdown.Span> {
            val out = mutableListOf<PdfMarkdown.Span>()
            var pos = 0
            for (span in spans) {
                val spanStart = pos
                val spanEnd = pos + span.text.length
                val from = maxOf(start, spanStart)
                val to = minOf(end, spanEnd)
                if (from < to) {
                    out.add(span.copy(text = span.text.substring(from - spanStart, to - spanStart)))
                }
                pos = spanEnd
            }
            return out
        }
        val lines = buildList {
            add(Line(title, 18f, true))
            add(Line("", 11f, false))
            blockList.forEach { block ->
                if (block.rule) {
                    add(Line("", 11f, false, rule = true))
                    return@forEach
                }
                if (block.image != null) {
                    val bitmap = BitmapFactory.decodeByteArray(block.image, 0, block.image.size)
                    if (bitmap != null) {
                        val maxWidth = contentWidth * 0.8f
                        val maxHeight = pageHeight - margin * 2 - lineHeight * 4
                        val scale = minOf(1f, maxWidth / bitmap.width, maxHeight / bitmap.height)
                        val w = bitmap.width * scale
                        val h = bitmap.height * scale
                        add(
                            Line(
                                block.text, 10f, false,
                                image = bitmap,
                                imageWidth = w,
                                imageHeight = h,
                                weight = (h / lineHeight).toInt().coerceAtLeast(1)
                            )
                        )
                    } else {
                        add(Line(block.text, 10f, false))
                    }
                    return@forEach
                }
                if (block.table && block.cells.isNotEmpty()) {
                    add(
                        Line(
                            "", 10f, block.tableHeader,
                            cells = block.cells,
                            table = true,
                            weights = if (colWeights.size == block.cells.size) colWeights else null
                        )
                    )
                    return@forEach
                }
                val size = if (block.table) 10f else when (block.level) {
                    1 -> 20f
                    2 -> 18f
                    3 -> 16f
                    4 -> 14f
                    5 -> 13f
                    6 -> 12f
                    else -> 11f
                }
                val bold = block.level > 0 || block.tableHeader
                val baseSpans = if (block.spans.isEmpty()) listOf(PdfMarkdown.Span(block.text)) else block.spans
                val spans = if (block.bullet) listOf(PdfMarkdown.Span("• ")) + baseSpans else baseSpans
                val plain = spans.joinToString("") { it.text }
                var offset = 0
                PdfPager.wrap(plain, contentWidth) { paint.measureText(it) * (size / 11f) }
                    .forEach { wrapped ->
                        val end = offset + wrapped.length
                        add(Line(wrapped, size, bold, block.code, block.quote, spans = sliceSpans(spans, offset, end)))
                        offset = end
                    }
            }
        }
        val firstPageLines = ((pageHeight - margin * 2 - lineHeight * 4) / lineHeight).toInt().coerceAtLeast(1)
        val pages = PdfPager.paginateWeighted(lines.map { it.weight }, firstPageLines)
            .map { lines.subList(it.first, it.last + 1) }
        val doc = PdfDocument()
        try {
            pages.forEachIndexed { index, pageLines ->
                val page = doc.startPage(PdfDocument.PageInfo.Builder(pageWidth, pageHeight, index + 1).create())
                val canvas: Canvas = page.canvas
                var y = margin + 20f
                pageLines.forEach { line ->
                    if (line.rule) {
                        canvas.drawLine(margin, y - 6f, pageWidth - margin, y - 6f, paint)
                        y += 8f
                        return@forEach
                    }
                    if (line.image != null) {
                        val bmp = line.image
                        val x = margin + (contentWidth - line.imageWidth) / 2f
                        canvas.drawBitmap(bmp, null, RectF(x, y, x + line.imageWidth, y + line.imageHeight), null)
                        y += line.imageHeight + 4f
                        return@forEach
                    }
                    if (line.spans.isNotEmpty()) {
                        var x = margin
                        for (span in line.spans) {
                            if (span.text.isEmpty()) continue
                            val sp = Paint(paint).apply {
                                textSize = line.size
                                isFakeBoldText = line.bold || span.bold
                                typeface = if (span.code || line.mono) Typeface.MONOSPACE else Typeface.DEFAULT
                                if (line.italic || span.italic) textSkewX = -0.25f
                            }
                            canvas.drawText(span.text, x, y, sp)
                            x += sp.measureText(span.text)
                        }
                        y += maxOf(lineHeight, line.size * 1.3f)
                        return@forEach
                    }
                    if (line.cells.isNotEmpty()) {
                        val weights = line.weights ?: FloatArray(line.cells.size) { 1f }
                        val totalWeight = weights.sum().coerceAtLeast(1f)
                        val p = Paint(paint).apply {
                            textSize = line.size
                            isFakeBoldText = line.bold
                        }
                        var x = margin
                        val xs = mutableListOf<Float>()
                        line.cells.forEachIndexed { i, cell ->
                            val w = contentWidth * weights[i] / totalWeight
                            canvas.drawText(ellipsize(cell, p, w - 6f), x, y, p)
                            xs.add(x)
                            x += w
                        }
                        if (line.table) {
                            for (i in 1 until line.cells.size) {
                                canvas.drawLine(xs[i], y - line.size, xs[i], y + 4f, paint)
                            }
                            canvas.drawLine(margin, y + 4f, pageWidth - margin, y + 4f, paint)
                        }
                        y += lineHeight
                        return@forEach
                    }
                    if (line.mono) {
                        val bg = Paint().apply { color = Color.rgb(245, 245, 245) }
                        canvas.drawRect(margin - 4f, y - line.size - 2f, margin + contentWidth, y + 4f, bg)
                    }
                    if (line.italic) {
                        canvas.drawLine(margin - 6f, y - line.size, margin - 6f, y + 4f, paint)
                    }
                    val p = Paint(paint).apply {
                        textSize = line.size
                        isFakeBoldText = line.bold
                        typeface = if (line.mono) Typeface.MONOSPACE else Typeface.DEFAULT
                        if (line.italic) textSkewX = -0.25f
                    }
                    canvas.drawText(line.text, margin, y, p)
                    y += maxOf(lineHeight, line.size * 1.3f)
                }
                canvas.drawText((index + 1).toString() + " / " + pages.size, pageWidth - margin - 40f, pageHeight - margin / 2, paint)
                doc.finishPage(page)
            }
            target.outputStream().use { doc.writeTo(it) }
        } finally {
            doc.close()
        }
        return Created(target, pages.size, target.length())
    }

    private fun ellipsize(text: String, paint: Paint, maxWidth: Float): String {
        if (paint.measureText(text) <= maxWidth) return text
        var end = text.length
        while (end > 0 && paint.measureText(text.substring(0, end) + "…") > maxWidth) end--
        return text.substring(0, end) + "…"
    }
}
