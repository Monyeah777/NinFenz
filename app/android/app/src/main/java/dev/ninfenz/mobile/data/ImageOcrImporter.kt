package dev.ninfenz.mobile.data

import android.content.Context
import android.graphics.Bitmap
import java.io.File

/** 基础包 stub：实现在 :feature:ocr；未安装时抛错，不伪造识别结果。 */
object ImageOcrImporter {
    fun extract(context: Context, file: File): String =
        OcrFeatureBridge.call("extractImage", context, file) as? String
            ?: throw IllegalStateException("OCR 扩展返回空结果")

    fun extract(bitmap: Bitmap): String = throw IllegalStateException("OCR 扩展未安装")
}
