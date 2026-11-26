package dev.ninfenz.mobile.data

import java.nio.file.Files
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import org.junit.Assert.assertTrue
import org.junit.Test

class ExtensionContributionValidatorTest {
    @Test
    fun flagsMissingRequiredConfig() {
        assertTrue(ExtensionContributionValidator.validate("saved_view", buildJsonObject { }) != null)
        assertTrue(ExtensionContributionValidator.validate("smart_collection", buildJsonObject { }) != null)
        assertTrue(ExtensionContributionValidator.validate("slot_transform", buildJsonObject { put("kind", "nope") }) != null)
        assertTrue(ExtensionContributionValidator.validate("review_checklist", buildJsonObject { }) != null)
        assertTrue(ExtensionContributionValidator.validate("assembly_recipe", buildJsonObject { }) != null)
    }

    @Test
    fun acceptsKnownShapes() {
        assertTrue(ExtensionContributionValidator.validate("saved_view", buildJsonObject { put("name", "最近") }) == null)
        assertTrue(ExtensionContributionValidator.validate("slot_transform", buildJsonObject { put("kind", "trim") }) == null)
    }

    @Test
    fun installedExtensionCarriesWarnings() {
        val dir = Files.createTempDirectory("nf-ext-warn").toFile()
        val store = ExtensionStore(dir)
        val text = buildJsonObject {
            put("schema", "nf-extension/1")
            put("id", "warn")
            put("type", "bundle")
            put("compat", buildJsonObject { put("min_app_version", "0.3.5"); put("schema_version", "nf-extension/1") })
            put("capabilities", kotlinx.serialization.json.buildJsonArray { add(kotlinx.serialization.json.JsonPrimitive("preset")) })
            put("contributions", kotlinx.serialization.json.buildJsonArray {
                add(buildJsonObject {
                    put("kind", "saved_view")
                    put("id", "bad")
                    put("config", buildJsonObject { })
                })
            })
        }.toString()
        val installed = store.install(text)
        assertTrue(installed.warnings.isNotEmpty())
    }
}
