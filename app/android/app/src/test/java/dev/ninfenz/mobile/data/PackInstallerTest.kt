package dev.ninfenz.mobile.data

import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class PackInstallerTest {
    @Test
    fun installsNewVersionAndRemovesStage() {
        val root = Files.createTempDirectory("nf-pack-install").toFile()
        val stage = root.resolve("incoming/demo/1.0.0").apply { mkdirs() }
        stage.resolve("nf-pack.json").writeText("{}", Charsets.UTF_8)
        val target = root.resolve("library/packs/demo/1.0.0")
        PackInstaller.install(stage, target)
        assertTrue(target.resolve("nf-pack.json").isFile)
        assertFalse(stage.exists())
        assertFalse(root.resolve("library/packs/demo/1.0.0.old").exists())
    }

    @Test
    fun replacesExistingVersionAndDropsOldBackup() {
        val root = Files.createTempDirectory("nf-pack-install-2").toFile()
        val target = root.resolve("library/packs/demo/1.0.0").apply { mkdirs() }
        target.resolve("nf-pack.json").writeText("old", Charsets.UTF_8)
        val stage = root.resolve("incoming/demo/1.0.0").apply { mkdirs() }
        stage.resolve("nf-pack.json").writeText("new", Charsets.UTF_8)
        PackInstaller.install(stage, target)
        assertEquals("new", target.resolve("nf-pack.json").readText())
        assertFalse(root.resolve("library/packs/demo/1.0.0.old").exists())
    }
}
