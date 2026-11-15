package dev.ninfenz.mobile.core

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.longOrNull

/**
 * 模型解析错误：code 取自 app/schema/error_codes.json（单一真源），
 * pointer 用 RFC 6901 JSON Pointer（CLI.md §2）。
 */
class ModelException(
    val code: String,
    val pointer: String,
    val detail: String,
    val fix: String
) : Exception(code + " @ " + pointer + ": " + detail)

/** 严格 JSON 读取助手：缺字段/类型错一律 fail-closed（CONTRACT.md §3/§7）。 */
object J {

    fun parseObject(text: String, what: String): JsonObject {
        val el: JsonElement = try {
            Json.parseToJsonElement(text)
        } catch (t: Throwable) {
            throw ModelException(
                "NF-E-002", "#", what + " 不是合法 JSON：" + (t.message ?: t.javaClass.simpleName),
                "确认输入是 UTF-8 JSON（无 BOM）；可用 nf-app-core canonical 复核"
            )
        }
        return el as? JsonObject ?: throw ModelException(
            "NF-E-002", "#", what + " 顶层必须是 JSON 对象", "按 app/schema 对应格式修正"
        )
    }

    fun schema(o: JsonObject, expected: String) {
        val got = optString(o, "schema")
        if (got != expected) {
            throw ModelException(
                "NF-E-001", "/schema", "期望 " + expected + "，实际 " + (got ?: "缺失"),
                "升级 APP 或改用 " + expected + " 文件（未知版本 fail-closed）"
            )
        }
    }

    fun child(o: JsonObject, key: String, ptr: String): JsonObject {
        val el = o[key] ?: throw ModelException("NF-E-002", ptr + "/" + key, "必填对象缺失", "按 schema 补齐")
        return el as? JsonObject ?: throw ModelException("NF-E-002", ptr + "/" + key, "应为对象", "按 schema 修正类型")
    }

    fun optChild(o: JsonObject, key: String): JsonObject? = o[key] as? JsonObject

    fun string(o: JsonObject, key: String, ptr: String): String {
        val p = o[key] as? JsonPrimitive
        if (p == null || !p.isString) {
            throw ModelException("NF-E-002", ptr + "/" + key, "必填字符串缺失或类型错", "按 schema 修正")
        }
        return p.content
    }

    fun optString(o: JsonObject, key: String): String? {
        val p = o[key] as? JsonPrimitive ?: return null
        return if (p.isString) p.content else null
    }

    fun int(o: JsonObject, key: String, ptr: String): Int {
        val p = o[key] as? JsonPrimitive
            ?: throw ModelException("NF-E-002", ptr + "/" + key, "必填整数缺失", "按 schema 修正")
        return p.intOrNull ?: throw ModelException(
            "NF-E-006", ptr + "/" + key, "应为整数（canonical 禁浮点）", "改用整数"
        )
    }

    fun optInt(o: JsonObject, key: String): Int? = (o[key] as? JsonPrimitive)?.intOrNull

    fun optLong(o: JsonObject, key: String): Long? = (o[key] as? JsonPrimitive)?.longOrNull

    fun bool(o: JsonObject, key: String, ptr: String): Boolean {
        val p = o[key] as? JsonPrimitive
            ?: throw ModelException("NF-E-002", ptr + "/" + key, "必填布尔缺失", "按 schema 修正")
        return p.booleanOrNull ?: throw ModelException("NF-E-002", ptr + "/" + key, "应为布尔", "改用 true/false")
    }

    fun optBool(o: JsonObject, key: String): Boolean? = (o[key] as? JsonPrimitive)?.booleanOrNull

    fun array(o: JsonObject, key: String, ptr: String): List<JsonElement> {
        val a = o[key] as? JsonArray
            ?: throw ModelException("NF-E-002", ptr + "/" + key, "必填数组缺失", "按 schema 修正")
        return a.toList()
    }

    fun optArray(o: JsonObject, key: String): List<JsonElement> = (o[key] as? JsonArray)?.toList() ?: emptyList()

    fun stringList(o: JsonObject, key: String, ptr: String): List<String> =
        array(o, key, ptr).mapIndexed { i, el ->
            val p = el as? JsonPrimitive
            if (p == null || !p.isString) {
                throw ModelException("NF-E-002", ptr + "/" + key + "/" + i, "应为字符串", "按 schema 修正")
            }
            p.content
        }

    fun optStringList(o: JsonObject, key: String): List<String> =
        optArray(o, key).mapNotNull { el -> (el as? JsonPrimitive)?.takeIf { it.isString }?.content }
}
