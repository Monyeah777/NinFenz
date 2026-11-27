package dev.ninfenz.mobile.data

import android.content.Context
import android.net.Uri
import java.io.File
import java.io.InputStreamReader

/**
 * content:// URI 的读取入口。
 *
 * UI 层不得直接碰 ContentResolver（审计规则 B-004：UI 只做交互，平台 IO 走 data 层），
 * 导入/恢复/对比等路径统一从这里读。
 */
object UriIo {
    /** 把 URI 内容复制到 [target]；URI 打不开返回 false。 */
    fun copyTo(context: Context, uri: Uri, target: File): Boolean {
        target.parentFile?.mkdirs()
        val input = context.contentResolver.openInputStream(uri) ?: return false
        input.use { src -> target.outputStream().use { dst -> src.copyTo(dst) } }
        return true
    }

    /** 读全文；URI 打不开返回 null。 */
    fun readText(context: Context, uri: Uri): String? =
        context.contentResolver.openInputStream(uri)?.bufferedReader(Charsets.UTF_8)?.use { it.readText() }

    /** 限长读文本：超过 [maxChars] 抛 IllegalArgumentException([tooLargeMessage])。 */
    fun readTextLimited(context: Context, uri: Uri, maxChars: Int, tooLargeMessage: String): String {
        val stream = context.contentResolver.openInputStream(uri) ?: return ""
        stream.use { input ->
            val reader = InputStreamReader(input, Charsets.UTF_8)
            val buffer = CharArray(8192)
            val out = StringBuilder()
            while (true) {
                val n = reader.read(buffer)
                if (n < 0) break
                out.append(buffer, 0, n)
                if (out.length > maxChars) throw IllegalArgumentException(tooLargeMessage)
            }
            return out.toString()
        }
    }
}
