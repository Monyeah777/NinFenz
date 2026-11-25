package dev.ninfenz.mobile.data

import android.content.Context
import com.tom_roush.fontbox.ttf.TrueTypeCollection
import com.tom_roush.pdfbox.pdmodel.PDDocument
import com.tom_roush.pdfbox.pdmodel.font.PDType0Font
import java.io.Closeable
import java.io.File

/** PDF 字体优先用系统 NotoSansCJK（TTC），避免 APK 内置 17MB 全量字体；失败回退内置字体。 */
object PdfFontProvider {
    data class Loaded(val font: PDType0Font, val closeable: Closeable?)

    private val SYSTEM_TTC = listOf(
        "/system/fonts/NotoSansCJK-Regular.ttc",
        "/system/fonts/NotoSansCJKsc-Regular.ttc",
        "/system/fonts/NotoSansSC-Regular.ttf",
        "/system/fonts/NotoSansSC-Regular.otf"
    )
    private val TTC_NAMES = listOf("NotoSansCJKsc-Regular", "NotoSansCJK-Regular", "NotoSansSC-Regular")

    fun load(doc: PDDocument, context: Context): Loaded {
        for (path in SYSTEM_TTC) {
            val file = File(path)
            if (!file.isFile) continue
            try {
                if (file.extension.equals("ttc", true)) {
                    val collection = TrueTypeCollection(file)
                    for (name in TTC_NAMES) {
                        val ttf = runCatching { collection.getFontByName(name) }.getOrNull() ?: continue
                        return Loaded(PDType0Font.load(doc, ttf, true), collection)
                    }
                    collection.close()
                } else {
                    return Loaded(PDType0Font.load(doc, file), null)
                }
            } catch (_: Throwable) {
                // 继续尝试下一个
            }
        }
        val bytes = context.assets.open("fonts/NotoSansSC-VF.ttf").use { it.readBytes() }
        return Loaded(PDType0Font.load(doc, java.io.ByteArrayInputStream(bytes)), null)
    }
}
