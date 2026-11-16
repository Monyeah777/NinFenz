package dev.ninfenz.mobile.data

import java.io.File
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

/** 诊断包：只含本地诊断文本与隐私声明；不含网络/账号/内容正文。 */
object DiagnosticsBundle {
    data class Created(val file: File, val bytes: Long)

    fun create(filesDir: File, diagnostics: String): Created {
        val dir = File(filesDir, "exports/diagnostics").apply { mkdirs() }
        val target = File(dir, "nf-diagnostics-" + System.currentTimeMillis() + ".zip")
        ZipOutputStream(target.outputStream()).use { out ->
            put(out, "diagnostics.txt", diagnostics)
            put(out, "README.txt", "NF Mobile 本地诊断包。无网络请求、无账号、无遥测；仅包含应用/核心/错误目录状态与环境信息。\\n")
        }
        return Created(target, target.length())
    }

    private fun put(out: ZipOutputStream, name: String, text: String) {
        out.putNextEntry(ZipEntry(name).apply { time = 0L })
        out.write(text.toByteArray(Charsets.UTF_8))
        out.closeEntry()
    }
}
