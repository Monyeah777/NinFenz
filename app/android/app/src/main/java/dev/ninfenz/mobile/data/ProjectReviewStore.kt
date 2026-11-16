package dev.ninfenz.mobile.data

import dev.ninfenz.mobile.core.Core
import dev.ninfenz.mobile.core.CoreBridge
import dev.ninfenz.mobile.model.Project
import dev.ninfenz.mobile.model.ProjectModel
import java.io.File
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonObject

sealed interface ReviewResult {
    data class Reviewed(val project: Project) : ReviewResult
    data class Failure(val code: String, val message: String, val fix: String) : ReviewResult
}

/** 本地人工评审：approved 需 reviewer+note，写 subject_digest 后 project-validate 通过才落盘。 */
class ProjectReviewStore(
    private val filesDir: File,
    private val injectedBridge: CoreBridge? = null
) {
    private fun bridge(): CoreBridge? = injectedBridge ?: runCatching { Core.bridge }.getOrNull()

    suspend fun review(
        project: Project,
        approve: Boolean,
        reviewer: String,
        note: String
    ): ReviewResult = withContext(Dispatchers.IO) {
        val who = reviewer.trim()
        val why = note.trim()
        if (who.isBlank() || why.isBlank()) {
            return@withContext ReviewResult.Failure("NF-REV-001", "评审人/意见不能为空", "填写 reviewer 与 note")
        }
        val core = bridge() ?: return@withContext ReviewResult.Failure(
            "NF-E-005", "原生核心不可用，无法写回评审", "重装原生库并运行诊断"
        )
        try {
            val file = File(File(filesDir, "projects"), project.id + ".nfproject.json")
            if (!file.isFile) return@withContext ReviewResult.Failure("NF-PCK-003", "项目文件不存在", "重新创建项目")
            var raw = Json.parseToJsonElement(file.readText(Charsets.UTF_8)).jsonObject
            val status = raw["status"]?.jsonPrimitive?.content ?: ""
            if (approve && status !in setOf("validated", "exported", "reviewed")) {
                return@withContext ReviewResult.Failure("NF-REV-002", "当前状态不可评审通过：" + status, "先完成 validate/export")
            }
            val subject = JsonObject(raw.toMutableMap().apply { remove("review") })
            val canonical = core.call("canonical", buildJsonObject {
                put("value", subject)
            })
            if (!canonical.ok) return@withContext ReviewResult.Failure("NF-E-005", "评审 subject_digest 计算失败", "检查核心 canonical")
            val digest = canonical.resultObject()?.get("digest")?.jsonPrimitive?.content
                ?: return@withContext ReviewResult.Failure("NF-E-005", "canonical 未返回 digest", "检查核心输出")

            raw = withReview(raw, approve, who, why, digest)
            if (approve) {
                raw = withHistory(raw, "review:approved", digest)
                raw = withStatus(raw, "reviewed")
            }
            val validate = core.call("project-validate", buildJsonObject { put("project", raw) })
            if (!validate.ok) {
                val e = validate.error
                return@withContext ReviewResult.Failure(
                    e?.code ?: "NF-VAL-001", e?.message ?: "评审写入校验失败", e?.fix ?: "检查 review/history/status"
                )
            }
            AtomicFiles.writeText(file, raw.toString())
            ReviewResult.Reviewed(ProjectModel.parse(raw.toString()))
        } catch (t: Throwable) {
            ReviewResult.Failure("NF-E-005", "评审写回失败：" + (t.message ?: t.javaClass.simpleName), "检查项目文件与核心桥")
        }
    }

    private fun withReview(raw: JsonObject, approve: Boolean, reviewer: String, note: String, digest: String): JsonObject {
        val next = raw.toMutableMap()
        next["review"] = buildJsonObject {
            put("state", if (approve) "approved" else "rejected")
            put("reviewer", reviewer)
            put("note", note)
            put("subject_digest", digest)
        }
        return JsonObject(next)
    }

    private fun withStatus(raw: JsonObject, status: String): JsonObject {
        val next = raw.toMutableMap()
        next["status"] = kotlinx.serialization.json.JsonPrimitive(status)
        return JsonObject(next)
    }

    private fun withHistory(raw: JsonObject, op: String, digest: String): JsonObject {
        val history = raw["history"] as? kotlinx.serialization.json.JsonArray
        val next = raw.toMutableMap()
        next["history"] = buildJsonArray {
            history?.forEach { add(it) }
            add(buildJsonObject {
                put("op", op)
                put("digest", digest)
            })
        }
        return JsonObject(next)
    }
}
