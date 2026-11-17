package dev.ninfenz.mobile.data

import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
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
        data class Line(val text: String, val size: Float, val bold: Boolean)

        val lineHeight = 16f
        val contentWidth = pageWidth - margin * 2
        val lines = buildList {
            add(Line(title, 18f, true))
            add(Line("", 11f, false))
            PdfMarkdown.blocks(markdown).forEach { block ->
                val size = when (block.level) {
                    1 -> 20f
                    2 -> 18f
                    3 -> 16f
                    4 -> 14f
                    5 -> 13f
                    6 -> 12f
                    else -> 11f
                }
                val bold = block.level > 0
                val prefix = if (block.bullet) "• " else ""
                PdfPager.wrap(prefix + block.text, contentWidth) { paint.measureText(it) * (size / 11f) }
                    .forEach { add(Line(it, size, bold)) }
            }
        }
        val firstPageLines = ((pageHeight - margin * 2 - lineHeight * 4) / lineHeight).toInt().coerceAtLeast(1)
        val pages = PdfPager.paginateItems(lines, firstPageLines)
        val doc = PdfDocument()
        try {
            pages.forEachIndexed { index, pageLines ->
                val page = doc.startPage(PdfDocument.PageInfo.Builder(pageWidth, pageHeight, index + 1).create())
                val canvas: Canvas = page.canvas
                var y = margin + 20f
                pageLines.forEach { line ->
                    val p = Paint(paint).apply {
                        textSize = line.size
                        isFakeBoldText = line.bold
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
}
