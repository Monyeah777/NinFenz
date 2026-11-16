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
    fun decodesMetaCharset() {
        val bytes = "<meta charset=\"gbk\"><p>中文</p>".toByteArray(java.nio.charset.Charset.forName("GBK"))
        assertTrue(HtmlImporter.decode(bytes).contains("中文"))
        assertTrue(HtmlImporter.decode("<p>utf8 中文</p>".toByteArray()).contains("utf8 中文"))
    }

    @Test
    fun convertsBoldAndItalic() {
        val md = HtmlImporter.toMarkdown("<p><strong>粗</strong>与<em>斜</em></p>")
        assertTrue(md.contains("**粗**"))
        assertTrue(md.contains("*斜*"))
    }

    @Test
    fun convertsStrikethrough() {
        val md = HtmlImporter.toMarkdown("<p><del>旧</del></p>")
        assertTrue(md.contains("~~旧~~"))
    }

    @Test
    fun decodesNumericEntities() {
        assertTrue(HtmlImporter.toMarkdown("<p>&#20320;&#x597d;</p>").contains("你好"))
    }

    @Test
    fun respectsOrderedListStart() {
        val md = HtmlImporter.toMarkdown("<ol start=\"3\"><li>三</li><li>四</li></ol>")
        assertTrue(md.contains("3. 三"))
        assertTrue(md.contains("4. 四"))
    }

    @Test
    fun convertsNestedList() {
        val md = HtmlImporter.toMarkdown("<ul><li>父<ul><li>子</li></ul></li></ul>")
        assertTrue(md.contains("- 父"))
        assertTrue(md.contains("  - 子"))
    }

    @Test
    fun convertsNestedOrderedList() {
        val md = HtmlImporter.toMarkdown("<ol><li>一<ol><li>a</li></ol></li><li>二</li></ol>")
        assertTrue(md.contains("1. 一"))
        assertTrue(md.contains("  1. a"))
        assertTrue(md.contains("2. 二"))
    }

    @Test
    fun keepsInlineFormattingInsideList() {
        val md = HtmlImporter.toMarkdown("<ul><li><strong>粗</strong> <a href=\"https://e\">链</a></li></ul>")
        assertTrue(md.contains("- **粗** [链](https://e)"))
    }

    @Test
    fun keepsInlineFormattingInTable() {
        val md = HtmlImporter.toMarkdown("<table><tr><td><strong>粗</strong></td><td><a href=\"https://e\">链</a></td></tr></table>")
        assertTrue(md.contains("| **粗** | [链](https://e) |"))
    }

    @Test
    fun removesScriptAndStyle() {
        val md = HtmlImporter.toMarkdown("<style>x{}</style><script>alert(1)</script><p>正文</p>")
        assertTrue(md.contains("正文"))
        assertTrue(!md.contains("alert"))
        assertTrue(!md.contains("x{}"))
    }
}
