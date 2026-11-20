package dev.ninfenz.mobile.data

import java.io.File
import java.nio.charset.Charset

/** 文本编码识别：带 BOM 的 UTF-8/UTF-16 统一转成 UTF-8；另按 NUL 分布识别无 BOM UTF-16；其余返回 null。 */
object TextEncoding {
    data class Decoded(val text: String, val encoding: String)

    fun decode(bytes: ByteArray): Decoded? {
        if (bytes.size >= 3 && bytes[0] == 0xEF.toByte() && bytes[1] == 0xBB.toByte() && bytes[2] == 0xBF.toByte()) {
            return Decoded(String(bytes, 3, bytes.size - 3, Charsets.UTF_8), "UTF-8")
        }
        if (bytes.size >= 2 && bytes[0] == 0xFF.toByte() && bytes[1] == 0xFE.toByte()) {
            return Decoded(String(bytes, 2, bytes.size - 2, Charset.forName("UTF-16LE")), "UTF-16LE")
        }
        if (bytes.size >= 2 && bytes[0] == 0xFE.toByte() && bytes[1] == 0xFF.toByte()) {
            return Decoded(String(bytes, 2, bytes.size - 2, Charset.forName("UTF-16BE")), "UTF-16BE")
        }
        if (bytes.size >= 8) {
            var oddZero = 0
            var evenZero = 0
            for (i in bytes.indices) {
                if (bytes[i] == 0.toByte()) {
                    if (i % 2 == 0) evenZero++ else oddZero++
                }
            }
            if (oddZero > bytes.size / 3 && evenZero < bytes.size / 10) {
                return Decoded(String(bytes, Charset.forName("UTF-16LE")), "UTF-16LE")
            }
            if (evenZero > bytes.size / 3 && oddZero < bytes.size / 10) {
                return Decoded(String(bytes, Charset.forName("UTF-16BE")), "UTF-16BE")
            }
        }
        return null
    }

    fun decodeText(bytes: ByteArray): String {
        decode(bytes)?.let { return it.text }
        return try {
            val decoder = Charsets.UTF_8.newDecoder()
                .onMalformedInput(java.nio.charset.CodingErrorAction.REPORT)
                .onUnmappableCharacter(java.nio.charset.CodingErrorAction.REPORT)
            decoder.decode(java.nio.ByteBuffer.wrap(bytes)).toString()
        } catch (t: Throwable) {
            String(bytes, Charset.forName("GB18030"))
        }
    }

    fun toUtf8(file: File): File? {
        val bytes = runCatching { file.readBytes() }.getOrNull() ?: return null
        val decoded = decode(bytes) ?: return null
        val target = File(file.parentFile, "utf8-" + file.name)
        target.writeBytes(decoded.text.toByteArray(Charsets.UTF_8))
        return target
    }
}
