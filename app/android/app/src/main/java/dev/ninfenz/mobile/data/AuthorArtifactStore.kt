package dev.ninfenz.mobile.data

import dev.ninfenz.mobile.core.Core
import dev.ninfenz.mobile.core.CoreBridge
import dev.ninfenz.mobile.model.MdSpec
import dev.ninfenz.mobile.model.PipelineGraph
import dev.ninfenz.mobile.model.Project
import dev.ninfenz.mobile.model.ProjectModel
import dev.ninfenz.mobile.model.ProjectStatus
import dev.ninfenz.mobile.model.SpecModel
import dev.ninfenz.mobile.model.GraphModel
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

private data class AuthorRefUpdate(
    val kind: String,
    val id: String,
    val version: String,
    val digest: String,
    val relative: String,
    val sha: String
)

sealed interface SaveArtifactResult {
    data class Saved(val project: Project, val path: String, val sha256: String) : SaveArtifactResult
    data class Failure(val code: String, val message: String, val fix: String) : SaveArtifactResult
}

/**
 * 作者态管线/规格保存（C-06）：写 projects/<id>/authoring/{graph,spec}.json，
 * 更新 project.refs 的 path/sha256/digest，追加 history，core project-validate 后原子写。
 * 不修改基础 Pack。
 */
class AuthorArtifactStore(
    private val filesDir: File,
    private val injectedBridge: CoreBridge? = null
) {
    private fun bridge(): CoreBridge? = injectedBridge ?: runCatching { Core.bridge }.getOrNull()

    suspend fun saveGraph(project: Project, graph: PipelineGraph): SaveArtifactResult {
        return save(project, "graph", GraphModel.toJson(graph), graph.id, graph.version)
    }

    suspend fun saveSpec(project: Project, spec: MdSpec): SaveArtifactResult {
        return save(project, "spec", SpecModel.toJson(spec), spec.id, spec.version)
    }

    private suspend fun save(project: Project, kind: String, json: JsonObject, id: String, version: String): SaveArtifactResult =
        withContext(Dispatchers.IO) {
            val core = bridge() ?: return@withContext SaveArtifactResult.Failure(
                "NF-E-005", "原生核心不可用，无法保存作者产物", "重装原生库并运行诊断"
            )
            try {
                val canonical = core.call("canonical", buildJsonObject { put("value", json) })
                if (!canonical.ok) {
                    val e = canonical.error
                    return@withContext SaveArtifactResult.Failure(
                        e?.code ?: "NF-E-005", e?.message ?: "canonical 失败", e?.fix ?: "检查核心"
                    )
                }
                val digest = canonical.resultObject()?.get("digest")?.jsonPrimitive?.content
                    ?: return@withContext SaveArtifactResult.Failure("NF-E-005", "canonical 未返回 digest", "检查核心输出")

                val projectFile = File(File(filesDir, "projects"), project.id + ".nfproject.json")
                if (!projectFile.isFile) return@withContext SaveArtifactResult.Failure("NF-PCK-003", "项目文件不存在", "重新创建项目")
                val relative = "authoring/" + kind + ".json"
                val target = File(File(filesDir, "projects/" + project.id), relative)
                target.parentFile?.mkdirs()
                val bytes = json.toString().toByteArray(Charsets.UTF_8)
                atomicWrite(target, bytes)
                val sha = sha256(bytes)

                val raw = Json.parseToJsonElement(projectFile.readText(Charsets.UTF_8)).jsonObject
                val updated = updatedProject(raw, AuthorRefUpdate(kind, id, version, digest, relative, sha))
                val validate = core.call("project-validate", buildJsonObject { put("project", updated) })
                if (!validate.ok) {
                    val e = validate.error
                    return@withContext SaveArtifactResult.Failure(
                        e?.code ?: "NF-VAL-001", e?.message ?: "项目校验失败", e?.fix ?: "检查项目 refs/history"
                    )
                }
                atomicWrite(projectFile, updated.toString().toByteArray(Charsets.UTF_8))
                SaveArtifactResult.Saved(ProjectModel.parse(updated.toString()), relative, sha)
            } catch (t: Throwable) {
                SaveArtifactResult.Failure("NF-E-005", "保存失败：" + (t.message ?: t.javaClass.simpleName), "检查项目文件与核心桥")
            }
        }

    private fun updatedProject(raw: JsonObject, ref: AuthorRefUpdate): JsonObject {
        val refs = raw["refs"]!!.jsonObject
        val newRefs = buildJsonObject {
            for ((key, value) in refs) {
                if (key == ref.kind) {
                    putJsonObject(ref.kind) {
                        put("id", ref.id)
                        put("version", ref.version)
                        put("digest", ref.digest)
                        put("path", ref.relative)
                        put("sha256", ref.sha)
                    }
                } else {
                    put(key, value)
                }
            }
        }
        val status = raw["status"]?.jsonPrimitive?.content
        val newStatus = if (status == ProjectStatus.DRAFT.wire) ProjectStatus.AUTHORING.wire else status
        val history = raw["history"]?.jsonArray ?: JsonArray(emptyList())
        val newHistory = buildJsonArray {
            for (entry in history) add(entry)
            add(buildJsonObject {
                put("op", ref.kind + ":save")
                put("digest", ref.sha)
            })
        }
        return buildJsonObject {
            for ((key, value) in raw) {
                when (key) {
                    "refs" -> put("refs", newRefs)
                    "status" -> put("status", newStatus)
                    "history" -> put("history", newHistory)
                    else -> put(key, value)
                }
            }
        }
    }

    private fun atomicWrite(target: File, bytes: ByteArray) = AtomicFiles.writeBytes(target, bytes)

    private fun sha256(bytes: ByteArray): String =
        MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
}
