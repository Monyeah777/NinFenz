package dev.ninfenz.mobile.data

import java.nio.file.Files
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ExtensionStoreTest {
    private fun manifest(id: String = "starter") = buildJsonObject {
        put("schema", "nf-extension/1")
        put("id", id)
        put("type", "bundle")
        put("compat", buildJsonObject { put("min_app_version", "0.3.5"); put("schema_version", "nf-extension/1") })
        put("capabilities", kotlinx.serialization.json.buildJsonArray { add(kotlinx.serialization.json.JsonPrimitive("preset")) })
        put("targets", kotlinx.serialization.json.buildJsonArray { add(kotlinx.serialization.json.JsonPrimitive("import")) })
        put("contributions", kotlinx.serialization.json.buildJsonArray {
            add(buildJsonObject {
                put("kind", "import_recipe")
                put("id", "r1")
                put("config", buildJsonObject { put("source_kind", "clipboard") })
            })
        })
    }.toString()

    @Test
    fun installEnableDisableRemove() {
        val dir = Files.createTempDirectory("nf-ext").toFile()
        val store = ExtensionStore(dir)
        val ext = store.install(manifest())
        assertTrue(ext.enabled)
        assertEquals(1, ext.contributions.size)
        assertEquals("clipboard", ext.contributions.first().config["source_kind"].toString().trim('"'))
        store.setEnabled("starter", false)
        assertFalse(store.load().first().enabled)
        assertTrue(store.contributions().isEmpty())
        store.setEnabled("starter", true)
        assertTrue(store.contributions().isNotEmpty())
        store.remove("starter")
        assertTrue(store.load().isEmpty())
    }

    @Test
    fun rejectsDuplicateContributionIds() {
        val dir = Files.createTempDirectory("nf-ext-dup").toFile()
        val store = ExtensionStore(dir)
        val text = manifest().replace("\"id\":\"r1\"", "\"id\":\"r1\"").replace("\"kind\":\"import_recipe\"", "\"kind\":\"import_recipe\"")
        store.install(text)
        val dup = text.replace("\"contributions\":[", "\"contributions\":[{\"kind\":\"saved_view\",\"id\":\"r1\",\"config\":{}},")
        val rejected = runCatching { store.install(dup) }.isFailure
        assertTrue(rejected)
    }
}
