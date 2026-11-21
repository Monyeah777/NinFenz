package dev.ninfenz.mobile.model

import dev.ninfenz.mobile.core.J
import dev.ninfenz.mobile.core.ModelException
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonPrimitive

/** nf-patch/1：按 blockId 的语义补丁；应用后重新渲染 Markdown。 */
object NfPatchModel {
    const val SCHEMA = "nf-patch/1"

    data class Op(
        val kind: String,
        val blockId: String?,
        val afterBlockId: String?,
        val index: Int?,
        val text: String?,
        val slot: String?
    )

    data class Patch(val ops: List<Op>)

    data class Change(val op: String, val blockId: String?, val before: String?, val after: String?)
    data class Result(val markdown: String, val applied: Int, val rejected: List<String>, val changes: List<Change> = emptyList())

    private data class Entry(val id: String, val block: MarkdownBlock)

    fun parse(text: String): Patch {
        val o = J.parseObject(text, SCHEMA)
        J.schema(o, SCHEMA)
        val ops = o["ops"] as? JsonArray ?: throw ModelException("NF-E-002", "/ops", "ops 必须是数组", "按 nf-patch/1 修正")
        if (ops.isEmpty()) throw ModelException("NF-E-002", "/ops", "ops 不能为空", "至少一条补丁")
        return Patch(ops.mapIndexed { i, el ->
            val op = el as? JsonObject ?: throw ModelException("NF-E-002", "/ops/" + i, "op 必须是对象", "按 nf-patch/1 修正")
            val kind = op["op"]?.jsonPrimitive?.contentOrNull
                ?: throw ModelException("NF-E-002", "/ops/" + i + "/op", "缺 op", "replace/insert/delete/move/set-slot")
            val blockId = op["block_id"]?.jsonPrimitive?.contentOrNull
            val afterBlockId = op["after_block_id"]?.jsonPrimitive?.contentOrNull
            val index = op["index"]?.jsonPrimitive?.intOrNull
            val text = op["text"]?.jsonPrimitive?.contentOrNull
            val slot = op["slot"]?.jsonPrimitive?.contentOrNull
            when (kind) {
                "replace" -> if (blockId == null || text == null) throw ModelException("NF-E-002", "/ops/" + i, "replace 需要 block_id + text", "补齐字段")
                "insert" -> if (text == null) throw ModelException("NF-E-002", "/ops/" + i, "insert 需要 text", "补齐 text")
                "delete" -> if (blockId == null) throw ModelException("NF-E-002", "/ops/" + i, "delete 需要 block_id", "补齐 block_id")
                "move" -> if (blockId == null || (afterBlockId == null && index == null)) throw ModelException("NF-E-002", "/ops/" + i, "move 需要 block_id + after_block_id/index", "补齐目标")
                "set-slot" -> if (slot == null || text == null) throw ModelException("NF-E-002", "/ops/" + i, "set-slot 需要 slot + text", "补齐字段")
                else -> throw ModelException("NF-E-002", "/ops/" + i + "/op", "未知 op " + kind, "见 app/schema/nf-patch.schema.json")
            }
            Op(kind, blockId, afterBlockId, index, text, slot)
        })
    }

    fun apply(markdown: String, patch: Patch): Result {
        val entries = MarkdownBlocks.parse(markdown).mapIndexed { i, b -> Entry("b" + (i + 1), b) }.toMutableList()
        var applied = 0
        val rejected = mutableListOf<String>()
        val changes = mutableListOf<Change>()
        var next = 1
        fun find(id: String?): Int = entries.indexOfFirst { it.id == id }
        patch.ops.forEachIndexed { i, op ->
            when (op.kind) {
                "replace" -> {
                    val at = find(op.blockId)
                    if (at < 0) rejected += "op " + (i + 1) + "：找不到 " + op.blockId
                    else {
                        val before = entries[at].block.text
                        entries[at] = entries[at].copy(block = entries[at].block.copy(text = op.text!!))
                        changes += Change("replace", op.blockId, before, op.text)
                        applied++
                    }
                }
                "delete" -> {
                    val at = find(op.blockId)
                    if (at < 0) rejected += "op " + (i + 1) + "：找不到 " + op.blockId
                    else {
                        changes += Change("delete", op.blockId, entries[at].block.text, null)
                        entries.removeAt(at)
                        applied++
                    }
                }
                "insert" -> {
                    val at = if (op.afterBlockId != null) find(op.afterBlockId) + 1 else (op.index ?: entries.size)
                    if (at < 0) rejected += "op " + (i + 1) + "：找不到 " + op.afterBlockId
                    else {
                        entries.add(at.coerceIn(0, entries.size), Entry("n" + next++, MarkdownBlock(-1, op.text!!)))
                        changes += Change("insert", op.afterBlockId, null, op.text)
                        applied++
                    }
                }
                "move" -> {
                    val at = find(op.blockId)
                    if (at < 0) rejected += "op " + (i + 1) + "：找不到 " + op.blockId
                    else {
                        val item = entries.removeAt(at)
                        val target = if (op.afterBlockId != null) find(op.afterBlockId) + 1 else (op.index ?: entries.size)
                        entries.add(target.coerceIn(0, entries.size), item)
                        changes += Change("move", op.blockId, item.block.text, item.block.text)
                        applied++
                    }
                }
                "set-slot" -> rejected += "op " + (i + 1) + "：set-slot 不修改块，需项目槽位"
            }
        }
        return Result(MarkdownBlocks.render(entries.map { it.block }), applied, rejected, changes)
    }
}
