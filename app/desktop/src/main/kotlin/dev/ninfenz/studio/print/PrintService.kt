package dev.ninfenz.studio.print

import dev.ninfenz.studio.render.MarkdownRenderer
import java.awt.Graphics
import java.awt.Graphics2D
import java.awt.print.PageFormat
import java.awt.print.Printable
import java.awt.print.PrinterJob
import java.io.File
import java.nio.file.Files

/**
 * 打印出口：javax.print 纯文本分页打印，或生成 HTML 交给系统打印。
 * 无打印机 / headless 时返回失败原因，不假装打印成功。
 */
object PrintService {

    data class PrintResult(val ok: Boolean, val message: String)

    fun printPlainText(jobName: String, text: String): PrintResult = try {
        val job = PrinterJob.getPrinterJob()
        job.jobName = jobName
        job.setPrintable(TextPrintable(text))
        job.print()
        PrintResult(true, "已提交到打印机：" + job.printService.name)
    } catch (t: Throwable) {
        PrintResult(false, "打印失败：" + (t.message ?: t.javaClass.simpleName))
    }

    fun writeHtml(markdown: String, name: String): File {
        val dir = Files.createTempDirectory("nf-studio-print").toFile()
        val file = File(dir, name + ".html")
        file.writeText(MarkdownRenderer.toHtml(markdown), Charsets.UTF_8)
        return file
    }

    private class TextPrintable(private val text: String) : Printable {
        override fun print(graphics: Graphics, pageFormat: PageFormat, pageIndex: Int): Int {
            val g = graphics as Graphics2D
            val font = g.font.deriveFont(10f)
            g.font = font
            val metrics = g.fontMetrics
            val lineHeight = metrics.height + 2
            val pageHeight = pageFormat.imageableHeight.toInt()
            val pageWidth = pageFormat.imageableWidth.toInt()
            val linesPerPage = maxOf(1, pageHeight / lineHeight)
            val lines = text.lines()
            val start = pageIndex * linesPerPage
            if (start >= lines.size) return Printable.NO_SUCH_PAGE
            g.translate(pageFormat.imageableX, pageFormat.imageableY)
            var y = metrics.ascent
            var i = start
            while (i < lines.size && i < start + linesPerPage) {
                var line = lines[i]
                while (line.length > 1 && metrics.stringWidth(line) > pageWidth) {
                    line = line.substring(0, line.length - 1)
                }
                g.drawString(line, 0, y)
                y += lineHeight
                i++
            }
            return Printable.PAGE_EXISTS
        }
    }
}
