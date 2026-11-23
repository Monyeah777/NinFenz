package dev.ninfenz.mobile.data

import dev.ninfenz.mobile.model.ProtocolField
import dev.ninfenz.mobile.model.SpecSlot
import java.io.File
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive

/** 协议字段 -> spec 槽位的显式预填：只认同名（规范化后）或显式 slot_id，不猜顺序。 */
object ProtocolSlotPrefill {
    fun normalize(value: String): String =
        value.lowercase().filter { it.isLetterOrDigit() }

    fun bind(fields: List<ProtocolField>, slots: List<SpecSlot>, params: Map<String, String>): Map<String, String> {
        val byName = mutableMapOf<String, String>()
        for (slot in slots) {
            val key = normalize(slot.name)
            if (key.isNotBlank()) byName[key] = slot.id
        }
        val out = mutableMapOf<String, String>()
        for (field in fields) {
            val value = params[field.id]?.trim().orEmpty()
            if (value.isBlank()) continue
            val slotId = byName[normalize(field.label)] ?: continue
            out[slotId] = value
        }
        return out
    }

    fun loadParams(filesDir: File, projectId: String): Map<String, String> {
        val file = File(File(File(filesDir, "projects"), projectId), "overlay/nf-overlay.json")
        if (!file.isFile) return emptyMap()
        return runCatching {
            val root = Json.parseToJsonElement(file.readText(Charsets.UTF_8)).jsonObject
            val params = root["params"]?.jsonObject ?: return@runCatching emptyMap()
            params.mapNotNull { (key, value) ->
                val text = value.jsonPrimitive.content
                if (text.isBlank()) null else key to text
            }.toMap()
        }.getOrDefault(emptyMap())
    }
}
