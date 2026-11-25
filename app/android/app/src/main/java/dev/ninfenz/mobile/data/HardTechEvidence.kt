package dev.ninfenz.mobile.data

import android.content.Context
import dev.ninfenz.mobile.core.Core
import java.io.File
import java.security.SecureRandom
import java.time.Instant
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

/**
 * 交付证据包：把一次导出接到核心的 SDIR → build-plan → evidence → pack 链路。
 * 设备密钥只用于本地 Ed25519 签名；不是 CA/TSA，也不冒充身份认证。
 */
object HardTechEvidence {
    data class Result(val ok: Boolean, val message: String, val packageFile: File?)

    private const val PREFS = "nf_hardtech"
    private const val SEED = "evidence_seed"

    private fun mimeOf(format: String): String = when (format) {
        "md" -> "text/markdown"
        "html" -> "text/html"
        "epub" -> "application/epub+zip"
        "docx" -> "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        "json" -> "application/json"
        else -> "application/octet-stream"
    }

    private fun seed(context: Context): String {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        prefs.getString(SEED, null)?.let { return it }
        val bytes = ByteArray(32)
        SecureRandom().nextBytes(bytes)
        val hex = bytes.joinToString("") { "%02x".format(it) }
        prefs.edit().putString(SEED, hex).apply()
        return hex
    }

    private fun fail(message: String) = Result(false, message, null)

    suspend fun pack(context: Context, markdown: String, artifact: File): Result {
        if (!artifact.isFile) return fail("导出文件不存在")
        val format = artifact.extension.lowercase()
        if (format !in setOf("md", "html", "epub", "docx", "json")) {
            return fail("该格式暂不支持证据包：$format")
        }
        val bridge = runCatching { Core.bridge }.getOrNull() ?: return fail("共享核心不可用")
        val at = Instant.now().toString()
        val source = buildJsonObject {
            put("name", artifact.name)
            put("mime", mimeOf(format))
        }
        val imported = bridge.call(
            "sdir-import",
            buildJsonObject {
                put("markdown", markdown)
                put("source", source)
                put("created_at", at)
                put("lang", "zh")
            }
        )
        if (!imported.ok) return fail(imported.error?.message ?: "SDIR 导入失败")
        val sdir = imported.resultObject() ?: return fail("SDIR 结果为空")
        val planned = bridge.call(
            "build-plan",
            buildJsonObject {
                put("sdir", sdir)
                put("locale", "zh")
                put(
                    "outputs",
                    buildJsonArray {
                        add(buildJsonObject {
                            put("path", artifact.name)
                            put("format", format)
                        })
                    }
                )
            }
        )
        if (!planned.ok) return fail(planned.error?.message ?: "构建计划失败")
        val graph = planned.resultObject() ?: return fail("构建计划为空")
        val created = bridge.call(
            "evidence-create",
            buildJsonObject {
                put("artifact_path", artifact.absolutePath)
                put("sdir", sdir)
                put("graph", graph)
                put("created_at", at)
                put("private_key", seed(context))
                put("profile", "accessible")
            }
        )
        if (!created.ok) return fail(created.error?.message ?: "证据生成失败")
        val evidence = created.resultObject() ?: return fail("证据为空")
        val target = File(artifact.parentFile, artifact.name + ".nfpkg")
        val packed = bridge.call(
            "evidence-pack",
            buildJsonObject {
                put("artifact_path", artifact.absolutePath)
                put("evidence", evidence)
                put("out_path", target.absolutePath)
                put("version", 1)
            }
        )
        if (!packed.ok) return fail(packed.error?.message ?: "证据打包失败")
        val verified = bridge.call(
            "evidence-verify-package",
            buildJsonObject { put("package_path", target.absolutePath) }
        )
        if (!verified.ok) return fail(verified.error?.message ?: "证据包自验失败")
        return Result(true, "证据包已生成：" + target.name, target)
    }
}
