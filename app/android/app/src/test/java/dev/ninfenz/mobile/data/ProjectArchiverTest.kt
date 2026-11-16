package dev.ninfenz.mobile.data

import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ProjectArchiverTest {
    private val valid = "{\"schema\":\"nf-project/1\",\"id\":\"p\",\"title\":\"p\",\"refs\":{" +
        "\"base_pack\":{\"id\":\"pack\",\"version\":\"1.0.0\"}," +
        "\"protocol\":{\"id\":\"proto\",\"digest\":\"0000\"}," +
        "\"graph\":{\"digest\":\"1111\"},\"spec\":{\"digest\":\"2222\"}}," +
        "\"status\":\"draft\",\"review\":{\"state\":\"pending\"},\"history\":[]}"

    @Test
    fun movesProjectOutOfProjectsIntoArchive() {
        val root = Files.createTempDirectory("nf-archive").toFile()
        val projects = java.io.File(root, "projects").apply { mkdirs() }
        val f = java.io.File(projects, "p.nfproject.json").apply { writeText(valid) }
        java.io.File(projects, "p/authoring").mkdirs()
        java.io.File(projects, "p/authoring/assembly.md").writeText("body")
        val archived = ProjectArchiver.archive(f, root, 123L)
        assertFalse(f.exists())
        assertTrue(archived.isFile)
        assertTrue(java.io.File(archived.parentFile, archived.name + ".data/authoring/assembly.md").isFile)
        assertTrue(archived.name.contains("123"))
        assertTrue(archived.readText() == valid)
    }

    @Test
    fun listsAndRestoresArchivedProject() {
        val root = Files.createTempDirectory("nf-archive-3").toFile()
        val projects = java.io.File(root, "projects").apply { mkdirs() }
        val f = java.io.File(projects, "p.nfproject.json").apply { writeText(valid) }
        java.io.File(projects, "p/authoring").mkdirs()
        java.io.File(projects, "p/authoring/assembly.md").writeText("body")
        ProjectArchiver.archive(f, root, 42L)
        assertEquals(1, ProjectArchiver.list(root).size)
        val restored = ProjectArchiver.restore(ProjectArchiver.list(root).first(), root)
        assertTrue(restored.isFile)
        assertEquals("body", java.io.File(projects, "p/authoring/assembly.md").readText())
        assertTrue(restored.name.endsWith(".nfproject.json"))
        assertTrue(ProjectArchiver.list(root).isEmpty())
    }

    @Test
    fun deletesArchivedFileOnlyInsideArchive() {
        val root = Files.createTempDirectory("nf-archive-delete").toFile()
        val archive = java.io.File(root, "projects-archive").apply { mkdirs() }
        val f = java.io.File(archive, "a.nfproject.json.1.archived").apply { writeText("x") }
        val data = java.io.File(archive, f.name + ".data").apply { mkdirs() }
        assertTrue(ProjectArchiver.delete(f, root))
        assertTrue(!f.exists())
        assertTrue(!data.exists())
        val outside = java.io.File(root, "outside").apply { writeText("x") }
        assertTrue(runCatching { ProjectArchiver.delete(outside, root) }.isFailure)
    }

    @Test
    fun rejectsInvalidArchivedProject() {
        val root = Files.createTempDirectory("nf-archive-4").toFile()
        val archive = java.io.File(root, "projects-archive").apply { mkdirs() }
        val bad = java.io.File(archive, "bad.nfproject.json.1.archived").apply { writeText("{}") }
        assertTrue(runCatching { ProjectArchiver.restore(bad, root) }.isFailure)
        assertTrue(bad.exists())
    }

    @Test
    fun rejectsFileOutsideProjects() {
        val root = Files.createTempDirectory("nf-archive-2").toFile()
        val f = java.io.File(root, "outside.nfproject.json").apply { writeText("{}") }
        val failed = runCatching { ProjectArchiver.archive(f, root) }.isFailure
        assertTrue(failed)
        assertTrue(f.exists())
    }
}
