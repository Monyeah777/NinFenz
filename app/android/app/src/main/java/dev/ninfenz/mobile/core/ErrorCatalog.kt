package dev.ninfenz.mobile.core

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject

/** 错误码登记项（字段同 app/schema/error_codes.json）。 */
data class ErrorCodeEntry(
    val code: String,
    val severity: String,
    val exit: Int,
    val message: String,
    val fix: String
)

/**
 * 错误码登记表：构建时从 app/schema/error_codes.json 复制为 Java resource（单一真源，不散落字面量）。
 * 读取失败时返回空表并在诊断页明确显示「登记表未打包」，不伪造。
 */
object ErrorCatalog {
    private const val RESOURCE = "schema/error_codes.json"

    private val entries: List<ErrorCodeEntry> by lazy { load() }

    fun all(): List<ErrorCodeEntry> = entries
    fun find(code: String): ErrorCodeEntry? = entries.firstOrNull { it.code == code }
    fun isLoaded(): Boolean = entries.isNotEmpty()

    private fun load(): List<ErrorCodeEntry> {
        val stream = ErrorCatalog::class.java.classLoader?.getResourceAsStream(RESOURCE) ?: return emptyList()
        val text = stream.bufferedReader(Charsets.UTF_8).use { it.readText() }
        val root = try {
            Json.parseToJsonElement(text) as? JsonObject
        } catch (t: Throwable) {
            null
        } ?: return emptyList()
        val codes = root["codes"] as? JsonArray ?: return emptyList()
        return codes.mapNotNull { el ->
            val o = el as? JsonObject ?: return@mapNotNull null
            val code = J.optString(o, "code") ?: return@mapNotNull null
            ErrorCodeEntry(
                code = code,
                severity = J.optString(o, "severity") ?: "error",
                exit = J.optInt(o, "exit") ?: 2,
                message = J.optString(o, "message") ?: "",
                fix = J.optString(o, "fix") ?: ""
            )
        }
    }
}
