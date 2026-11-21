package dev.ninfenz.mobile.model

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class NfPatchTest {
    private fun patch(json: String) = NfPatchModel.parse(json)

    @Test
    fun replaceInsertMoveDelete() {
        val md = "一\n\n二\n\n三"
        val result = NfPatchModel.apply(md, patch("""{"schema":"nf-patch/1","ops":[
            {"op":"replace","block_id":"b2","text":"新二"},
            {"op":"insert","after_block_id":"b2","text":"插入"},
            {"op":"move","block_id":"b3","index":0},
            {"op":"delete","block_id":"b1"}
        ]}"""))
        assertEquals(4, result.applied)
        assertEquals(4, result.changes.size)
        assertEquals("二", result.changes.first { it.op == "replace" }.before)
        assertEquals("新二", result.changes.first { it.op == "replace" }.after)
        assertTrue(result.rejected.isEmpty())
        assertEquals("三\n\n新二\n\n插入", result.markdown)
    }

    @Test
    fun stableIdsAfterInsert() {
        val md = "一\n\n二\n\n三"
        val result = NfPatchModel.apply(md, patch("""{"schema":"nf-patch/1","ops":[
            {"op":"insert","index":0,"text":"零"},
            {"op":"replace","block_id":"b3","text":"新三"}
        ]}"""))
        assertEquals("零\n\n一\n\n二\n\n新三", result.markdown)
    }

    @Test
    fun setSlotRejectedButOtherOpsApply() {
        val result = NfPatchModel.apply("一\n\n二", patch("""{"schema":"nf-patch/1","ops":[
            {"op":"set-slot","slot":"SLT-01","text":"甲"},
            {"op":"replace","block_id":"b1","text":"新一"}
        ]}"""))
        assertEquals(1, result.applied)
        assertEquals(1, result.rejected.size)
        assertEquals("新一\n\n二", result.markdown)
    }

    @Test
    fun missingReplaceTextRejectedAtParse() {
        var failed = false
        try {
            patch("""{"schema":"nf-patch/1","ops":[{"op":"replace","block_id":"b1"}]}""")
        } catch (e: dev.ninfenz.mobile.core.ModelException) {
            failed = true
            assertEquals("NF-E-002", e.code)
        }
        assertTrue(failed)
    }
}
