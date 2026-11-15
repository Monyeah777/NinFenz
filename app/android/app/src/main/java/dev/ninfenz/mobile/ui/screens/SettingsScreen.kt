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
import androidx.compose.ui.res.stringResource
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

    NfScaffold(title = stringResource(dev.ninfenz.mobile.R.string.settings_title), onBack = onBack) {
        CardBox(title = stringResource(dev.ninfenz.mobile.R.string.settings_core_diag)) {
            KeyValue("backend", diag.backend)
            KeyValue(stringResource(dev.ninfenz.mobile.R.string.settings_abi), diag.abiVersion ?: stringResource(dev.ninfenz.mobile.R.string.settings_abi_unavailable))
            KeyValue(stringResource(dev.ninfenz.mobile.R.string.settings_native), if (diag.nativeReady) stringResource(dev.ninfenz.mobile.R.string.settings_loaded) else stringResource(dev.ninfenz.mobile.R.string.settings_missing))
            KeyValue(stringResource(dev.ninfenz.mobile.R.string.settings_err_registry), if (diag.errorCatalogLoaded) stringResource(dev.ninfenz.mobile.R.string.settings_err_count, diag.errorCodeCount) else stringResource(dev.ninfenz.mobile.R.string.settings_not_packaged))
            if (!diag.nativeReady) {
                Notice("NF-E-005：共享核心原生库不可用。\n" + CoreBridgeNative.GUIDANCE, Tone.ERROR)
            }
            Text(
                text = stringResource(dev.ninfenz.mobile.R.string.settings_error_hint, ErrorCatalog.all().size),
                style = MaterialTheme.typography.bodySmall
            )
        }

        CardBox(title = stringResource(dev.ninfenz.mobile.R.string.settings_privacy)) {
            Text(stringResource(dev.ninfenz.mobile.R.string.settings_privacy_1), style = MaterialTheme.typography.bodySmall)
            Text(stringResource(dev.ninfenz.mobile.R.string.settings_privacy_2), style = MaterialTheme.typography.bodySmall)
            Text(stringResource(dev.ninfenz.mobile.R.string.settings_privacy_3), style = MaterialTheme.typography.bodySmall)
            Text(stringResource(dev.ninfenz.mobile.R.string.settings_privacy_4), style = MaterialTheme.typography.bodySmall)
            Text(stringResource(dev.ninfenz.mobile.R.string.settings_privacy_5), style = MaterialTheme.typography.bodySmall)
        }

        CardBox(title = stringResource(dev.ninfenz.mobile.R.string.settings_diag_info)) {
            MonoText(diagnosticsText)
            Button(onClick = {
                val manager = context.getSystemService(Context.CLIPBOARD_SERVICE) as? ClipboardManager
                manager?.setPrimaryClip(ClipData.newPlainText("NF Mobile diagnostics", diagnosticsText))
                copied = true
            }) {
                Text(if (copied) stringResource(dev.ninfenz.mobile.R.string.settings_copied) else stringResource(dev.ninfenz.mobile.R.string.settings_copy))
            }
        }
    }
}
