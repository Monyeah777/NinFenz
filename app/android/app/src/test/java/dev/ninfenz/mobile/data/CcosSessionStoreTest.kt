package dev.ninfenz.mobile.data

import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class CcosSessionStoreTest {
    @Test
    fun savesAndLoadsTaskAndResult() {
        val dir = Files.createTempDirectory("nf-ccos-session").toFile()
        CcosSessionStore.saveTask(dir, "task")
        CcosSessionStore.saveResult(dir, "result")
        assertEquals("task", CcosSessionStore.loadTask(dir))
        assertEquals("result", CcosSessionStore.loadResult(dir))
    }

    @Test
    fun clearResultKeepsTask() {
        val dir = Files.createTempDirectory("nf-ccos-clear").toFile()
        CcosSessionStore.saveTask(dir, "task")
        CcosSessionStore.saveResult(dir, "result")
        CcosSessionStore.clearResult(dir)
        assertEquals("task", CcosSessionStore.loadTask(dir))
        assertNull(CcosSessionStore.loadResult(dir))
    }

    @Test
    fun clearAllRemovesBoth() {
        val dir = Files.createTempDirectory("nf-ccos-clear-all").toFile()
        CcosSessionStore.saveTask(dir, "task")
        CcosSessionStore.saveResult(dir, "result")
        CcosSessionStore.clearAll(dir)
        assertNull(CcosSessionStore.loadTask(dir))
        assertNull(CcosSessionStore.loadResult(dir))
    }

    @Test
    fun missingFilesReturnNull() {
        val dir = Files.createTempDirectory("nf-ccos-empty").toFile()
        assertNull(CcosSessionStore.loadTask(dir))
        assertNull(CcosSessionStore.loadResult(dir))
    }
}
