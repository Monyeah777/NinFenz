package dev.ninfenz.mobile.model

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class FlashFillModelTest {
    @Test
    fun infersUpperAndTrim() {
        assertEquals("upper", FlashFillModel.infer("Hello", "HELLO")?.kind)
        assertEquals("trim", FlashFillModel.infer("  Hi  ", "Hi")?.kind)
    }

    @Test
    fun suffix() {
        assertEquals(FlashFillModel.Transform("suffix", "！"), FlashFillModel.infer("标题", "标题！"))
    }

    @Test
    fun prefix() {
        assertEquals(FlashFillModel.Transform("prefix", "【"), FlashFillModel.infer("文", "【文"))
    }

    @Test
    fun stripPrefix() {
        assertEquals(FlashFillModel.Transform("strip_prefix", "# "), FlashFillModel.infer("# 文", "文"))
    }

    @Test
    fun stripSuffix() {
        assertEquals(FlashFillModel.Transform("strip_suffix", "！"), FlashFillModel.infer("文！", "文"))
    }

    @Test
    fun truncate() {
        assertEquals(FlashFillModel.Transform("strip_suffix", "def"), FlashFillModel.infer("abcdef", "abc"))
    }

    @Test
    fun replace() {
        assertEquals(FlashFillModel.Transform("replace", "报名", "登记"), FlashFillModel.infer("请报名", "请登记"))
    }

    @Test
    fun multiExamplePrefix() {
        assertEquals(
            FlashFillModel.Transform("prefix", "【"),
            FlashFillModel.infer(listOf("文" to "【文", "章" to "【章"))
        )
    }

    @Test
    fun multiExampleReplace() {
        assertEquals(
            FlashFillModel.Transform("replace", "报名", "登记"),
            FlashFillModel.infer(listOf("请报名" to "请登记", "报名截止" to "登记截止"))
        )
    }

    @Test
    fun multiExampleDisambiguatesTruncate() {
        assertEquals(
            FlashFillModel.Transform("truncate", "3"),
            FlashFillModel.infer(listOf("abcdef" to "abc", "xyz123" to "xyz"))
        )
    }

    @Test
    fun multiExampleInconsistent() {
        assertNull(FlashFillModel.infer(listOf("a" to "【a", "b" to "b】")))
    }

    @Test
    fun noRule() {
        assertNull(FlashFillModel.infer("a", "b"))
    }
}
