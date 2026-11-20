package dev.ninfenz.mobile.model

import org.junit.Assert.assertTrue
import org.junit.Test

class CsvTableTest {
    @Test
    fun detectsSemicolonAndTab() {
        val semi = CsvTable.toMarkdown("a;b\n1;2")
        assertTrue(semi.startsWith("| a | b |"))
        assertTrue(semi.contains("| 1 | 2 |"))
        val directive = CsvTable.toMarkdown("sep=;\na;b\n1;2")
        assertTrue(directive.startsWith("| a | b |"))
        val tab = CsvTable.toMarkdown("a\tb\n1\t2")
        assertTrue(tab.startsWith("| a | b |"))
        assertTrue(tab.contains("| 1 | 2 |"))
    }

    @Test
    fun delimiterDetectionIgnoresQuotedCommas() {
        val table = CsvTable.toMarkdown("\"a,b\";c\n1;2")
        assertTrue(table.startsWith("| a,b | c |"))
        assertTrue(table.contains("| 1 | 2 |"))
    }

    @Test
    fun convertsQuotedCsv() {
        val table = CsvTable.toMarkdown("name,note\nA,\"x,y\"\nB,z")
        assertTrue(table.startsWith("| name | note |"))
        assertTrue(table.contains("| A | x,y |"))
    }
}
