package dev.ninfenz.mobile.data

import java.io.File
import java.security.MessageDigest
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.long

/** 导出产物校验：文件存在、bytes/sha256 与 manifest 一致。 */
object ExportVerifier {
    data class Result(val ok: Boolean, val message: String)

    fun verify(file: File, manifestJson: String?): Result {
        if (!file.isFile) return Result(false, "导出文件不存在：" + file.name)
        if (manifestJson.isNullOrBlank()) return Result(false, "缺少导出 manifest")
        val manifest = try {
            Json.parseToJsonElement(manifestJson).jsonObject
        } catch (t: Throwable) {
            return Result(false, "manifest 不是合法 JSON")
        }
        val files = manifest["files"]?.jsonArray ?: return Result(false, "manifest 缺少 files")
        val entry = files.mapNotNull { it as? JsonObject }
            .firstOrNull { it["name"]?.jsonPrimitive?.content == file.name }
            ?: return Result(false, "manifest 未登记 " + file.name)
        val expectedBytes = entry["bytes"]?.jsonPrimitive?.long
        if (expectedBytes != null && expectedBytes != file.length()) {
            return Result(false, "字节数不一致：manifest=" + expectedBytes + "，实际=" + file.length())
        }
        val expectedSha = entry["sha256"]?.jsonPrimitive?.content
        if (expectedSha.isNullOrBlank()) return Result(false, "manifest 缺 sha256")
        val actual = sha256(file)
        if (actual != expectedSha) return Result(false, "sha256 不一致")
        return Result(true, "导出校验通过：" + file.name + " · " + actual.take(12))
    }

    private fun sha256(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { input ->
            val buffer = ByteArray(8192)
            while (true) {
                val n = input.read(buffer)
                if (n < 0) break
                digest.update(buffer, 0, n)
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }
}
