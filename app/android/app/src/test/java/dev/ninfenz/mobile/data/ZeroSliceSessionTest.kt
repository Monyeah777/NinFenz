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
