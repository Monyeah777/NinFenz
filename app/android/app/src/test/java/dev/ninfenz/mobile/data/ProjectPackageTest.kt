package dev.ninfenz.mobile.data

import java.io.File
import java.nio.file.Files
import java.util.zip.ZipFile
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ProjectPackageTest {
    @Test
    fun includesProjectJsonAndDataDir() {
        val root = Files.createTempDirectory("nf-project-package").toFile()
        val project = File(root, "p.nfproject.json").apply { writeText("{}") }
        val data = File(root, "p/authoring").apply { mkdirs() }
        File(data, "assembly.md").writeText("body")
        val zip = ProjectPackage.create(project, File(root, "p"), File(root, "out"))
        ZipFile(zip).use { z ->
            val names = z.entries().toList().map { it.name }.sorted()
            assertEquals(listOf("data/authoring/assembly.md", "manifest.json", "p.nfproject.json"), names)
            assertEquals("body", z.getInputStream(z.getEntry("data/authoring/assembly.md")).bufferedReader().readText())
            val manifest = z.getInputStream(z.getEntry("manifest.json")).bufferedReader().readText()
            assertTrue(manifest.contains("nf-project-package/1"))
            assertTrue(manifest.contains("data/authoring/assembly.md"))
        }
    }

    @Test
    fun rejectsMissingProject() {
        val root = Files.createTempDirectory("nf-project-package-2").toFile()
        assertTrue(runCatching { ProjectPackage.create(File(root, "missing.json"), root, root) }.isFailure)
    }
}
