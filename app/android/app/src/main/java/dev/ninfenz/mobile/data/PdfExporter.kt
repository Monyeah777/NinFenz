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
        val titlePaint = Paint().apply {
            color = Color.BLACK
            textSize = 16f
            isAntiAlias = true
            isFakeBoldText = true
        }
        val lineHeight = 16f
        val contentWidth = pageWidth - margin * 2
        val lines = buildList {
            add(title)
            add("")
            PdfMarkdown.lines(markdown).forEach { raw ->
                PdfPager.wrap(raw, contentWidth) { paint.measureText(it) }.forEach { add(it) }
            }
        }
        val firstPageLines = ((pageHeight - margin * 2 - lineHeight * 3) / lineHeight).toInt().coerceAtLeast(1)
        val pages = PdfPager.paginate(lines, firstPageLines)
        val doc = PdfDocument()
        try {
            pages.forEachIndexed { index, pageLines ->
                val page = doc.startPage(PdfDocument.PageInfo.Builder(pageWidth, pageHeight, index + 1).create())
                val canvas: Canvas = page.canvas
                var y = margin + lineHeight
                pageLines.forEachIndexed { lineIndex, line ->
                    val p = if (index == 0 && lineIndex == 0) titlePaint else paint
                    canvas.drawText(line, margin, y, p)
                    y += lineHeight
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
