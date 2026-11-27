package dev.ninfenz.mobile.ocr

import android.content.Context
import android.graphics.Bitmap
import com.tom_roush.pdfbox.android.PDFBoxResourceLoader
import com.tom_roush.pdfbox.io.MemoryUsageSetting
import com.tom_roush.pdfbox.pdmodel.PDDocument
import com.tom_roush.pdfbox.rendering.PDFRenderer
import dev.ninfenz.mobile.data.PdfOcrImporter
import java.io.File

/** OCR 动态 feature 的扫描 PDF 兜底实现。 */
object PdfOcrFeature {
    private const val MAX_PAGES = 20

    fun extract(context: Context, file: File): PdfOcrImporter.Result {
        require(file.isFile && file.length() in 1..(25L * 1024 * 1024)) { "PDF 文件为空或超过 25MB" }
        PDFBoxResourceLoader.init(context.applicationContext)
        PDDocument.load(file, MemoryUsageSetting.setupTempFileOnly()).use { document ->
            require(!document.isEncrypted) { "PDF 已加密" }
            val pages = minOf(document.numberOfPages, MAX_PAGES)
            if (pages <= 0) return PdfOcrImporter.Result("", 0, false)
            val renderer = PDFRenderer(document)
            val recognizer = ImageOcrImporter.newRecognizer()
            val text = StringBuilder()
            try {
                for (page in 0 until pages) {
                    val bitmap: Bitmap = renderer.renderImageWithDPI(page, 150f)
                    require(bitmap.width.toLong() * bitmap.height.toLong() <= 40_000_000L) { "PDF 页面渲染尺寸过大" }
                    try {
                        val pageText = ImageOcrImporter.extract(bitmap, recognizer)
                        if (pageText.isNotBlank()) text.append(pageText).append("\n\n")
                    } finally {
                        bitmap.recycle()
                    }
                }
            } finally {
                recognizer.close()
            }
            return PdfOcrImporter.Result(text.toString().trim(), pages, document.numberOfPages > MAX_PAGES)
        }
    }
}
