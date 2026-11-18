package dev.ninfenz.mobile.data

import java.io.File
import kotlinx.serialization.json.JsonObject

/** 本地模板候选落盘；仅保存已通过核心 spec-validate 的候选。 */
class TemplateCandidateStore(private val filesDir: File) {
    fun save(spec: JsonObject): File {
        val id = spec["id"]?.toString()?.trim('"')?.ifBlank { "candidate" } ?: "candidate"
        val safe = id.replace(Regex("[^A-Za-z0-9._-]"), "_").take(64)
        val dir = File(filesDir, "templates").apply { mkdirs() }
        val file = File(dir, "candidate-" + safe + ".json")
        AtomicFiles.writeText(file, spec.toString())
        return file
    }
}
