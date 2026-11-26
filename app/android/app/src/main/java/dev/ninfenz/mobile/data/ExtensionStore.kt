package dev.ninfenz.mobile.data

import dev.ninfenz.mobile.core.J
import dev.ninfenz.mobile.core.ModelException
import java.io.File
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put

/** 本地声明式扩展：只读清单 + 启用状态；不执行代码、不联网。 */
class ExtensionStore(private val filesDir: File) {
    data class Contribution(val kind: String, val id: String, val config: JsonObject)
    data class Installed(
        val id: String,
        val type: String,
        val targets: List<String>,
        val contributions: List<Contribution>,
        val signed: Boolean,
        val enabled: Boolean,
        val path: String
    )

    private fun root(): File = File(filesDir, "extensions").apply { mkdirs() }
    private fun file(id: String): File = File(File(root(), id), "nf-extension.json")
    private fun enabledFile(): File = File(filesDir, "extensions-enabled.json")

    private fun enabledIds(): Set<String> {
        val f = enabledFile()
        if (!f.isFile) return emptySet()
        return runCatching {
            Json.parseToJsonElement(f.readText(Charsets.UTF_8)).jsonObject["enabled"]?.jsonArray
                ?.mapNotNull { it.jsonPrimitive.content }?.toSet().orEmpty()
        }.getOrElse { emptySet() }
    }

    private fun saveEnabled(ids: Set<String>) {
        AtomicFiles.writeText(enabledFile(), buildJsonObject {
            put("enabled", buildJsonArray { ids.sorted().forEach { add(kotlinx.serialization.json.JsonPrimitive(it)) } })
        }.toString())
    }

    fun load(): List<Installed> {
        val enabled = enabledIds()
        return root().listFiles()?.filter { it.isDirectory }?.sortedBy { it.name }?.mapNotNull { dir ->
            val f = File(dir, "nf-extension.json")
            if (!f.isFile) return@mapNotNull null
            runCatching {
                val o = J.parseObject(f.readText(Charsets.UTF_8), "nf-extension/1")
                parse(o, enabled.contains(dir.name), f.absolutePath)
            }.getOrNull()
        }.orEmpty()
    }

    fun install(text: String): Installed {
        val o = J.parseObject(text, "nf-extension/1")
        val id = o["id"]?.jsonPrimitive?.content
            ?: throw ModelException("NF-EXT-003", "/id", "扩展缺 id", "补 id")
        if (!id.matches(Regex("^[A-Za-z0-9._-]+$"))) {
            throw ModelException("NF-EXT-003", "/id", "扩展 id 含非法字符", "使用字母数字._-")
        }
        val contributionIds = (o["contributions"] as? kotlinx.serialization.json.JsonArray)?.mapNotNull {
            (it as? JsonObject)?.get("id")?.jsonPrimitive?.content
        }.orEmpty()
        if (contributionIds.size != contributionIds.toSet().size) {
            throw ModelException("NF-EXT-003", "/contributions", "contribution id 重复", "保证 id 唯一")
        }
        val dir = File(root(), id).apply { mkdirs() }
        AtomicFiles.writeText(file(id), o.toString())
        val enabled = enabledIds() + id
        saveEnabled(enabled)
        return parse(o, true, file(id).absolutePath)
    }

    fun remove(id: String) {
        File(root(), id).deleteRecursively()
        saveEnabled(enabledIds() - id)
    }

    fun setEnabled(id: String, enabled: Boolean) {
        val next = enabledIds().toMutableSet()
        if (enabled) next.add(id) else next.remove(id)
        saveEnabled(next)
    }

    fun contributions(kinds: Set<String>? = null): List<Contribution> =
        load().filter { it.enabled }.flatMap { ext ->
            ext.contributions.filter { kinds == null || it.kind in kinds }
        }

    fun starterJson(context: android.content.Context): String? = runCatching {
        context.assets.open("extensions/starter.json").bufferedReader(Charsets.UTF_8).use { it.readText() }
    }.getOrNull()

    private fun parse(o: JsonObject, enabled: Boolean, path: String): Installed {
        val contributions = (o["contributions"] as? kotlinx.serialization.json.JsonArray)?.mapNotNull { el ->
            val c = el as? JsonObject ?: return@mapNotNull null
            Contribution(
                kind = c["kind"]?.jsonPrimitive?.content ?: "",
                id = c["id"]?.jsonPrimitive?.content ?: "",
                config = c["config"] as? JsonObject ?: buildJsonObject { }
            )
        }.orEmpty()
        return Installed(
            id = o["id"]?.jsonPrimitive?.content.orEmpty(),
            type = o["type"]?.jsonPrimitive?.content.orEmpty(),
            targets = (o["targets"] as? kotlinx.serialization.json.JsonArray)?.mapNotNull { it.jsonPrimitive.content }.orEmpty(),
            contributions = contributions,
            signed = o["signature"] != null,
            enabled = enabled,
            path = path
        )
    }
}
