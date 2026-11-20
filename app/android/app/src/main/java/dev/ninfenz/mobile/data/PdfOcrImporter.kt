package dev.ninfenz.mobile.data

import android.content.Context
import android.graphics.Bitmap
import com.tom_roush.pdfbox.android.PDFBoxResourceLoader
import com.tom_roush.pdfbox.io.MemoryUsageSetting
import com.tom_roush.pdfbox.pdmodel.PDDocument
import com.tom_roush.pdfbox.rendering.PDFRenderer
import java.io.File

/** 扫描 PDF 的兜底 OCR：逐页渲染后识别，限制页数避免无限等待。 */
object PdfOcrImporter {
    private const val MAX_PAGES = 20

    fun extract(context: Context, file: File): String {
        require(file.isFile && file.length() in 1..(25L * 1024 * 1024)) { "PDF 文件为空或超过 25MB" }
        PDFBoxResourceLoader.init(context.applicationContext)
        PDDocument.load(file, MemoryUsageSetting.setupTempFileOnly()).use { document ->
            require(!document.isEncrypted) { "PDF 已加密" }
            val pages = minOf(document.numberOfPages, MAX_PAGES)
            if (pages <= 0) return ""
            val renderer = PDFRenderer(document)
            val text = StringBuilder()
            for (page in 0 until pages) {
                val bitmap: Bitmap = renderer.renderImageWithDPI(page, 150f)
                try {
                    val pageText = ImageOcrImporter.extract(bitmap)
                    if (pageText.isNotBlank()) text.append(pageText).append("\n\n")
                } finally {
                    bitmap.recycle()
                }
            }
            return text.toString().trim()
        }
    }
}
