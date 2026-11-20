package dev.ninfenz.mobile.data

import android.content.Context
import android.net.Uri
import com.google.android.gms.tasks.Tasks
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.TextRecognizer
import com.google.mlkit.vision.text.chinese.ChineseTextRecognizerOptions
import java.io.File
import java.util.concurrent.TimeUnit

/** 图片 OCR：中文优先，返回纯文本；不伪造空白图片的结果。 */
object ImageOcrImporter {
    fun extract(context: Context, file: File): String {
        require(file.isFile && file.length() in 1..(25L * 1024 * 1024)) { "图片为空或超过 25MB" }
        val recognizer = newRecognizer()
        return try {
            extract(InputImage.fromFilePath(context, Uri.fromFile(file)), recognizer)
        } finally {
            recognizer.close()
        }
    }

    fun extract(bitmap: Bitmap): String {
        val recognizer = newRecognizer()
        return try {
            extract(bitmap, recognizer)
        } finally {
            recognizer.close()
        }
    }

    fun newRecognizer(): TextRecognizer =
        TextRecognition.getClient(ChineseTextRecognizerOptions.Builder().build())

    fun extract(bitmap: Bitmap, recognizer: TextRecognizer): String =
        extract(InputImage.fromBitmap(bitmap, 0), recognizer)

    private fun extract(image: InputImage, recognizer: TextRecognizer): String {
        val result = Tasks.await(recognizer.process(image), 60, TimeUnit.SECONDS)
        return result.text.trim()
    }
}
