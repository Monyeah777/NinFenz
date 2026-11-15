package dev.ninfenz.studio.core

import com.sun.jna.Library
import com.sun.jna.Native
import com.sun.jna.Pointer
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import java.io.File
import java.nio.file.Files

/**
 * Windows JNA 桥：加载 nf_app_core.dll（构建时由 Gradle copyCoreNative 复制到 resources/native）。
 * 查找顺序：-Dnf.core.dll 显式路径 → classpath 资源 → 仓库相对路径（开发期）。
 */
class CoreBridgeJna : CoreBridge {

    private interface NativeLib : Library {
        fun nf_app_core_abi_version(): Pointer?
        fun nf_app_core_call(reqJson: String): Pointer?
        fun nf_app_core_free(ptr: Pointer?)
    }

    private val lib: NativeLib?
    private val diagnostic: String?

    init {
        var loaded: NativeLib? = null
        var failure: String? = null
        val candidate = locateDll()
        if (candidate == null) {
            failure = "找不到 nf_app_core.dll（resources/native、-Dnf.core.dll、../core/target/release 均无）"
        } else {
            try {
                loaded = Native.load(candidate.absolutePath, NativeLib::class.java)
            } catch (t: Throwable) {
                failure = "加载 " + candidate.absolutePath + " 失败：" + (t.message ?: t.javaClass.simpleName)
            }
        }
        lib = loaded
        diagnostic = failure
    }

    override val backendName: String = "jna-native"

    override fun abiVersion(): String? = lib?.let {
        try {
            readUtf8(it.nf_app_core_abi_version())
        } catch (t: Throwable) {
            null
        }
    }

    override fun loadDiagnostic(): String? = diagnostic

    override suspend fun call(op: String, payload: JsonObject): CoreResponse = withContext(Dispatchers.IO) {
        val native = lib ?: return@withContext CoreResponse.failure(
            "NF-E-005",
            "共享核心原生库不可用：" + (diagnostic ?: "未打包"),
            "cd app/core && cargo build --release；构建 Studio 时 copyCoreNative 会自动打包 nf_app_core.dll",
            4
        )
        val request = buildJsonObject {
            put("op", op)
            put("in", payload)
        }.toString()
        val handle: Pointer = try {
            native.nf_app_core_call(request)
        } catch (t: Throwable) {
            return@withContext CoreResponse.failure("NF-E-005", "核心调用失败（JNA）：" + (t.message ?: t.javaClass.simpleName),
                "确认 DLL 与 JDK 位数一致（x64），查看 stderr 日志", 4)
        } ?: return@withContext CoreResponse.failure("NF-E-005", "核心返回 NULL（panic 兜底）", "查看核心 stderr 诊断", 4)
        val text = try {
            readUtf8(handle)
        } finally {
            try {
                native.nf_app_core_free(handle)
            } catch (t: Throwable) {
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
        fun locateDll(): File? {
            val explicit = System.getProperty("nf.core.dll")
            if (!explicit.isNullOrBlank()) {
                val f = File(explicit)
                if (f.isFile) return f
            }
            var resource = CoreBridgeJna::class.java.getResourceAsStream("/native/nf_app_core.dll")
            if (resource == null) resource = CoreBridgeJna::class.java.getResourceAsStream("/nf_app_core.dll")
            if (resource != null) {
                try {
                    val dir = Files.createTempDirectory("nf-studio-core").toFile()
                    val target = File(dir, "nf_app_core.dll")
                    resource.use { input -> target.outputStream().use { output -> input.copyTo(output) } }
                    target.deleteOnExit()
                    return target
                } catch (t: Throwable) {
                    System.err.println("解包 nf_app_core.dll 失败: " + (t.message ?: t.javaClass.simpleName))
                }
            }
            val cwd = File(System.getProperty("user.dir"))
            val relative = listOf(
                "../core/target/release/nf_app_core.dll",
                "../../core/target/release/nf_app_core.dll",
                "core/target/release/nf_app_core.dll",
                "../core/target/debug/nf_app_core.dll"
            )
            for (path in relative) {
                val f = File(cwd, path)
                if (f.isFile) return f
            }
            return null
        }
    }
}

/** 进程内单例（UI 与 TUI 面板共用同一桥）。 */
object Core {
    val bridge: CoreBridge by lazy {
        val jna = CoreBridgeJna()
        if (jna.abiVersion() != null) jna else {
            val reason = jna.loadDiagnostic() ?: "原生桥不可用"
            MissingCoreBridge(reason)
        }
    }

    fun nativeReady(): Boolean = bridge.abiVersion() != null
}
