package dev.ninfenz.mobile.data

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.pdf.PdfDocument
import android.view.View
import android.view.ContextThemeWrapper
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.core.graphics.createBitmap
import androidx.core.graphics.withClip
import java.io.File
import kotlin.math.ceil
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

/**
 * HTML/CSS -> PDF：用系统 WebView 渲染（JS/网络/文件访问全关），绘制到 PdfDocument。
 * 失败或被判定为空白时返回 null，调用方回退基础文本 PDF。
 */
object WebPdfExporter {
    data class Created(val file: File, val pages: Int, val bytes: Long)

    data class SecurityConfig(
        val javaScriptEnabled: Boolean,
        val blockNetworkLoads: Boolean,
        val allowFileAccess: Boolean,
        val allowContentAccess: Boolean
    )

    fun securityConfig() = SecurityConfig(
        javaScriptEnabled = false,
        blockNetworkLoads = true,
        allowFileAccess = false,
        allowContentAccess = false
    )

    fun pageCount(contentHeight: Int, width: Int): Int {
        require(width > 0) { "width 必须为正" }
        if (contentHeight <= 0) return 1
        val pageWidth = 595
        val pageHeight = 842
        val scale = pageWidth.toFloat() / width
        val perPage = pageHeight / scale
        return ceil(contentHeight / perPage).toInt().coerceIn(1, 200)
    }

    suspend fun export(
        context: Context,
        markdown: String,
        title: String,
        outDir: File
    ): Created? = withContext(Dispatchers.Main) {
        var web: WebView? = null
        try {
            val html = HtmlExporter.html(markdown, title)
            val view = WebView(ContextThemeWrapper(context, android.R.style.Theme_DeviceDefault_Light))
            web = view
            val security = securityConfig()
            view.settings.javaScriptEnabled = security.javaScriptEnabled
            view.settings.blockNetworkLoads = security.blockNetworkLoads
            view.settings.allowFileAccess = security.allowFileAccess
            view.settings.allowContentAccess = security.allowContentAccess
            view.settings.loadsImagesAutomatically = true
            view.setBackgroundColor(Color.WHITE)
            withTimeout(8_000) {
                suspendCancellableCoroutine<Unit> { cont ->
                    view.webViewClient = object : WebViewClient() {
                        override fun onPageFinished(v: WebView?, url: String?) {
                            if (cont.isActive) cont.resume(Unit)
                        }

                        override fun onReceivedError(v: WebView?, request: WebResourceRequest?, error: WebResourceError?) {
                            if (cont.isActive) cont.resumeWithException(IllegalStateException("webview load error"))
                        }
                    }
                    view.loadDataWithBaseURL(null, html, "text/html", "UTF-8", null)
                }
            }
            val width = 794
            view.measure(
                View.MeasureSpec.makeMeasureSpec(width, View.MeasureSpec.EXACTLY),
                View.MeasureSpec.makeMeasureSpec(0, View.MeasureSpec.UNSPECIFIED)
            )
            val height = maxOf(view.measuredHeight, view.contentHeight)
            if (height <= 0) return@withContext null
            view.layout(0, 0, width, height)
            if (isBlank(view, width, height)) return@withContext null

            val pageWidth = 595
            val pageHeight = 842
            val scale = pageWidth.toFloat() / width
            val perPage = pageHeight / scale
            val pageCount = pageCount(height, width)
            outDir.mkdirs()
            val target = File(outDir, "result.pdf")
            val doc = PdfDocument()
            try {
                for (i in 0 until pageCount) {
                    val page = doc.startPage(PdfDocument.PageInfo.Builder(pageWidth, pageHeight, i + 1).create())
                    val canvas = page.canvas
                    canvas.drawColor(Color.WHITE)
                    canvas.withClip(0f, 0f, pageWidth.toFloat(), pageHeight.toFloat()) {
                        scale(scale, scale)
                        translate(0f, -i * perPage)
                        view.draw(this)
                    }
                    doc.finishPage(page)
                }
                target.outputStream().use { doc.writeTo(it) }
            } finally {
                doc.close()
            }
            Created(target, pageCount, target.length())
        } catch (t: Throwable) {
            null
        } finally {
            web?.destroy()
        }
    }

    private fun isBlank(view: WebView, width: Int, height: Int): Boolean {
        return try {
            val probeHeight = minOf(height, 1200)
            val bitmap = createBitmap(width, probeHeight)
            val canvas = Canvas(bitmap)
            canvas.drawColor(Color.WHITE)
            view.draw(canvas)
            val pixels = IntArray(width * probeHeight)
            bitmap.getPixels(pixels, 0, width, 0, 0, width, probeHeight)
            bitmap.recycle()
            pixels.count { it != Color.WHITE } < 100
        } catch (t: Throwable) {
            true
        }
    }
}
