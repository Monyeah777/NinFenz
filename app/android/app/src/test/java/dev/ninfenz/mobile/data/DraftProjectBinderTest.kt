package dev.ninfenz.mobile.data

import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class DraftProjectBinderTest {
    @Test
    fun writesSpecOverrideNextToProject() {
        val filesDir = Files.createTempDirectory("nf-bind-spec").toFile()
        val projects = java.io.File(filesDir, "projects").apply { mkdirs() }
        java.io.File(projects, "p.nfproject.json").writeText("{}")
        val target = DraftProjectBinder.bindSpec(filesDir, "p", "{\"schema\":\"nf-md-spec/1\"}")
        assertTrue(target.isFile)
        assertEquals("{\"schema\":\"nf-md-spec/1\"}", target.readText())
    }

    @Test
    fun copiesZeroSliceSidecar() {
        val filesDir = Files.createTempDirectory("nf-bind-slice").toFile()
        val projects = java.io.File(filesDir, "projects").apply { mkdirs() }
        java.io.File(projects, "p.nfproject.json").writeText("{}")
        val draft = java.io.File(filesDir, "draft.json").apply { writeText("{}") }
        java.io.File(filesDir, "draft.zero-slice.json").writeText("{\"slot_values\":{\"SLT-01\":\"x\"}}")
        DraftProjectBinder.bind(filesDir, "p", draft)
        val copied = java.io.File(java.io.File(projects, "p"), "authoring/zero-slice.json")
        assertTrue(copied.isFile)
        assertTrue(copied.readText().contains("SLT-01"))
    }

    @Test(expected = IllegalArgumentException::class)
    fun rejectsMissingProject() {
        val filesDir = Files.createTempDirectory("nf-bind-missing").toFile()
        DraftProjectBinder.bindSpec(filesDir, "absent", "{}")
    }
}
