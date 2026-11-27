package dev.ninfenz.mobile.data

import android.content.Context
import java.io.File

/** 基础包 stub：PDF OCR 在 :feature:ocr；未安装时明确失败。 */
object PdfOcrImporter {
    data class Result(val text: String, val pages: Int, val truncated: Boolean)

    fun extract(context: Context, file: File): Result =
        OcrFeatureBridge.call("extractPdf", context, file) as? Result
            ?: throw IllegalStateException("OCR 扩展返回空结果")
}
