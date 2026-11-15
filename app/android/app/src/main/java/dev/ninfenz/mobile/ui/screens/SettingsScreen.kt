package dev.ninfenz.mobile.ui.screens

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import dev.ninfenz.mobile.BuildConfig
import dev.ninfenz.mobile.core.Core
import dev.ninfenz.mobile.core.CoreBridgeNative
import dev.ninfenz.mobile.core.ErrorCatalog
import dev.ninfenz.mobile.ui.components.CardBox
import dev.ninfenz.mobile.ui.components.KeyValue
import dev.ninfenz.mobile.ui.components.MonoText
import dev.ninfenz.mobile.ui.components.NfScaffold
import dev.ninfenz.mobile.ui.components.Notice
import dev.ninfenz.mobile.ui.components.Tone

@Composable
fun SettingsScreen(onBack: () -> Unit) {
    val context = LocalContext.current
    val diag = remember { Core.diagnostics() }
    var copied by remember { mutableStateOf(false) }

    val diagnosticsText = buildString {
        appendLine("app=dev.ninfenz.mobile " + BuildConfig.VERSION_NAME + " (" + BuildConfig.VERSION_CODE + ")")
        appendLine("android=" + android.os.Build.VERSION.RELEASE + " sdk=" + android.os.Build.VERSION.SDK_INT)
        appendLine("abi=" + android.os.Build.SUPPORTED_ABIS.joinToString(","))
        appendLine("core.backend=" + diag.backend)
        appendLine("core.abi=" + (diag.abiVersion ?: "unavailable"))
        appendLine("core.nativeReady=" + diag.nativeReady)
        appendLine("errorCatalog.loaded=" + diag.errorCatalogLoaded + " count=" + diag.errorCodeCount)
        appendLine("telemetry=none network=denied account=none")
    }

    NfScaffold(title = "Settings · 诊断/隐私", onBack = onBack) {
        CardBox(title = "核心诊断") {
            KeyValue("backend", diag.backend)
            KeyValue("ABI 版本", diag.abiVersion ?: "不可用")
            KeyValue("原生库", if (diag.nativeReady) "已加载" else "缺失")
            KeyValue("错误码登记", if (diag.errorCatalogLoaded) diag.errorCodeCount.toString() + " 条" else "未打包")
            if (!diag.nativeReady) {
                Notice("NF-E-005：共享核心原生库不可用。\n" + CoreBridgeNative.GUIDANCE, Tone.ERROR)
            }
            Text(
                text = "错误码文本取自 app/schema/error_codes.json（构建时复制为资源）；登记条数 = " + ErrorCatalog.all().size,
                style = MaterialTheme.typography.bodySmall
            )
        }

        CardBox(title = "隐私说明") {
            Text("• 全部处理在本机；APP 未声明 INTERNET 权限。", style = MaterialTheme.typography.bodySmall)
            Text("• 无遥测、无账号、无云端同步；不直连任何 API。", style = MaterialTheme.typography.bodySmall)
            Text("• 诊断信息只落本机（本页手动复制/分享）。", style = MaterialTheme.typography.bodySmall)
            Text("• 分享只读 URI 限于 app cache/shared，可随时清理。", style = MaterialTheme.typography.bodySmall)
            Text("• 密钥只属于 CCOS 执行面；APP 侧拒绝含密钥字段的 ccos-task/result（NF-CCOS-003）。", style = MaterialTheme.typography.bodySmall)
        }

        CardBox(title = "诊断信息") {
            MonoText(diagnosticsText)
            Button(onClick = {
                val manager = context.getSystemService(Context.CLIPBOARD_SERVICE) as? ClipboardManager
                manager?.setPrimaryClip(ClipData.newPlainText("NF Mobile diagnostics", diagnosticsText))
                copied = true
            }) {
                Text(if (copied) "已复制到剪贴板" else "复制诊断信息")
            }
        }
    }
}
