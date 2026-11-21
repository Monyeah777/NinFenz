package dev.ninfenz.mobile.ui

import dev.ninfenz.mobile.core.J
import dev.ninfenz.mobile.data.AuthorArtifactsLoader
import dev.ninfenz.mobile.data.DeliveryDraftStore
import dev.ninfenz.mobile.data.LibraryStore
import dev.ninfenz.mobile.data.PackEntry
import dev.ninfenz.mobile.data.PackStore
import java.io.File
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonArray

/** 多项目并行装配：每个项目用自己的交付草稿；失败逐项记录，不阻断其他项目。 */
object BatchAssembler {
    data class Item(val projectId: String, val title: String, val ok: Boolean, val markdown: String?, val error: String?)
    data class Created(val file: File, val items: List<Item>)

    suspend fun assembleAll(filesDir: File, outDir: File, selectedIds: Set<String>? = null): Created = coroutineScope {
        val snapshot = LibraryStore(filesDir).loadProjects()
        val projects = snapshot.projects.filter { selectedIds == null || it.project.id in selectedIds }
        require(projects.isNotEmpty() || snapshot.errors.isNotEmpty()) { "没有可装配的项目" }
        val packs = PackStore(filesDir).scan().packs.associateBy { it.id + "/" + it.version }
        val parsed = projects.map { entry ->
            async(Dispatchers.IO) {
                runCatching { assembleOne(entry.project, packs, filesDir) }.getOrElse { t ->
                    Item(entry.project.id, entry.project.title, false, null, t.message ?: t.javaClass.simpleName)
                }
            }
        }.awaitAll()
        val errors = if (selectedIds == null) {
            snapshot.errors
        } else {
            snapshot.errors.filter { error -> selectedIds.any { id -> error.startsWith(id + ".nfproject.json") } }
        }
        val items = parsed + errors.mapIndexed { index, error ->
            Item("invalid-" + index, "项目解析失败", false, null, error)
        }
        require(items.any { it.ok }) { "所有项目都未装配成功" }
        val file = withContext(Dispatchers.IO) { writeZip(items, outDir) }
        Created(file, items)
    }

    private suspend fun assembleOne(
        project: dev.ninfenz.mobile.model.Project,
        packs: Map<String, PackEntry>,
        filesDir: File
    ): Item {
        val key = project.refs.basePackId + "/" + project.refs.basePackVersion
        val pack = packs[key] ?: error("缺少 Pack " + key)
        val override = File(File(File(filesDir, "projects"), project.id), "authoring/spec-override.json")
        val artifacts = AuthorArtifactsLoader.load(pack, override)
        val compiled = safeCall("graph-compile", buildJsonObject {
            put("graph", artifacts.graphJson)
            put("spec", artifacts.specJson)
        })
        val plan = compiled.resultObject() ?: error(compiled.error?.message ?: "计划编译失败")
        val inputs = DeliveryDraftStore(filesDir).load(project.id)
        require(inputs.isNotEmpty()) { "没有交付草稿" }
        val assembled = safeCall("assemble", buildJsonObject {
            put("plan", plan)
            put("spec", artifacts.specJson)
            put("inputs", buildJsonObject { for ((k, v) in inputs) put(k, v) })
        })
        val markdown = assembled.resultObject()?.let { J.optString(it, "markdown") }
        require(assembled.ok && !markdown.isNullOrBlank()) { assembled.error?.message ?: "装配结果为空" }
        val validated = safeCall("validate", buildJsonObject {
            put("markdown", markdown)
            put("spec", artifacts.specJson)
            put("plan", plan)
            put("level", "L1")
        })
        require(validated.ok) { validated.error?.message ?: "L1 校验未通过" }
        return Item(project.id, project.title, true, markdown, null)
    }

    private fun safeName(id: String): String = id.replace(Regex("[^A-Za-z0-9._-]"), "_").ifBlank { "project" }

    internal fun writeZip(items: List<Item>, outDir: File): File {
        outDir.mkdirs()
        val target = File(outDir, "nf-batch-" + System.nanoTime() + ".zip")
        ZipOutputStream(target.outputStream()).use { out ->
            val good = items.filter { it.ok && it.markdown != null }
            val manifest = buildJsonObject {
                put("schema", "nf-batch/1")
                if (good.size >= 2) put("merged", "merged.md")
                putJsonArray("projects") {
                    items.forEach { item ->
                        add(buildJsonObject {
                            put("id", item.projectId)
                            put("title", item.title)
                            put("ok", item.ok)
                            if (item.ok) {
                                put("markdown", "projects/" + safeName(item.projectId) + ".md")
                                put("validated", "L1")
                            }
                            item.error?.let { put("error", it) }
                        })
                    }
                }
            }
            out.putNextEntry(ZipEntry("nf-batch.json").apply { time = 0L })
            out.write(manifest.toString().toByteArray(Charsets.UTF_8))
            out.closeEntry()
            good.forEach { item ->
                out.putNextEntry(ZipEntry("projects/" + safeName(item.projectId) + ".md").apply { time = 0L })
                out.write(item.markdown!!.toByteArray(Charsets.UTF_8))
                out.closeEntry()
            }
            if (good.size >= 2) {
                val merged = good.joinToString("\n\n---\n\n") { item ->
                    "<!-- project: " + item.projectId + " | " + item.title + " -->\n\n" + item.markdown
                }
                out.putNextEntry(ZipEntry("merged.md").apply { time = 0L })
                out.write(merged.toByteArray(Charsets.UTF_8))
                out.closeEntry()
            }
        }
        outDir.listFiles { f -> f.isFile && f.name.startsWith("nf-batch-") && f.name.endsWith(".zip") }
            ?.sortedByDescending { it.lastModified() }
            ?.drop(3)
            ?.forEach { it.delete() }
        return target
    }
}
