package dev.ninfenz.mobile.data

import dev.ninfenz.mobile.core.Core
import dev.ninfenz.mobile.core.CoreBridge
import dev.ninfenz.mobile.core.CoreResponse
import dev.ninfenz.mobile.model.Project
import dev.ninfenz.mobile.model.ProjectModel
import java.io.File
import java.security.MessageDigest
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonObject

sealed interface CreateProjectResult {
    data class Success(val project: Project, val file: File) : CreateProjectResult
    data class Failure(val code: String, val message: String, val fix: String) : CreateProjectResult
}

/** nf-project/1 构造参数对象（参数对象化，避免超长参数表）。 */
data class ProjectBuildSpec(
    val id: String,
    val title: String,
    val packId: String,
    val packVersion: String,
    val packTree: String,
    val protocolId: String,
    val protocolVersion: String,
    val protocolDigest: String,
    val graphId: String,
    val graphVersion: String,
    val graphDigest: String,
    val graphSha256: String,
    val specId: String,
    val specVersion: String,
    val specDigest: String,
    val specSha256: String
)

/** 纯构造器（可 JVM 单测）：只负责 nf-project/1 文档形状，摘要由调用方传入。 */
object ProjectFactory {
    fun build(spec: ProjectBuildSpec): JsonObject = with(spec) {
        buildJsonObject {
            put("schema", "nf-project/1")
            put("id", id)
            put("title", title)
            putJsonObject("refs") {
                putJsonObject("base_pack") {
                    put("id", packId)
                    put("version", packVersion)
                    put("tree", packTree)
                }
                putJsonObject("protocol") {
                    put("id", protocolId)
                    put("version", protocolVersion)
                    put("digest", protocolDigest)
                }
                putJsonObject("graph") {
                    put("id", graphId)
                    put("version", graphVersion)
                    put("digest", graphDigest)
                    put("path", "pack/pipeline/main.nfg.json")
                    put("sha256", graphSha256)
                }
                putJsonObject("spec") {
                    put("id", specId)
                    put("version", specVersion)
                    put("digest", specDigest)
                    put("path", "pack/spec/main.nfspec.json")
                    put("sha256", specSha256)
                }
            }
            put("status", "draft")
            putJsonObject("review") { put("state", "none") }
            put("history", buildJsonArray {})
        }
    }
}

/**
 * 从已安装 Pack 创建项目：读 protocol/graph/spec → core canonical 摘要 → 构造 nf-project →
 * core project-validate（fail-closed）→ 原子写 projects/<id>.nfproject.json。
 * 核心不可用时返回 NF-E-005，不写半成品。
 */
private data class PackArtifactInput(
    val pack: PackEntry,
    val title: String,
    val projectId: String,
    val protocol: JsonObject,
    val graph: JsonObject,
    val spec: JsonObject,
    val protocolDigest: String,
    val graphDigest: String,
    val specDigest: String,
    val graphFile: File,
    val specFile: File
)

class ProjectCreator(
    private val filesDir: File,
    private val injectedBridge: CoreBridge? = null
) {
    private fun bridge(): CoreBridge? = injectedBridge ?: runCatching { Core.bridge }.getOrNull()

    suspend fun create(pack: PackEntry, title: String, preferredId: String? = null): CreateProjectResult =
        withContext(Dispatchers.IO) {
            val core = bridge() ?: return@withContext CreateProjectResult.Failure(
                "NF-E-005",
                "原生核心不可用，无法创建项目",
                "重装原生库并运行诊断；项目创建需要 canonical/project-validate"
            )
            try {
                val protocolFile = File(pack.dir, "protocol/nf-protocol-pack.json")
                val graphFile = File(pack.dir, "pipeline/main.nfg.json")
                val specFile = File(pack.dir, "spec/main.nfspec.json")
                if (!protocolFile.isFile || !graphFile.isFile || !specFile.isFile) {
                    return@withContext CreateProjectResult.Failure(
                        "NF-PCK-002",
                        "Pack 缺少 protocol/pipeline/spec 文件，无法创建项目",
                        "确认示例 Pack 完整，或重新载入示例"
                    )
                }
                val protocol = Json.parseToJsonElement(protocolFile.readText(Charsets.UTF_8)).jsonObject
                val graph = Json.parseToJsonElement(graphFile.readText(Charsets.UTF_8)).jsonObject
                val spec = Json.parseToJsonElement(specFile.readText(Charsets.UTF_8)).jsonObject

                val protocolDigest = canonicalDigest(core, protocol) ?: return@withContext coreFailure()
                val graphDigest = canonicalDigest(core, graph) ?: return@withContext coreFailure()
                val specDigest = canonicalDigest(core, spec) ?: return@withContext coreFailure()

                val projectId = uniqueId(preferredId ?: slug(title))
                val document = newProjectJson(
                    PackArtifactInput(
                        pack = pack,
                        title = title,
                        projectId = projectId,
                        protocol = protocol,
                        graph = graph,
                        spec = spec,
                        protocolDigest = protocolDigest,
                        graphDigest = graphDigest,
                        specDigest = specDigest,
                        graphFile = graphFile,
                        specFile = specFile
                    )
                )
                validateProject(core, document)?.let { return@withContext it }

                val projectsDir = File(filesDir, "projects").apply { mkdirs() }
                val target = File(projectsDir, projectId + ".nfproject.json")
                atomicWrite(target, document.toString())
                val parsed = ProjectModel.parse(document.toString())
                CreateProjectResult.Success(parsed, target)
            } catch (t: Throwable) {
                CreateProjectResult.Failure(
                    "NF-E-005",
                    "创建项目失败：" + (t.message ?: t.javaClass.simpleName),
                    "检查核心桥与 Pack 完整性；诊断见设置页"
                )
            }
        }

    private fun newProjectJson(input: PackArtifactInput): JsonObject = with(input) {
        ProjectFactory.build(
            ProjectBuildSpec(
                id = projectId,
                title = title.ifBlank { "未命名项目" },
                packId = pack.id,
                packVersion = pack.version,
                packTree = pack.tree,
                protocolId = text(protocol, "id"),
                protocolVersion = text(protocol, "version"),
                protocolDigest = protocolDigest,
                graphId = text(graph, "id"),
                graphVersion = text(graph, "version"),
                graphDigest = graphDigest,
                graphSha256 = sha256(graphFile.readBytes()),
                specId = text(spec, "id"),
                specVersion = text(spec, "version"),
                specDigest = specDigest,
                specSha256 = sha256(specFile.readBytes())
            )
        )
    }

    private suspend fun validateProject(core: CoreBridge, document: JsonObject): CreateProjectResult.Failure? {
        val validate = core.call("project-validate", buildJsonObject { put("project", document) })
        if (!validate.ok) {
            val error = validate.error
            return CreateProjectResult.Failure(
                error?.code ?: "NF-VAL-001",
                error?.message ?: "项目校验失败",
                error?.fix ?: "检查 Pack 引用与 schema"
            )
        }
        val verdict = validate.resultObject()?.get("verdict")?.jsonPrimitive?.content
        if (verdict != null && verdict == "fail") {
            return CreateProjectResult.Failure(
                "NF-VAL-001", "项目校验未通过", "查看校验报告并修复引用"
            )
        }
        return null
    }

    private suspend fun canonicalDigest(core: CoreBridge, obj: JsonObject): String? {
        val response: CoreResponse = try {
            core.call("canonical", buildJsonObject { put("value", obj) })
        } catch (t: Throwable) {
            return null
        }
        if (!response.ok) return null
        return response.resultObject()?.get("digest")?.jsonPrimitive?.content
    }

    private fun coreFailure() = CreateProjectResult.Failure(
        "NF-E-005",
        "核心不可用，无法计算引用摘要",
        "重装原生库或运行诊断；示例项目需要核心 canonical/project-validate"
    )

    private fun uniqueId(base: String): String {
        val projectsDir = File(filesDir, "projects")
        var candidate = base
        var index = 2
        while (File(projectsDir, candidate + ".nfproject.json").exists()) {
            candidate = base + "-" + index
            index += 1
        }
        return candidate
    }

    private fun slug(title: String): String {
        val normalized = title.lowercase()
            .replace(Regex("[^a-z0-9]+"), "-")
            .trim('-')
            .ifBlank { "project" }
        val withLetter = if (normalized.first().isLetter()) normalized else "p-" + normalized
        return withLetter.take(60)
    }

    private fun text(obj: JsonObject, key: String): String = obj[key]?.jsonPrimitive?.content ?: ""

    private fun sha256(bytes: ByteArray): String {
        val digest = MessageDigest.getInstance("SHA-256").digest(bytes)
        return digest.joinToString("") { byte -> "%02x".format(byte) }
    }

    private fun atomicWrite(target: File, text: String) = AtomicFiles.writeText(target, text)
}
