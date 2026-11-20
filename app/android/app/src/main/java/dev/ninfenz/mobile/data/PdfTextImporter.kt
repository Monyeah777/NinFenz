package dev.ninfenz.mobile.data

import android.content.Context
import com.tom_roush.pdfbox.android.PDFBoxResourceLoader
import com.tom_roush.pdfbox.pdmodel.PDDocument
import com.tom_roush.pdfbox.text.PDFTextStripper
import java.io.File

/** PDF 文字层提取；扫描件没有文字层，明确报空而不是伪造 OCR。 */
object PdfTextImporter {
    @Volatile
    private var initialized = false

    fun extract(context: Context, file: File): String {
        require(file.isFile && file.length() in 1..(25L * 1024 * 1024)) { "PDF 文件为空或超过 25MB" }
        if (!initialized) {
            synchronized(this) {
                if (!initialized) {
                    PDFBoxResourceLoader.init(context.applicationContext)
                    initialized = true
                }
            }
        }
        PDDocument.load(file).use { document ->
            require(!document.isEncrypted) { "PDF 已加密" }
            require(document.numberOfPages <= 500) { "PDF 页数超过 500" }
            return PDFTextStripper().apply { sortByPosition = true }.getText(document)
                .replace("\r\n", "\n")
                .replace('\u000C', '\n')
                .replace(Regex("\n{3,}"), "\n\n")
                .trim()
        }
    }
}
