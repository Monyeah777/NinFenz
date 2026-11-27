package dev.ninfenz.mobile.ocr

import android.content.Context
import dev.ninfenz.mobile.data.PdfOcrImporter
import java.io.File

/** 基础包通过反射调用的稳定入口。 */
object OcrFeature {
    @JvmStatic
    fun extractImage(context: Context, file: File): String = ImageOcrImporter.extract(context, file)

    @JvmStatic
    fun extractPdf(context: Context, file: File): PdfOcrImporter.Result = PdfOcrFeature.extract(context, file)
}
