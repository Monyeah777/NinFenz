package dev.ninfenz.mobile.data

import android.content.Context
import android.net.Uri
import com.google.android.gms.tasks.Tasks
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.chinese.ChineseTextRecognizerOptions
import java.io.File
import java.util.concurrent.TimeUnit

/** 图片 OCR：中文优先，返回纯文本；不伪造空白图片的结果。 */
object ImageOcrImporter {
    fun extract(context: Context, file: File): String {
        require(file.isFile && file.length() in 1..(25L * 1024 * 1024)) { "图片为空或超过 25MB" }
        val image = InputImage.fromFilePath(context, Uri.fromFile(file))
        val recognizer = TextRecognition.getClient(ChineseTextRecognizerOptions.Builder().build())
        return try {
            val result = Tasks.await(recognizer.process(image), 60, TimeUnit.SECONDS)
            result.text.trim()
        } finally {
            recognizer.close()
        }
    }
}
