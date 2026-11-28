package dev.ninfenz.mobile.data

import android.content.Context
import dev.ninfenz.mobile.R
import com.google.android.play.core.splitinstall.SplitInstallManagerFactory
import com.google.android.play.core.splitinstall.SplitInstallRequest
import java.io.File
import java.lang.reflect.InvocationTargetException

/** 基础包不直接依赖 MLKit；OCR 实现在 :feature:ocr 动态模块中。 */
internal object OcrFeatureBridge {
    private const val CLASS = "dev.ninfenz.mobile.ocr.OcrFeature"

    fun call(method: String, context: Context, file: File): Any? {
        try {
            val clazz = Class.forName(CLASS)
            val target = clazz.getMethod(method, Context::class.java, File::class.java)
            return target.invoke(null, context, file)
        } catch (t: Throwable) {
            val cause = (t as? InvocationTargetException)?.targetException ?: t
            android.util.Log.w("NfOcr", "OCR 反射调用失败", cause)
            runCatching {
                SplitInstallManagerFactory.create(context).startInstall(
                    SplitInstallRequest.newBuilder().addModule("ocr").build()
                )
            }
            throw IllegalStateException(context.getString(R.string.ocr_feature_installing), cause)
        }
    }
}
