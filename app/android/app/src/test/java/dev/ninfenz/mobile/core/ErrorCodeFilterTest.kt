package dev.ninfenz.mobile.core

import org.junit.Assert.assertEquals
import org.junit.Test

class ErrorCodeFilterTest {
    private val entries = listOf(
        ErrorCodeEntry("NF-IMP-001", "error", 3, "内容无法识别", "换格式"),
        ErrorCodeEntry("NF-EXP-004", "error", 4, "导出器不可用", "安装导出器")
    )

    @Test
    fun emptyQueryKeepsAll() {
        assertEquals(2, ErrorCodeFilter.apply(entries, "").size)
        assertEquals(2, ErrorCodeFilter.apply(entries, "  ").size)
    }

    @Test
    fun filtersByCodeMessageAndFixCaseInsensitive() {
        assertEquals(listOf("NF-IMP-001"), ErrorCodeFilter.apply(entries, "imp").map { it.code })
        assertEquals(listOf("NF-IMP-001"), ErrorCodeFilter.apply(entries, "内容").map { it.code })
        assertEquals(listOf("NF-EXP-004"), ErrorCodeFilter.apply(entries, "导出器").map { it.code })
    }
}
