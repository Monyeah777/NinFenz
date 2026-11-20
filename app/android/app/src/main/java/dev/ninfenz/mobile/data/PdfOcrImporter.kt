package dev.ninfenz.mobile.data

import android.content.Context
import android.graphics.Bitmap
import com.tom_roush.pdfbox.io.MemoryUsageSetting
import com.tom_roush.pdfbox.pdmodel.PDDocument
import com.tom_roush.pdfbox.rendering.PDFRenderer
import java.io.File

/** 扫描 PDF 的兜底 OCR：逐页渲染后识别，限制页数避免无限等待。 */
object PdfOcrImporter {
    private const val MAX_PAGES = 20
    data class Result(val text: String, val pages: Int, val truncated: Boolean)

    fun extract(context: Context, file: File): Result {
        require(file.isFile && file.length() in 1..(25L * 1024 * 1024)) { "PDF 文件为空或超过 25MB" }
        PdfTextImporter.ensureInitialized(context)
        PDDocument.load(file, MemoryUsageSetting.setupTempFileOnly()).use { document ->
            require(!document.isEncrypted) { "PDF 已加密" }
            val pages = minOf(document.numberOfPages, MAX_PAGES)
            if (pages <= 0) return Result("", 0, false)
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
            return Result(text.toString().trim(), pages, document.numberOfPages > MAX_PAGES)
        }
    }
}
