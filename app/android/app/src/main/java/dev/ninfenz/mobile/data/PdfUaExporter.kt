package dev.ninfenz.mobile.data

import android.content.Context
import com.tom_roush.pdfbox.cos.COSArray
import com.tom_roush.pdfbox.cos.COSDictionary
import com.tom_roush.pdfbox.cos.COSInteger
import com.tom_roush.pdfbox.cos.COSName
import com.tom_roush.pdfbox.pdmodel.PDDocument
import com.tom_roush.pdfbox.pdmodel.PDDocumentInformation
import com.tom_roush.pdfbox.pdmodel.PDPage
import com.tom_roush.pdfbox.pdmodel.PDPageContentStream
import com.tom_roush.pdfbox.pdmodel.PDResources
import com.tom_roush.pdfbox.pdmodel.common.PDMetadata
import com.tom_roush.pdfbox.pdmodel.documentinterchange.logicalstructure.PDMarkInfo
import com.tom_roush.pdfbox.pdmodel.documentinterchange.logicalstructure.PDStructureElement
import com.tom_roush.pdfbox.pdmodel.documentinterchange.logicalstructure.PDStructureTreeRoot
import com.tom_roush.pdfbox.pdmodel.documentinterchange.markedcontent.PDPropertyList
import com.tom_roush.pdfbox.pdmodel.documentinterchange.taggedpdf.StandardStructureTypes
import com.tom_roush.pdfbox.pdmodel.font.PDType0Font
import java.io.ByteArrayInputStream
import java.io.File

/** 基础 PDF/UA 结构导出：每块一页，带 StructTreeRoot/ParentTree/MCID/语言/标题。 */
object PdfUaExporter {
    data class Created(val file: File, val pages: Int, val bytes: Long)

    private data class BlockPage(
        val page: PDPage,
        val block: PdfMarkdown.Block,
        val pageIndex: Int,
        val headingLevel: Int
    )

    private fun xml(s: String): String = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\"", "&quot;")

    fun export(context: Context, markdown: String, title: String, outDir: File): Created {
        val doc = PDDocument()
        val loaded = PdfFontProvider.load(doc, context)
        return try {
            exportLoaded(doc, loaded.font, markdown, title, outDir)
        } finally {
            loaded.closeable?.close()
        }
    }

    fun export(fontBytes: ByteArray, markdown: String, title: String, outDir: File): Created {
        val doc = PDDocument()
        val font = PDType0Font.load(doc, ByteArrayInputStream(fontBytes))
        return exportLoaded(doc, font, markdown, title, outDir)
    }

    private fun exportLoaded(doc: PDDocument, font: PDType0Font, markdown: String, title: String, outDir: File): Created {
        outDir.mkdirs()
        val target = File(outDir, "result-ua.pdf")
        val tree = PDStructureTreeRoot()
        doc.documentCatalog.structureTreeRoot = tree
        val root = PDStructureElement(StandardStructureTypes.DOCUMENT, null)
        tree.appendKid(root)
        val parentNums = COSArray()
        val blocks = PdfMarkdown.blocks(markdown)
        var pageIndex = 0
        var lastHeading = 0
        for (b in blocks) {
            if (b.text.isBlank() && b.image == null) continue
            val page = PDPage()
            doc.addPage(page)
            page.cosObject.setInt(COSName.STRUCT_PARENTS, pageIndex)
            val headingLevel = if (b.level > 0) {
                val l = if (lastHeading == 0) 1 else minOf(b.level, lastHeading + 1)
                lastHeading = l
                l
            } else 0
            writeBlockPage(doc, font, root, parentNums, BlockPage(page, b, pageIndex, headingLevel))
            pageIndex++
        }
        tree.cosObject.setItem(COSName.NUMS, parentNums)
        tree.cosObject.setInt(COSName.PARENT_TREE_NEXT_KEY, pageIndex)
        tree.cosObject.setItem(COSName.PARENT_TREE, COSDictionary().apply { setItem(COSName.NUMS, parentNums) })
        applyCatalogMetadata(doc, title)
        doc.save(target)
        doc.close()
        return Created(target, pageIndex, target.length())
    }

    private fun writeBlockPage(
        doc: PDDocument,
        font: PDType0Font,
        root: PDStructureElement,
        parentNums: COSArray,
        target: BlockPage
    ) {
        val type = when {
            target.headingLevel == 1 -> StandardStructureTypes.H1
            target.headingLevel == 2 -> StandardStructureTypes.H2
            target.headingLevel == 3 -> StandardStructureTypes.H3
            target.headingLevel >= 4 -> StandardStructureTypes.H4
            target.block.code -> StandardStructureTypes.CODE
            target.block.quote -> StandardStructureTypes.QUOTE
            target.block.bullet -> StandardStructureTypes.P
            else -> StandardStructureTypes.P
        }
        val element = PDStructureElement(type, root)
        root.appendKid(element)
        element.page = target.page
        element.setKids(listOf(0))
        val dict = COSDictionary().apply { setInt(COSName.MCID, 0) }
        val resources = PDResources()
        target.page.resources = resources
        val propName = resources.add(PDPropertyList.create(dict))
        PDPageContentStream(doc, target.page).use { cs ->
            cs.beginMarkedContentSequence(COSName.getPDFName(type), propName)
            cs.beginText()
            cs.setFont(font, if (target.headingLevel > 0) 18f else 11f)
            cs.newLineAtOffset(48f, 760f)
            val text = target.block.text.replace('\n', ' ').take(1200)
            if (text.isNotBlank()) cs.showText(text)
            cs.endText()
            cs.endMarkedContentSequence()
        }
        parentNums.add(COSInteger.get(target.pageIndex.toLong()))
        val arr = COSArray().apply { add(element.cosObject) }
        parentNums.add(arr)
    }

    private fun applyCatalogMetadata(doc: PDDocument, title: String) {
        val catalog = doc.documentCatalog
        catalog.language = "en-US"
        val mark = PDMarkInfo().apply { isMarked = true }
        catalog.markInfo = mark
        val vp = COSDictionary().apply { setBoolean(COSName.getPDFName("DisplayDocTitle"), true) }
        catalog.cosObject.setItem(COSName.getPDFName("ViewerPreferences"), vp)
        doc.documentInformation = PDDocumentInformation().apply { this.title = title }
        val xmp = """<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
<rdf:Description rdf:about="" xmlns:pdfuaid="http://www.aiim.org/pdfua/ns/id/" xmlns:dc="http://purl.org/dc/elements/1.1/">
<pdfuaid:part>1</pdfuaid:part>
<dc:title><rdf:Alt><rdf:li xml:lang="x-default">${xml(title)}</rdf:li></rdf:Alt></dc:title>
</rdf:Description>
</rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>""".trimIndent().toByteArray(Charsets.UTF_8)
        catalog.metadata = PDMetadata(doc, ByteArrayInputStream(xmp))
    }
}
