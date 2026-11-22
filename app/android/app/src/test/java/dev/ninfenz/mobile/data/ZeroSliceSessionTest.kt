package dev.ninfenz.mobile.data

import java.nio.file.Files
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class ZeroSliceSessionTest {
    private val json = """
        {"mappings":[{"from_index":0,"to_id":"SLT-01","to_name":"主题句","confidence":95}],
         "exceptions":[{"text":"x","target":null,"reason":"低置信"}],
         "coverage":88}
    """.trimIndent()

    @Test
    fun parsesReport() {
        val report = ZeroSliceModel.parse(Json.parseToJsonElement(json).jsonObject)
        assertEquals(1, report.mappings.size)
        assertEquals("SLT-01", report.mappings[0].toId)
        assertEquals(95, report.mappings[0].confidence)
        assertEquals(1, report.exceptions.size)
        assertEquals(88, report.coverage)
    }

    @Test
    fun parsesProjectSlots() {
        val report = ZeroSliceModel.parse(Json.parseToJsonElement(
            """{"mappings":[],"exceptions":[],"coverage":100,"project":{"schema":"nf-project/1","slots":{"SLT-01":"甲"}}}"""
        ).jsonObject)
        assertEquals("甲", report.projectSlots["SLT-01"])
    }

    @Test
    fun draftSidecarRoundTrip() {
        val dir = java.nio.file.Files.createTempDirectory("nf-zero-draft").toFile()
        val draft = java.io.File(dir, "draft.json").apply { writeText("{}") }
        val report = ZeroSliceModel.parse(Json.parseToJsonElement(json).jsonObject)
            .copy(slotValues = mapOf("SLT-01" to "主题正文"))
        val store = ZeroSliceStore(dir)
        store.saveDraft(draft, report)
        val loaded = store.loadDraft(draft)
        assertEquals("主题正文", loaded?.slotValues?.get("SLT-01"))
    }

    @Test
    fun slotValuesRoundTrip() {
        val report = ZeroSliceModel.parse(Json.parseToJsonElement(json).jsonObject)
            .copy(slotValues = mapOf("SLT-01" to "主题正文"))
        val parsed = ZeroSliceModel.parse(ZeroSliceModel.toJson(report))
        assertEquals("主题正文", parsed.slotValues["SLT-01"])
    }

    @Test
    fun savesAndRestoresByDigest() {
        val dir = Files.createTempDirectory("zero-slice").toFile()
        val store = ZeroSliceStore(dir)
        val report = ZeroSliceModel.parse(Json.parseToJsonElement(json).jsonObject)
        store.save("sha1", report)
        assertEquals(report, store.load("sha1"))
        assertNull(store.load("sha2"))
        store.clear()
        assertNull(store.load("sha1"))
    }
}
