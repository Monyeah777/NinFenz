package dev.ninfenz.mobile.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class HtmlImporterTest {
    @Test
    fun convertsHeadingsListsAndEntities() {
        val md = HtmlImporter.toMarkdown(
            "<html><body><h1>标题</h1><p>A &amp; B</p><ul><li>一</li><li>二</li></ul></body></html>"
        )
        assertTrue(md.contains("# 标题"))
        assertTrue(md.contains("A & B"))
        assertTrue(md.contains("- 一"))
        assertTrue(md.contains("- 二"))
    }

    @Test
    fun convertsTablesAndLinks() {
        val md = HtmlImporter.toMarkdown(
            "<table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table>" +
                "<p><a href=\"https://example.com\">官网</a></p>"
        )
        assertTrue(md.contains("| A | B |"))
        assertTrue(md.contains("| 1 | 2 |"))
        assertTrue(md.contains("[官网](https://example.com)"))
    }

    @Test
    fun convertsOrderedList() {
        val md = HtmlImporter.toMarkdown("<ol><li>一</li><li>二</li></ol>")
        assertTrue(md.contains("1. 一"))
        assertTrue(md.contains("2. 二"))
    }

    @Test
    fun convertsImages() {
        val md = HtmlImporter.toMarkdown("<p><img src=\"a.png\" alt=\"图\"/></p>")
        assertTrue(md.contains("![图](a.png)"))
    }

    @Test
    fun convertsCodeBlocks() {
        val md = HtmlImporter.toMarkdown("<pre><code>val x = 1</code></pre><p>使用 <code>nf</code></p>")
        assertTrue(md.contains("```"))
        assertTrue(md.contains("val x = 1"))
        assertTrue(md.contains("`nf`"))
    }

    @Test
    fun convertsBlockquote() {
        val md = HtmlImporter.toMarkdown("<blockquote>引用</blockquote>")
        assertTrue(md.contains("> 引用"))
    }

    @Test
    fun convertsHorizontalRule() {
        val md = HtmlImporter.toMarkdown("<p>上</p><hr/><p>下</p>")
        assertTrue(md.contains("---"))
    }

    @Test
    fun removesScriptAndStyle() {
        val md = HtmlImporter.toMarkdown("<style>x{}</style><script>alert(1)</script><p>正文</p>")
        assertTrue(md.contains("正文"))
        assertTrue(!md.contains("alert"))
        assertTrue(!md.contains("x{}"))
    }
}
