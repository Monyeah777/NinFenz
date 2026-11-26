package dev.ninfenz.mobile.data

import dev.ninfenz.mobile.core.J
import dev.ninfenz.mobile.model.Project
import java.io.File
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json

/**
 * 从模板候选一键建项目：先用 Pack 的 protocol/graph 建基础项目，再把候选 spec 写成
 * authoring/spec-override.json；不复制 Pack 内容，不改 nf-project/1 的引用形状。
 */
class TemplateProjectCreator(private val filesDir: File) {
    suspend fun create(pack: PackEntry, title: String, candidate: File): CreateProjectResult =
        withContext(Dispatchers.IO) {
            if (!candidate.isFile) {
                return@withContext CreateProjectResult.Failure(
                    "NF-PRJ-001",
                    "模板候选不存在",
                    "重新导入模板并保存候选"
                )
            }
            val valid = runCatching {
                J.parseObject(candidate.readText(Charsets.UTF_8), "nf-md-spec/1")
            }.getOrElse {
                return@withContext CreateProjectResult.Failure(
                    "NF-PRJ-001",
                    "模板候选不是合法 JSON：" + (it.message ?: it.javaClass.simpleName),
                    "重新保存模板候选"
                )
            }
            if (valid["schema"]?.toString()?.trim('"') != "nf-md-spec/1") {
                return@withContext CreateProjectResult.Failure(
                    "NF-PRJ-001",
                    "模板候选不是 nf-md-spec/1",
                    "选择由规格页保存的模板候选"
                )
            }

            val created = ProjectCreator(filesDir).create(pack, title)
            if (created is CreateProjectResult.Success) {
                installOverride(filesDir, created.project.id, candidate)
            }
            created
        }

    companion object {
        fun overrideFile(filesDir: File, projectId: String): File =
            File(File(File(filesDir, "projects"), projectId), "authoring/spec-override.json")

        fun installOverride(filesDir: File, projectId: String, candidate: File) {
            val target = overrideFile(filesDir, projectId)
            target.parentFile?.mkdirs()
            AtomicFiles.writeText(target, candidate.readText(Charsets.UTF_8))
        }
    }
}
