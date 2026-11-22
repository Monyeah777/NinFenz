package dev.ninfenz.mobile.data

import java.io.File
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

/** 把「切片结果」落成可建项目的草稿：主草稿 + zero-slice sidecar + mapping。 */
object ZeroSliceProjectDraft {
    data class Prepared(val file: File, val title: String)

    fun prepare(
        filesDir: File,
        rawJson: String,
        report: ZeroSliceReport,
        accepted: Set<Int>,
        unmapped: List<String>,
        title: String
    ): Prepared {
        val store = LibraryStore(filesDir)
        val base = store.uniqueDraftBase(title)
        val file = store.saveDraft(base, rawJson)
        ZeroSliceStore(filesDir).saveDraft(file, report)
        val mappingJson = buildJsonObject {
            put("accepted", JsonArray(accepted.sorted().map { JsonPrimitive(it) }))
            put("unmapped", JsonArray(unmapped.map { JsonPrimitive(it) }))
        }.toString()
        store.saveDraft(base + ".mapping", mappingJson)
        return Prepared(file, title)
    }
}
