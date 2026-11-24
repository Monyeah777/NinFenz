package dev.ninfenz.mobile.ui.screens

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.widget.Toast
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import dev.ninfenz.mobile.core.ErrorCatalog
import dev.ninfenz.mobile.core.ErrorCodeEntry
import dev.ninfenz.mobile.core.ErrorCodeFilter
import dev.ninfenz.mobile.ui.components.NfTopAppBar
import dev.ninfenz.mobile.ui.theme.NfSpacing

/** 应用内错误码浏览器：搜索 code/message/fix，点击复制。 */
@Composable
fun ErrorCodesScreen(onBack: () -> Unit) {
    val context = LocalContext.current
    var query by rememberSaveable { mutableStateOf("") }
    val all = remember { ErrorCatalog.all() }
    val filtered = remember(query, all) { ErrorCodeFilter.apply(all, query) }

    Column(modifier = Modifier.fillMaxSize()) {
        NfTopAppBar(title = stringResource(dev.ninfenz.mobile.R.string.error_codes_title), onBack = onBack)
        OutlinedTextField(
            value = query,
            onValueChange = { query = it },
            modifier = Modifier.fillMaxWidth().padding(horizontal = NfSpacing.page),
            placeholder = { Text(stringResource(dev.ninfenz.mobile.R.string.error_codes_search)) },
            singleLine = true
        )
        if (all.isEmpty()) {
            Text(
                stringResource(dev.ninfenz.mobile.R.string.error_codes_not_loaded),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.error,
                modifier = Modifier.padding(NfSpacing.page)
            )
        } else if (filtered.isEmpty()) {
            Text(
                stringResource(dev.ninfenz.mobile.R.string.error_codes_no_result),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(NfSpacing.page)
            )
        } else {
            LazyColumn(modifier = Modifier.fillMaxSize()) {
                items(filtered, key = { it.code }) { entry ->
                    ErrorCodeRow(entry) {
                        val manager = context.getSystemService(Context.CLIPBOARD_SERVICE) as? ClipboardManager
                        manager?.setPrimaryClip(ClipData.newPlainText(entry.code, entry.code))
                        Toast.makeText(context, context.getString(dev.ninfenz.mobile.R.string.error_codes_copied, entry.code), Toast.LENGTH_SHORT).show()
                    }
                }
            }
        }
    }
}

@Composable
private fun ErrorCodeRow(entry: ErrorCodeEntry, onClick: () -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(horizontal = NfSpacing.page, vertical = 12.dp),
        verticalArrangement = Arrangement.spacedBy(2.dp)
    ) {
        Text(entry.code + " · " + entry.severity + " · exit=" + entry.exit, style = MaterialTheme.typography.titleMedium)
        Text(entry.message, style = MaterialTheme.typography.bodyMedium)
        Text(entry.fix, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}
