package dev.ninfenz.mobile.core

import com.sun.jna.Library
import com.sun.jna.Native
import com.sun.jna.Pointer
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

/**
 * C ABI（app/docs/CLI.md §5）：
 *   const char* nf_app_core_abi_version(void)
 *   char*       nf_app_core_call(const char* req_json)
 *   void        nf_app_core_free(char* ptr)
 */
private interface CoreNativeLib : Library {
    fun nf_app_core_abi_version(): Pointer?
    fun nf_app_core_call(reqJson: String): Pointer?
    fun nf_app_core_free(ptr: Pointer?)
}

/**
 * JNA 原生桥。libnf_app_core.so 由 app/scripts/build_core_android.sh 交叉编译进
 * app/src/main/jniLibs/{arm64-v8a,x86_64}/；缺失时构造不抛、调用报 NF-E-005。
 */
class CoreBridgeNative(
    private val libraryName: String = "nf_app_core"
) : CoreBridge {

    private val loadFailure: String?
    private val lib: CoreNativeLib?

    init {
        var loaded: CoreNativeLib? = null
        var failure: String? = null
        try {
            loaded = Native.load(libraryName, CoreNativeLib::class.java)
        } catch (t: Throwable) {
            failure = t.message ?: t.javaClass.simpleName
        }
        lib = loaded
        loadFailure = failure
    }

    override val backendName: String = "jna-native"

    override fun abiVersion(): String? {
        val l = lib ?: return null
        return try {
            readUtf8(l.nf_app_core_abi_version())
        } catch (t: Throwable) {
            null
        }
    }

    override suspend fun call(op: String, payload: JsonObject): CoreResponse = withContext(Dispatchers.IO) {
        val l = lib ?: return@withContext CoreResponse.failure(
            "NF-E-005",
            "共享核心原生库缺失或加载失败（libnf_app_core.so）：" + (loadFailure ?: "未打包"),
            GUIDANCE
        )
        val request = buildJsonObject {
            put("op", op)
            put("in", payload)
        }.toString()
        val handle: Pointer = try {
            l.nf_app_core_call(request)
        } catch (t: Throwable) {
            return@withContext CoreResponse.failure(
                "NF-E-005",
                "核心调用失败（JNA）：" + (t.message ?: t.javaClass.simpleName),
                "确认 .so 与 APP ABI 一致（arm64-v8a / x86_64），并检查 logcat"
            )
        } ?: return@withContext CoreResponse.failure(
            "NF-E-005",
            "核心返回 NULL（panic 兜底），stderr 应留诊断",
            "查看 logcat 中的 nf-app-core stderr；重跑 nf-app-core selftest"
        )
        val text = try {
            readUtf8(handle)
        } finally {
            try {
                l.nf_app_core_free(handle)
            } catch (t: Throwable) {
                // 释放失败不影响响应语义，但记录不吞：诊断走 stderr
                System.err.println("nf_app_core_free 失败: " + (t.message ?: t.javaClass.simpleName))
            }
        }
        CoreResponse.fromEnvelope(text ?: "")
    }

    private fun readUtf8(ptr: Pointer?): String? {
        if (ptr == null) return null
        return ptr.getString(0, "UTF-8")
    }

    companion object {
        const val GUIDANCE: String =
            "修复：bash app/scripts/build_core_android.sh（需要 NDK + rustup target aarch64-linux-android/x86_64-linux-android）" +
                "，把 libnf_app_core.so 放进 app/src/main/jniLibs/ 后重装 APK。工具链缺失时脚本 exit 4 并给安装指引。"
    }
}
