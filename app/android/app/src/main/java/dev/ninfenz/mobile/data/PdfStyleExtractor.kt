package dev.ninfenz.mobile.data

import com.tom_roush.pdfbox.pdmodel.PDDocument
import com.tom_roush.pdfbox.text.PDFTextStripper
import com.tom_roush.pdfbox.text.TextPosition
import com.tom_roush.pdfbox.io.MemoryUsageSetting
import java.io.File
import kotlin.math.roundToInt

/** PDF 样式抽取：只提取字体名与字号直方图；明确不是完整版式逆向。 */
data class PdfStyle(
    val pages: Int,
    val fonts: List<String>,
    val sizes: Map<Int, Int>
) {
    fun toStyleXml(): String = buildString {
        append("<pdf-style pages=\"")
        append(pages)
        append("\">")
        fonts.sorted().forEach { font ->
            append("<font name=\"")
            append(font.replace("&", "&amp;").replace("\"", "&quot;").replace("<", "&lt;"))
            append("\"/>")
        }
        sizes.toSortedMap().forEach { (size, count) ->
            append("<size value=\"")
            append(size)
            append("\" count=\"")
            append(count)
            append("\"/>")
        }
        append("</pdf-style>")
    }
}

object PdfStyleExtractor {
    fun extract(file: File): PdfStyle {
        val collector = object : PDFTextStripper() {
            val fonts = mutableSetOf<String>()
            val sizes = mutableMapOf<Int, Int>()

            override fun writeString(text: String, textPositions: List<TextPosition>) {
                for (position in textPositions) {
                    runCatching {
                        val name = position.font?.name
                        if (!name.isNullOrBlank()) fonts += name
                    }
                    val size = position.fontSize.roundToInt()
                    if (size > 0) sizes[size] = (sizes[size] ?: 0) + 1
                }
                super.writeString(text, textPositions)
            }
        }
        PDDocument.load(file, MemoryUsageSetting.setupTempFileOnly()).use { document ->
            collector.startPage = 1
            collector.endPage = document.numberOfPages
            collector.getText(document)
            return PdfStyle(
                pages = document.numberOfPages,
                fonts = collector.fonts.toList().sorted(),
                sizes = collector.sizes.toMap()
            )
        }
    }
}
