package dev.ninfenz.mobile.model

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class FlashFillModelTest {
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
    fun noRule() {
        assertNull(FlashFillModel.infer("a", "b"))
    }
}
