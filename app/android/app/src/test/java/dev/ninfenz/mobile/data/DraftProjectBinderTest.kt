package dev.ninfenz.mobile.data

import java.io.File
import java.nio.file.Files
import org.junit.Assert.assertTrue
import org.junit.Test

class DraftProjectBinderTest {
    @Test
    fun copiesDraftIntoProjectAuthoring() {
        val root = Files.createTempDirectory("nf-draft-project").toFile()
        File(root, "projects").mkdirs()
        File(root, "projects/p.nfproject.json").writeText("{}")
        val draft = File(root, "draft.json").apply { writeText("{\"schema\":\"nf-import/1\"}") }
        val target = DraftProjectBinder.bind(root, "p", draft)
        assertTrue(target.isFile)
        assertTrue(target.path.contains("projects"))
        assertTrue(target.path.contains("authoring"))
        assertTrue(target.readText().contains("nf-import/1"))
    }

    @Test
    fun rejectsMissingProjectOrDraft() {
        val root = Files.createTempDirectory("nf-draft-project-2").toFile()
        val draft = File(root, "draft.json").apply { writeText("x") }
        assertTrue(runCatching { DraftProjectBinder.bind(root, "missing", draft) }.isFailure)
        File(root, "projects").mkdirs()
        File(root, "projects/p.nfproject.json").writeText("{}")
        assertTrue(runCatching { DraftProjectBinder.bind(root, "p", File(root, "missing.json")) }.isFailure)
    }
}
