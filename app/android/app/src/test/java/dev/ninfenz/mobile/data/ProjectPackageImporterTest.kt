package dev.ninfenz.mobile.data

import java.io.File
import java.nio.file.Files
import java.util.zip.ZipEntry
import java.util.zip.ZipFile
import java.util.zip.ZipOutputStream
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ProjectPackageImporterTest {
    private fun zip(entries: List<Pair<String, String>>): File {
        val f = File.createTempFile("nf-project", ".zip")
        ZipOutputStream(f.outputStream()).use { out ->
            entries.forEach { (name, text) ->
                out.putNextEntry(ZipEntry(name)); out.write(text.toByteArray()); out.closeEntry()
            }
        }
        return f
    }

    private val doc = "{\"schema\":\"nf-project/1\",\"id\":\"p\",\"title\":\"p\",\"refs\":{" +
        "\"base_pack\":{\"id\":\"pack\",\"version\":\"1.0.0\"}," +
        "\"protocol\":{\"id\":\"proto\",\"digest\":\"0000\"}," +
        "\"graph\":{\"digest\":\"1111\"},\"spec\":{\"digest\":\"2222\"}}," +
        "\"status\":\"draft\",\"review\":{\"state\":\"pending\"},\"history\":[]}"

    @Test
    fun importsJsonAndData() {
        val root = Files.createTempDirectory("nf-import-project").toFile()
        val imported = ProjectPackageImporter.import(root, zip(listOf("p.nfproject.json" to doc, "data/authoring/assembly.md" to "body")))
        assertEquals("p", imported.id)
        assertEquals("body", File(root, "projects/p/authoring/assembly.md").readText())
    }

    @Test
    fun doesNotOverwriteExistingId() {
        val root = Files.createTempDirectory("nf-import-project-2").toFile()
        File(root, "projects").mkdirs()
        File(root, "projects/p.nfproject.json").writeText(doc)
        val imported = ProjectPackageImporter.import(root, zip(listOf("p.nfproject.json" to doc)))
        assertTrue(imported.id != "p")
        assertTrue(File(root, "projects/p.nfproject.json").readText().contains("\"p\""))
    }

    @Test
    fun roundTripsPackageExportImport() {
        val source = Files.createTempDirectory("nf-package-src").toFile()
        val project = java.io.File(source, "p.nfproject.json").apply { writeText(doc) }
        java.io.File(source, "p/authoring").mkdirs()
        java.io.File(source, "p/authoring/assembly.md").writeText("body")
        val zip = ProjectPackage.create(project, java.io.File(source, "p"), java.io.File(source, "out"))
        val target = Files.createTempDirectory("nf-package-dst").toFile()
        val imported = ProjectPackageImporter.import(target, zip)
        assertEquals("p", imported.id)
        assertEquals("body", java.io.File(target, "projects/p/authoring/assembly.md").readText())
    }

    @Test
    fun detectsProjectPackage() {
        val root = Files.createTempDirectory("nf-project-detect").toFile()
        val zip = zip(listOf("p.nfproject.json" to doc))
        assertTrue(ProjectPackageImporter.hasProjectJson(zip))
        assertTrue(!ProjectPackageImporter.hasProjectJson(zip(listOf("data/a.txt" to "x"))))
    }

    @Test
    fun importsProjectNestedUnderFolder() {
        val root = Files.createTempDirectory("nf-import-nested").toFile()
        val zip = zip(listOf("bundle/p.nfproject.json" to doc, "bundle/data/authoring/assembly.md" to "nested"))
        val imported = ProjectPackageImporter.import(root, zip)
        assertEquals("p", imported.id)
        assertEquals("nested", java.io.File(root, "projects/p/authoring/assembly.md").readText())
        assertTrue(ProjectPackageImporter.hasProjectJson(zip))
    }

    @Test
    fun rejectsTamperedData() {
        val source = Files.createTempDirectory("nf-tamper-src").toFile()
        val project = java.io.File(source, "p.nfproject.json").apply { writeText(doc) }
        java.io.File(source, "p/authoring").mkdirs()
        java.io.File(source, "p/authoring/assembly.md").writeText("body")
        val zip = ProjectPackage.create(project, java.io.File(source, "p"), java.io.File(source, "out"))
        val bad = java.io.File(source, "bad.zip")
        ZipFile(zip).use { z ->
            ZipOutputStream(bad.outputStream()).use { out ->
                z.entries().toList().forEach { entry ->
                    out.putNextEntry(ZipEntry(entry.name))
                    val bytes = z.getInputStream(entry).readBytes()
                    out.write(if (entry.name == "data/authoring/assembly.md") "tampered".toByteArray() else bytes)
                    out.closeEntry()
                }
            }
        }
        val target = Files.createTempDirectory("nf-tamper-dst").toFile()
        assertTrue(runCatching { ProjectPackageImporter.import(target, bad) }.isFailure)
    }

    @Test
    fun rejectsUnlistedDataEntry() {
        val source = Files.createTempDirectory("nf-unlisted-src").toFile()
        val project = java.io.File(source, "p.nfproject.json").apply { writeText(doc) }
        java.io.File(source, "p/authoring").mkdirs()
        java.io.File(source, "p/authoring/assembly.md").writeText("body")
        val zip = ProjectPackage.create(project, java.io.File(source, "p"), java.io.File(source, "out"))
        val bad = java.io.File(source, "bad.zip")
        ZipFile(zip).use { z ->
            ZipOutputStream(bad.outputStream()).use { out ->
                z.entries().toList().forEach { entry ->
                    out.putNextEntry(ZipEntry(entry.name))
                    out.write(z.getInputStream(entry).readBytes())
                    out.closeEntry()
                }
                out.putNextEntry(ZipEntry("data/authoring/extra.txt"))
                out.write("extra".toByteArray())
                out.closeEntry()
            }
        }
        val target = Files.createTempDirectory("nf-unlisted-dst").toFile()
        assertTrue(runCatching { ProjectPackageImporter.import(target, bad) }.isFailure)
    }

    @Test
    fun importsProjectJsonWithBom() {
        val root = Files.createTempDirectory("nf-bom-project").toFile()
        val imported = ProjectPackageImporter.import(root, zip(listOf("p.nfproject.json" to "\uFEFF" + doc)))
        assertEquals("p", imported.id)
    }

    @Test
    fun importsProjectUnderDeeperFolder() {
        val root = Files.createTempDirectory("nf-import-deep").toFile()
        val zip = zip(listOf("a/b/p.nfproject.json" to doc, "a/b/data/authoring/assembly.md" to "deep"))
        val imported = ProjectPackageImporter.import(root, zip)
        assertEquals("p", imported.id)
        assertEquals("deep", java.io.File(root, "projects/p/authoring/assembly.md").readText())
    }

    @Test
    fun rejectsMissingProjectJson() {
        val root = Files.createTempDirectory("nf-no-project").toFile()
        assertTrue(runCatching { ProjectPackageImporter.import(root, zip(listOf("data/a.md" to "x"))) }.isFailure)
    }

    @Test
    fun rejectsProjectWithoutId() {
        val root = Files.createTempDirectory("nf-no-id").toFile()
        assertTrue(runCatching { ProjectPackageImporter.import(root, zip(listOf("p.nfproject.json" to "{}"))) }.isFailure)
    }

    @Test
    fun rejectsTraversal() {
        val root = Files.createTempDirectory("nf-import-project-3").toFile()
        assertTrue(runCatching { ProjectPackageImporter.import(root, zip(listOf("../evil.nfproject.json" to doc))) }.isFailure)
    }
}
