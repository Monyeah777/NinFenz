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
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonObject

sealed interface StatusAdvanceResult {
    data class Advanced(val project: Project, val from: ProjectStatus, val to: ProjectStatus) : StatusAdvanceResult
    data class Failure(val code: String, val message: String, val fix: String) : StatusAdvanceResult
}

/** 装配产物：进入 assembled 时写入项目 refs.assembly（project-validate 要求）。 */
data class AssemblyArtifact(
    val bytes: ByteArray,
    val fileName: String = "assembly.md",
    val id: String = "assembly",
    val version: String = "1.0.0"
)

/**
 * 项目状态写回（CONTRACT §5.10）：只能相邻前进；每步追加 history；
 * 进入 assembled 时必须提供 assembly 引用；core project-validate 通过后才原子写盘。
 */
class ProjectStatusStore(
    private val filesDir: File,
    private val injectedBridge: CoreBridge? = null
) {
    private fun bridge(): CoreBridge? = injectedBridge ?: runCatching { Core.bridge }.getOrNull()

    private sealed interface StepOutcome

    private data class StepApplied(val raw: JsonObject) : StepOutcome

    private data class StepFailed(val failure: StatusAdvanceResult.Failure) : StepOutcome

    suspend fun advance(
        project: Project,
        target: ProjectStatus,
        assembly: AssemblyArtifact? = null,
        allowAuditSkip: Boolean = false
    ): StatusAdvanceResult = withContext(Dispatchers.IO) {
        val core = bridge() ?: return@withContext StatusAdvanceResult.Failure(
            "NF-E-005", "原生核心不可用，无法写回项目状态", "重装原生库并运行诊断"
        )
        try {
            val file = File(File(filesDir, "projects"), project.id + ".nfproject.json")
            if (!file.isFile) return@withContext StatusAdvanceResult.Failure("NF-PCK-003", "项目文件不存在", "重新创建项目")
            var raw = Json.parseToJsonElement(file.readText(Charsets.UTF_8)).jsonObject
            var current = ProjectStatus.fromWire(raw["status"]?.jsonPrimitive?.content ?: "")
                ?: return@withContext StatusAdvanceResult.Failure("NF-VAL-001", "项目 status 无法识别", "检查项目文件")
            if (current == target) {
                return@withContext StatusAdvanceResult.Advanced(ProjectModel.parse(raw.toString()), current, current)
            }
            val from = current
            val forward = forwardPath(current, target, allowAuditSkip)
            val stuckAt = forward.second
            if (stuckAt != null) {
                return@withContext StatusAdvanceResult.Failure(
                    "NF-VAL-001", "无法从 " + stuckAt.wire + " 前进到 " + target.wire, "检查项目状态机"
                )
            }
            for (step in forward.first) {
                val outcome = applyStep(core, raw, project.id, current, step, assembly)
                if (outcome is StepFailed) return@withContext outcome.failure
                raw = (outcome as StepApplied).raw
                current = step
            }
            val validate = core.call("project-validate", buildJsonObject { put("project", raw) })
            if (!validate.ok) {
                val e = validate.error
                return@withContext StatusAdvanceResult.Failure(
                    e?.code ?: "NF-VAL-001", e?.message ?: "项目状态校验失败", e?.fix ?: "检查 refs/history/status"
                )
            }
            atomicWrite(file, raw.toString())
            StatusAdvanceResult.Advanced(ProjectModel.parse(raw.toString()), from, target)
        } catch (t: Throwable) {
            StatusAdvanceResult.Failure("NF-E-005", "状态写回失败：" + (t.message ?: t.javaClass.simpleName), "检查项目文件与核心桥")
        }
    }

    private fun forwardPath(
        current: ProjectStatus,
        target: ProjectStatus,
        allowAuditSkip: Boolean
    ): Pair<List<ProjectStatus>, ProjectStatus?> {
        val path = mutableListOf<ProjectStatus>()
        if (allowAuditSkip && target == ProjectStatus.EXPORTED && current == ProjectStatus.ASSEMBLED) {
            path.add(ProjectStatus.EXPORTED)
            return path to null
        }
        var cursor = current
        while (cursor != target) {
            val next = ProjectModel.next(cursor) ?: return path to cursor
            path.add(next)
            cursor = next
        }
        return path to null
    }

    private suspend fun applyStep(
        core: CoreBridge,
        raw: JsonObject,
        projectId: String,
        from: ProjectStatus,
        step: ProjectStatus,
        assembly: AssemblyArtifact?
    ): StepOutcome {
        var next = raw
        if (step == ProjectStatus.ASSEMBLED && raw["refs"]?.jsonObject?.get("assembly") == null) {
            val artifact = assembly ?: return StepFailed(
                StatusAdvanceResult.Failure(
                    "NF-VAL-001",
                    "进入 assembled 前必须提供 assembly 引用",
                    "先装配并写入 assembly.md 再写回状态"
                )
            )
            next = withAssembly(core, raw, projectId, artifact)
                ?: return StepFailed(StatusAdvanceResult.Failure("NF-E-005", "assembly 摘要计算失败", "检查核心 canonical"))
        }
        if (step == ProjectStatus.EXPORTED) {
            next = withHistory(next, "export", sha256(("export:" + projectId).toByteArray(Charsets.UTF_8)))
        }
        return StepApplied(withStatus(next, from, step))
    }

    private suspend fun withAssembly(core: CoreBridge, raw: JsonObject, projectId: String, artifact: AssemblyArtifact): JsonObject? {
        val relative = "authoring/" + artifact.fileName
        val target = File(File(filesDir, "projects/" + projectId), relative)
        target.parentFile?.mkdirs()
        target.writeBytes(artifact.bytes)
        val sha = sha256(artifact.bytes)
        val canonical = core.call("canonical", buildJsonObject {
            put("value", buildJsonObject { put("markdown", artifact.bytes.toString(Charsets.UTF_8)) })
        })
        if (!canonical.ok) return null
        val digest = canonical.resultObject()?.get("digest")?.jsonPrimitive?.content ?: return null
        val refs = raw["refs"]?.jsonObject ?: emptyMap<String, kotlinx.serialization.json.JsonElement>()
        val newRefs = buildJsonObject {
            for ((key, value) in refs) {
                if (key == "assembly") {
                    putJsonObject("assembly") {
                        put("id", artifact.id)
                        put("version", artifact.version)
                        put("digest", digest)
                        put("path", relative)
                        put("sha256", sha)
                    }
                } else {
                    put(key, value)
                }
            }
            if (refs["assembly"] == null) {
                putJsonObject("assembly") {
                    put("id", artifact.id)
                    put("version", artifact.version)
                    put("digest", digest)
                    put("path", relative)
                    put("sha256", sha)
                }
            }
        }
        return buildJsonObject {
            for ((key, value) in raw) {
                if (key == "refs") put("refs", newRefs) else put(key, value)
            }
        }
    }


    private fun withHistory(raw: JsonObject, op: String, digest: String): JsonObject {
        val history = raw["history"]?.jsonArray ?: JsonArray(emptyList())
        val newHistory = buildJsonArray {
            for (entry in history) add(entry)
            add(buildJsonObject {
                put("op", op)
                put("digest", digest)
            })
        }
        return buildJsonObject {
            for ((key, value) in raw) {
                if (key == "history") put("history", newHistory) else put(key, value)
            }
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

    private fun atomicWrite(target: File, text: String) = AtomicFiles.writeText(target, text)

    private fun sha256(bytes: ByteArray): String =
        MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
}
