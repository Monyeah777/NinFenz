package dev.ninfenz.mobile.data

import java.io.File
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive

/** 本地模板候选落盘；仅保存已通过核心 spec-validate 的候选。 */
class TemplateCandidateStore(private val filesDir: File) {
    fun list(): List<File> {
        val dir = File(filesDir, "templates")
        if (!dir.isDirectory) return emptyList()
        return dir.listFiles { f -> f.isFile && f.name.startsWith("candidate-") && f.name.endsWith(".json") }
            ?.sortedByDescending { it.lastModified() }
            ?: emptyList()
    }

    fun titleOf(file: File): String {
        return runCatching {
            val root = kotlinx.serialization.json.Json.parseToJsonElement(file.readText(Charsets.UTF_8)).jsonObject
            root["title"]?.jsonPrimitive?.content?.takeIf { it.isNotBlank() } ?: file.name
        }.getOrDefault(file.name)
    }

    fun save(spec: JsonObject): File {
        val id = spec["id"]?.toString()?.trim('"')?.ifBlank { "candidate" } ?: "candidate"
        val safe = id.replace(Regex("[^A-Za-z0-9._-]"), "_").take(64)
        val dir = File(filesDir, "templates").apply { mkdirs() }
        val file = File(dir, "candidate-" + safe + ".json")
        AtomicFiles.writeText(file, spec.toString())
        return file
    }
}
