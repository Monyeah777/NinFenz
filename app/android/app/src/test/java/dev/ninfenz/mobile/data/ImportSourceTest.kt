package dev.ninfenz.mobile.data

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

class ImportSourceTest {
    @Test
    fun allKindsMatchImportSchema() {
        val schema = Json.parseToJsonElement(File("../../schema/nf-import.schema.json").readText())
            .jsonObject["properties"]!!.jsonObject["source"]!!.jsonObject["properties"]!!
            .jsonObject["kind"]!!.jsonObject["enum"]!!.jsonArray
            .map { it.jsonPrimitive.content }.toSet()
        assertEquals(schema, ImportSource.ALL)
    }

    @Test
    fun sampleHeadingsCoverSpecSections() {
        val sample = File("src/main/assets/sample-pack/docs/sample.md").readText()
        val spec = Json.parseToJsonElement(File("src/main/assets/sample-pack/spec/main.nfspec.json").readText())
            .jsonObject["sections"]!!.jsonArray.map { it.jsonObject["title"]!!.jsonPrimitive.content }
        assertTrue(sample.contains("## 开篇"))
        assertTrue(sample.contains("## 正文"))
        assertTrue(sample.contains("## 收束"))
        assertTrue(spec.containsAll(listOf("开篇", "正文", "收束")))
    }
}
