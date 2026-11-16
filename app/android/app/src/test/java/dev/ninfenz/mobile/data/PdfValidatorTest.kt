package dev.ninfenz.mobile.data

import java.io.File
import java.nio.file.Files
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class PdfValidatorTest {
    @Test
    fun acceptsMinimalPdf() {
        val dir = Files.createTempDirectory("nf-pdf").toFile()
        val f = File(dir, "ok.pdf")
        f.writeBytes(("%PDF-1.4\n1 0 obj\n<< /Type /Page >>\nendobj\nxref\n0 1\n0000000000 65535 f \ntrailer\n<< /Size 1 >>\nstartxref\n0\n%%EOF\n").toByteArray())
        assertTrue(PdfValidator.inspect(f).ok)
    }

    @Test
    fun rejectsBrokenOrEncryptedPdf() {
        val dir = Files.createTempDirectory("nf-pdf-2").toFile()
        val f = File(dir, "bad.pdf")
        f.writeBytes("not a pdf".toByteArray())
        assertFalse(PdfValidator.inspect(f).ok)
        val enc = File(dir, "enc.pdf")
        enc.writeBytes(("%PDF-1.4\n/Encrypt\n/Type /Page\nstartxref\n0\n%%EOF\n").toByteArray())
        assertFalse(PdfValidator.inspect(enc).ok)
    }

    @Test
    fun rejectsMissingFile() {
        val dir = Files.createTempDirectory("nf-pdf-3").toFile()
        assertFalse(PdfValidator.inspect(File(dir, "no.pdf")).ok)
    }
}
