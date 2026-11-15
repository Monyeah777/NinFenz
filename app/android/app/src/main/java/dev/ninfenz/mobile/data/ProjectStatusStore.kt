package dev.ninfenz.mobile.data

import dev.ninfenz.mobile.core.Core
import dev.ninfenz.mobile.core.CoreBridge
import dev.ninfenz.mobile.model.Project
import dev.ninfenz.mobile.model.ProjectModel
import dev.ninfenz.mobile.model.ProjectStatus
import java.io.File
import java.security.MessageDigest
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.put

sealed interface StatusAdvanceResult {
    data class Advanced(val project: Project, val from: ProjectStatus, val to: ProjectStatus) : StatusAdvanceResult
    data class Failure(val code: String, val message: String, val fix: String) : StatusAdvanceResult
}

/**
 * 项目状态写回（CONTRACT §5.10）：只能相邻前进；每步追加 history；
 * core project-validate 通过后才原子写盘。回退仍需显式 force（本类不提供隐式回退）。
 */
class ProjectStatusStore(
    private val filesDir: File,
    private val injectedBridge: CoreBridge? = null
) {
    private fun bridge(): CoreBridge? = injectedBridge ?: runCatching { Core.bridge }.getOrNull()

    suspend fun advance(project: Project, target: ProjectStatus): StatusAdvanceResult = withContext(Dispatchers.IO) {
        if (project.status == target) {
            return@withContext StatusAdvanceResult.Advanced(project, project.status, project.status)
        }
        var cursor = project.status
        val path = mutableListOf<ProjectStatus>()
        while (cursor != target) {
            val next = ProjectModel.next(cursor)
                ?: return@withContext StatusAdvanceResult.Failure("NF-VAL-001", "无法从 " + cursor.wire + " 前进到 " + target.wire, "检查项目状态机")
            path.add(next)
            cursor = next
        }
        val core = bridge() ?: return@withContext StatusAdvanceResult.Failure(
            "NF-E-005", "原生核心不可用，无法写回项目状态", "重装原生库并运行诊断"
        )
        try {
            val file = File(File(filesDir, "projects"), project.id + ".nfproject.json")
            if (!file.isFile) return@withContext StatusAdvanceResult.Failure("NF-PCK-003", "项目文件不存在", "重新创建项目")
            var raw = Json.parseToJsonElement(file.readText(Charsets.UTF_8)).jsonObject
            var current = project.status
            for (step in path) {
                raw = withStatus(raw, current, step)
                current = step
            }
            val validate = core.call("project-validate", buildJsonObject { put("project", raw) })
            if (!validate.ok) {
                val e = validate.error
                return@withContext StatusAdvanceResult.Failure(
                    e?.code ?: "NF-VAL-001", e?.message ?: "项目状态校验失败", e?.fix ?: "检查 history/status"
                )
            }
            atomicWrite(file, raw.toString())
            StatusAdvanceResult.Advanced(ProjectModel.parse(raw.toString()), project.status, target)
        } catch (t: Throwable) {
            StatusAdvanceResult.Failure("NF-E-005", "状态写回失败：" + (t.message ?: t.javaClass.simpleName), "检查项目文件与核心桥")
        }
    }

    private fun withStatus(raw: JsonObject, from: ProjectStatus, to: ProjectStatus): JsonObject {
        val history = raw["history"]?.jsonArray ?: JsonArray(emptyList())
        val digest = sha256((from.wire + "->" + to.wire).toByteArray(Charsets.UTF_8))
        val newHistory = buildJsonArray {
            for (entry in history) add(entry)
            add(buildJsonObject {
                put("op", "status:" + from.wire + "->" + to.wire)
                put("digest", digest)
            })
        }
        return buildJsonObject {
            for ((key, value) in raw) {
                when (key) {
                    "status" -> put("status", to.wire)
                    "history" -> put("history", newHistory)
                    else -> put(key, value)
                }
            }
        }
    }

    private fun atomicWrite(target: File, text: String) {
        val temp = File(target.parentFile, target.name + ".tmp")
        temp.writeText(text, Charsets.UTF_8)
        if (!temp.renameTo(target)) {
            target.writeText(text, Charsets.UTF_8)
            temp.delete()
        }
    }

    private fun sha256(bytes: ByteArray): String =
        MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
}
