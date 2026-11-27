package dev.ninfenz.mobile.ui

import android.content.Context
import dev.ninfenz.mobile.core.J
import dev.ninfenz.mobile.data.AuthorArtifactsLoader
import dev.ninfenz.mobile.data.DeliveryDraftStore
import dev.ninfenz.mobile.data.LibraryStore
import dev.ninfenz.mobile.data.PackEntry
import dev.ninfenz.mobile.data.PackStore
import dev.ninfenz.mobile.model.NfDocMerger
import dev.ninfenz.mobile.model.NfDocModel
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

    suspend fun assembleAll(context: Context, filesDir: File, outDir: File, selectedIds: Set<String>? = null): Created = coroutineScope {
        val snapshot = LibraryStore(filesDir).loadProjects()
        val projects = snapshot.projects.filter { selectedIds == null || it.project.id in selectedIds }
        require(projects.isNotEmpty() || snapshot.errors.isNotEmpty()) { context.getString(dev.ninfenz.mobile.R.string.batch_no_projects) }
        val packs = PackStore(filesDir).scan().packs.associateBy { it.id + "/" + it.version }
        val parsed = projects.map { entry ->
            async(Dispatchers.IO) {
                runCatching { assembleOne(entry.project, packs, filesDir, context) }.getOrElse { t ->
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
            Item("invalid-" + index, context.getString(dev.ninfenz.mobile.R.string.batch_project_parse_failed), false, null, error)
        }
        require(items.any { it.ok }) { context.getString(dev.ninfenz.mobile.R.string.batch_all_failed) }
        val file = withContext(Dispatchers.IO) { writeZip(items, outDir, context.getString(dev.ninfenz.mobile.R.string.nfdoc_merged_title)) }
        Created(file, items)
    }

    private suspend fun assembleOne(
        project: dev.ninfenz.mobile.model.Project,
        packs: Map<String, PackEntry>,
        filesDir: File,
        context: Context
    ): Item {
        val key = project.refs.basePackId + "/" + project.refs.basePackVersion
        val pack = packs[key] ?: error(context.getString(dev.ninfenz.mobile.R.string.batch_missing_pack, key))
        val override = File(File(File(filesDir, "projects"), project.id), "authoring/spec-override.json")
        val artifacts = AuthorArtifactsLoader.load(pack, override)
        val compiled = safeCall("graph-compile", buildJsonObject {
            put("graph", artifacts.graphJson)
            put("spec", artifacts.specJson)
        })
        val plan = compiled.resultObject() ?: error(compiled.error?.message ?: context.getString(dev.ninfenz.mobile.R.string.batch_plan_failed))
        val inputs = DeliveryDraftStore(filesDir).load(project.id)
        require(inputs.isNotEmpty()) { context.getString(dev.ninfenz.mobile.R.string.batch_no_draft) }
        val assembled = safeCall("assemble", buildJsonObject {
            put("plan", plan)
            put("spec", artifacts.specJson)
            put("inputs", buildJsonObject { for ((k, v) in inputs) put(k, v) })
        })
        val markdown = assembled.resultObject()?.let { J.optString(it, "markdown") }
        require(assembled.ok && !markdown.isNullOrBlank()) { assembled.error?.message ?: context.getString(dev.ninfenz.mobile.R.string.batch_empty_result) }
        val validated = safeCall("validate", buildJsonObject {
            put("markdown", markdown)
            put("spec", artifacts.specJson)
            put("plan", plan)
            put("level", "L1")
        })
        require(validated.ok) { validated.error?.message ?: context.getString(dev.ninfenz.mobile.R.string.batch_l1_failed) }
        return Item(project.id, project.title, true, markdown, null)
    }

    private fun safeName(id: String): String = id.replace(Regex("[^A-Za-z0-9._-]"), "_").ifBlank { "project" }

    internal fun writeZip(items: List<Item>, outDir: File, mergedTitle: String = "Merged document"): File {
        outDir.mkdirs()
        val target = File(outDir, "nf-batch-" + System.nanoTime() + ".zip")
        ZipOutputStream(target.outputStream()).use { out ->
            val good = items.filter { it.ok && it.markdown != null }
            val docs = good.mapNotNull { item ->
                item.markdown?.let { md -> NfDocModel.fromMarkdown(item.title, item.projectId, md) }
            }
            var mergedDoc = docs.firstOrNull()
            val conflicts = mutableListOf<NfDocMerger.Conflict>()
            for (doc in docs.drop(1)) {
                val result = NfDocMerger.merge(mergedDoc ?: doc, doc, mergedTitle)
                mergedDoc = result.doc
                conflicts += result.conflicts
            }
            val manifest = buildJsonObject {
                put("schema", "nf-batch/1")
                if (good.size >= 2) {
                    put("merged", "merged.md")
                    put("merged_doc", "merged.nf-doc.json")
                    putJsonArray("doc_conflicts") {
                        conflicts.forEach { c ->
                            add(buildJsonObject {
                                put("title", c.title)
                                put("reason", c.reason)
                            })
                        }
                    }
                }
                putJsonArray("projects") {
                    items.forEach { item ->
                        add(buildJsonObject {
                            put("id", item.projectId)
                            put("title", item.title)
                            put("ok", item.ok)
                            if (item.ok) {
                                put("markdown", "projects/" + safeName(item.projectId) + ".md")
                                put("doc", "projects/" + safeName(item.projectId) + ".nf-doc.json")
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
                val body = item.markdown ?: return@forEach
                val safe = safeName(item.projectId)
                out.putNextEntry(ZipEntry("projects/" + safe + ".md").apply { time = 0L })
                out.write(body.toByteArray(Charsets.UTF_8))
                out.closeEntry()
                out.putNextEntry(ZipEntry("projects/" + safe + ".nf-doc.json").apply { time = 0L })
                out.write(
                    NfDocModel.toJson(NfDocModel.fromMarkdown(item.title, item.projectId, body))
                        .toString().toByteArray(Charsets.UTF_8)
                )
                out.closeEntry()
            }
            if (good.size >= 2) {
                val merged = good.joinToString("\n\n---\n\n") { item ->
                    "<!-- project: " + item.projectId + " | " + item.title + " -->\n\n" + item.markdown
                }
                out.putNextEntry(ZipEntry("merged.md").apply { time = 0L })
                out.write(merged.toByteArray(Charsets.UTF_8))
                out.closeEntry()
                out.putNextEntry(ZipEntry("merged.nf-doc.json").apply { time = 0L })
                out.write(NfDocModel.toJson(mergedDoc ?: NfDocModel.append(docs, mergedTitle)).toString().toByteArray(Charsets.UTF_8))
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
